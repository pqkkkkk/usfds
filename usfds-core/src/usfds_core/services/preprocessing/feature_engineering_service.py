import hashlib
import io
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4
import joblib
import numpy as np
import pandas as pd

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.enums import PipelineStage, ValidationStatus
from usfds_core.domain.schemas.artifact_output import (
    ArtifactOutputKey,
    validate_stage_outputs,
)
from usfds_core.domain.schemas.preprocessing_config import FeatureEngineeringConfig
from usfds_core.services.preprocessing.cleansers.standard_cleanser import StandardDataCleanser
from usfds_core.services.preprocessing.feature_engineering.credit_card_engineer import CreditCardFeatureEngineer
from usfds_core.services.preprocessing.feature_engineering.velocity_engineer import VelocityFeatureEngineer
from usfds_core.services.preprocessing.splitters.temporal_splitter import TemporalDataSplitter
from usfds_core.storage.base_storage import IFileStorage


class FeatureEngineeringExecutionService:
    """Orchestrates chronological splitting, stateful data cleansing, and domain feature engineering.

    Produces business-semantic enriched datasets (train_enriched.parquet, test_enriched.parquet)
    at stage FEATURE_ENGINEERED, maintaining raw transaction identifiers (event_id, timestamp,
    amount, user_id) alongside behavioral features for downstream Rule Engine and ML models.
    """

    def __init__(self, file_storage: IFileStorage):
        self.file_storage = file_storage

    def _load_dataframe(self, storage_path: str) -> pd.DataFrame:
        """Loads data from storage into a pandas DataFrame based on file format."""
        raw_bytes = self.file_storage.read_bytes(storage_path)
        buffer = io.BytesIO(raw_bytes)

        if storage_path.endswith(".parquet") or storage_path.endswith(".pq"):
            return pd.read_parquet(buffer)
        elif storage_path.endswith(".csv") or storage_path.endswith(".txt"):
            return pd.read_csv(buffer)
        elif storage_path.endswith(".json"):
            return pd.read_json(buffer)
        else:
            try:
                return pd.read_parquet(buffer)
            except Exception:
                buffer.seek(0)
                return pd.read_csv(buffer)

    def execute(
        self,
        parent_artifact: DatasetArtifact,
        config: FeatureEngineeringConfig,
        user_name: str = "system",
    ) -> DatasetArtifact:
        """Executes the Feature Engineering pipeline stage.

        1. Validates parent_artifact is strictly at stage MAPPED with valid output_paths["mapped"].
        2. Loads mapped dataset strictly from parent_artifact.output_paths["mapped"].
        3. Splits dataset chronologically into train and test sets to prevent future data leakage.
        4. Cleanses train set, learning imputation values and clipping bounds. Cleanses test set using train stats.
        5. Fits and transforms domain feature engineers (cyclical hour, amount ratios, velocity rolling windows).
        6. Saves train_enriched.parquet and test_enriched.parquet to storage.
        7. Persists fitted feature engineering transformers (.joblib).
        8. Returns immutable DatasetArtifact with stage FEATURE_ENGINEERED.
        """
        # Resolve config
        if not isinstance(config, FeatureEngineeringConfig):
            raise TypeError(
                f"FeatureEngineeringExecutionService.execute expects FeatureEngineeringConfig, "
                f"got {type(config).__name__}. If you are using PreprocessingConfig, "
                "please pass `config.feature_engineering`."
            )
        fe_config = config

        # 0. Validate Parent Artifact
        if parent_artifact.pipeline_stage != PipelineStage.MAPPED:
            raise ValueError(
                f"FeatureEngineeringExecutionService expects parent artifact at stage MAPPED, "
                f"got '{parent_artifact.pipeline_stage}'."
            )

        if parent_artifact.validation_status == ValidationStatus.FAILED:
            raise ValueError(
                f"Parent artifact '{parent_artifact.artifact_id}' has validation status FAILED."
            )

        validate_stage_outputs(PipelineStage.MAPPED, parent_artifact.output_paths)

        # 1. Resolve and Load Dataset
        input_file_path = parent_artifact.output_paths.get(ArtifactOutputKey.MAPPED.value)
        if not input_file_path or not self.file_storage.exists(input_file_path):
            raise ValueError(
                f"Mapped dataset file not found in storage at '{input_file_path}' "
                f"(output_paths={parent_artifact.output_paths})."
            )

        df = self._load_dataframe(input_file_path)
        if df.empty:
            return DatasetArtifact(
                dataset_id=parent_artifact.dataset_id,
                parent_artifact_id=parent_artifact.artifact_id,
                pipeline_stage=PipelineStage.FEATURE_ENGINEERED,
                storage_path="",
                output_paths={},
                checksum_sha256="",
                validation_status=ValidationStatus.FAILED,
                validation_report={"error": "Loaded dataset is empty."},
                created_by=user_name,
            )

        # 2. Chronological Splitting (executed first to prevent data leakage)
        splitter = TemporalDataSplitter(fe_config.split)
        train_df, test_df = splitter.split_train_test(df)

        if len(train_df) == 0:
            return DatasetArtifact(
                dataset_id=parent_artifact.dataset_id,
                parent_artifact_id=parent_artifact.artifact_id,
                pipeline_stage=PipelineStage.FEATURE_ENGINEERED,
                storage_path="",
                output_paths={},
                checksum_sha256="",
                validation_status=ValidationStatus.FAILED,
                validation_report={"error": "Chronological split resulted in 0 training records."},
                created_by=user_name,
            )

        # 3. Stateful Cleansing (fit on train, apply to test)
        cleanser = StandardDataCleanser(fe_config.cleansing)
        train_clean, val_report = cleanser.fit_clean(
            train_df,
            time_col=fe_config.time_col,
            amount_col=fe_config.amount_col,
        )

        if len(train_clean) == 0:
            return DatasetArtifact(
                dataset_id=parent_artifact.dataset_id,
                parent_artifact_id=parent_artifact.artifact_id,
                pipeline_stage=PipelineStage.FEATURE_ENGINEERED,
                storage_path="",
                output_paths={},
                checksum_sha256="",
                validation_status=ValidationStatus.FAILED,
                validation_report={
                    "error": "All training records were dropped during data cleansing.",
                    **val_report,
                },
                created_by=user_name,
            )

        test_clean = (
            cleanser.clean(
                test_df,
                time_col=fe_config.time_col,
                amount_col=fe_config.amount_col,
            )
            if len(test_df) > 0
            else test_df.copy()
        )

        # 4. Feature Engineering
        train_enriched = train_clean
        test_enriched = test_clean
        fitted_engineers: Dict[str, Any] = {"cleanser": cleanser}
        engineered_features: List[str] = []

        # 4a. Credit Card Domain Features (cyclical time, amount-to-mean ratio)
        if fe_config.enable_amount_ratios or fe_config.enable_hour_of_day:
            cc_engineer = CreditCardFeatureEngineer(
                time_col=fe_config.time_col,
                amount_col=fe_config.amount_col,
                add_ratio=fe_config.enable_amount_ratios,
                enable_hour_of_day=fe_config.enable_hour_of_day,
            )
            cc_engineer.fit(train_enriched)
            train_enriched = cc_engineer.transform(train_enriched)
            if len(test_enriched) > 0:
                test_enriched = cc_engineer.transform(test_enriched)

            fitted_engineers["credit_card_engineer"] = cc_engineer
            if fe_config.enable_hour_of_day:
                engineered_features.append("hour_of_day")
            if fe_config.enable_amount_ratios:
                engineered_features.append("amount_to_mean_ratio")

        # 4b. Rolling Window Velocity Features (tx_freq_last_*h, tx_sum_last_*h)
        if fe_config.enable_velocity_features:
            vel_engineer = VelocityFeatureEngineer(
                user_id_col=fe_config.user_id_col,
                time_col=fe_config.time_col,
                amount_col=fe_config.amount_col,
                windows=fe_config.velocity_windows,
            )
            vel_engineer.fit(train_enriched)
            train_enriched = vel_engineer.transform(train_enriched)
            if len(test_enriched) > 0:
                test_enriched = vel_engineer.transform(test_enriched)

            fitted_engineers["velocity_engineer"] = vel_engineer
            for w in fe_config.velocity_windows:
                engineered_features.append(f"tx_freq_last_{w}h")
                if fe_config.amount_col:
                    engineered_features.append(f"tx_sum_last_{w}h")

        val_report["engineered_features"] = engineered_features
        val_report["train_rows"] = len(train_enriched)
        val_report["test_rows"] = len(test_enriched)

        # 5. Persist Datasets to Storage (Parquet)
        new_artifact_id = uuid4()
        base_storage_dir = f"datasets/{parent_artifact.dataset_id}/artifacts/{new_artifact_id}"

        # 5a. Train Enriched Parquet
        train_buffer = io.BytesIO()
        train_enriched.to_parquet(train_buffer, index=False)
        train_bytes = train_buffer.getvalue()
        train_storage_path = f"{base_storage_dir}/train_enriched.parquet"
        self.file_storage.save_bytes(train_storage_path, train_bytes)
        train_checksum = hashlib.sha256(train_bytes).hexdigest()

        # 5b. Test Enriched Parquet (if test rows exist)
        test_storage_path: Optional[str] = None
        if len(test_enriched) > 0:
            test_buffer = io.BytesIO()
            test_enriched.to_parquet(test_buffer, index=False)
            test_bytes = test_buffer.getvalue()
            test_storage_path = f"{base_storage_dir}/test_enriched.parquet"
            self.file_storage.save_bytes(test_storage_path, test_bytes)

        # 6. Persist Fitted FE Pipeline (.joblib)
        joblib_buffer = io.BytesIO()
        joblib.dump(fitted_engineers, joblib_buffer)
        joblib_bytes = joblib_buffer.getvalue()
        fe_pipeline_path = f"{base_storage_dir}/fitted_feature_engineers.joblib"
        self.file_storage.save_bytes(fe_pipeline_path, joblib_bytes)

        # 7. Create Schema Snapshot and DatasetArtifact
        schema_snapshot = {str(col): str(dtype) for col, dtype in train_enriched.dtypes.items()}

        output_paths = {
            ArtifactOutputKey.TRAIN.value: train_storage_path,
            ArtifactOutputKey.FITTED_ENGINEERS.value: fe_pipeline_path,
        }
        if test_storage_path:
            output_paths[ArtifactOutputKey.TEST.value] = test_storage_path

        return DatasetArtifact(
            artifact_id=new_artifact_id,
            dataset_id=parent_artifact.dataset_id,
            parent_artifact_id=parent_artifact.artifact_id,
            pipeline_stage=PipelineStage.FEATURE_ENGINEERED,
            storage_path=base_storage_dir,
            output_paths=output_paths,
            checksum_sha256=train_checksum,
            schema_snapshot=schema_snapshot,
            row_count=len(train_enriched),
            column_count=len(train_enriched.columns),
            validation_status=ValidationStatus.PASSED,
            validation_report=val_report,
            created_by=user_name,
        )


__all__ = ["FeatureEngineeringExecutionService"]
