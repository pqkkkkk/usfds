import hashlib
import io
from pathlib import Path
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
from usfds_core.services.preprocessing.workspace import FeatureEngineeringWorkspace
from usfds_core.storage.base_storage import IFileStorage


class LeakedFeatureEngineeringExecutionService:
    """EXPERIMENTAL SERVICE: Orchestrates data cleansing BEFORE chronological splitting.

    INTENTIONAL DATA LEAKAGE:
    Calculates imputation statistics (mean, median, mode) and outlier bounds on the ENTIRE dataset
    (including future evaluation data) BEFORE splitting into train and test sets.
    Used for academic research and thesis experiments to quantify the risk and performance impact
    of lookahead bias and data leakage compared to the proper split-first pipeline.
    """

    def __init__(self, file_storage: IFileStorage):
        self.file_storage = file_storage

    def _load_dataframe(self, file_path_or_storage: Union[str, Path]) -> pd.DataFrame:
        """Loads data from local path or storage into a pandas DataFrame based on file format."""
        path_str = str(file_path_or_storage)
        p = Path(path_str)
        if p.is_file():
            if path_str.endswith(".parquet") or path_str.endswith(".pq"):
                return pd.read_parquet(p)
            elif path_str.endswith(".csv") or path_str.endswith(".txt"):
                return pd.read_csv(p)
            elif path_str.endswith(".json"):
                return pd.read_json(p)
            else:
                try:
                    return pd.read_parquet(p)
                except Exception:
                    return pd.read_csv(p)

        raw_bytes = self.file_storage.read_bytes(path_str)
        buffer = io.BytesIO(raw_bytes)

        if path_str.endswith(".parquet") or path_str.endswith(".pq"):
            return pd.read_parquet(buffer)
        elif path_str.endswith(".csv") or path_str.endswith(".txt"):
            return pd.read_csv(buffer)
        elif path_str.endswith(".json"):
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
        """Executes the Feature Engineering pipeline stage with INTENTIONAL DATA LEAKAGE.

        1. Validates parent_artifact is strictly at stage MAPPED with valid output_paths["mapped"].
        2. Loads mapped dataset strictly from parent_artifact.output_paths["mapped"].
        3. Cleanses ENTIRE dataset (fit_clean on ALL records), calculating imputation statistics across train+test.
        4. Splits cleansed dataset chronologically into train and test sets (LEAKAGE OCCURRED).
        5. Fits and transforms domain feature engineers (cyclical hour, amount ratios, velocity rolling windows).
        6. Saves train_enriched.parquet and test_enriched.parquet to storage.
        7. Persists fitted feature engineering transformers (.joblib).
        8. Returns immutable DatasetArtifact with stage FEATURE_ENGINEERED.
        """
        # Resolve config
        if not isinstance(config, FeatureEngineeringConfig):
            raise TypeError(
                f"LeakedFeatureEngineeringExecutionService.execute expects FeatureEngineeringConfig, "
                f"got {type(config).__name__}. If you are using PreprocessingConfig, "
                "please pass `config.feature_engineering`."
            )
        fe_config = config

        # 0. Validate Parent Artifact
        if parent_artifact.pipeline_stage != PipelineStage.MAPPED:
            raise ValueError(
                f"LeakedFeatureEngineeringExecutionService expects parent artifact at stage MAPPED, "
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

        new_artifact_id = uuid4()
        workspace = FeatureEngineeringWorkspace(dataset_artifact_id=new_artifact_id)
        workspace.initialize()

        try:
            # Download input mapped data from storage to local workspace
            mapped_input_file = workspace.get_mapped_data_path(input_file_path)
            raw_bytes = self.file_storage.read_bytes(input_file_path)
            with open(mapped_input_file, "wb") as f:
                f.write(raw_bytes)

            df = self._load_dataframe(mapped_input_file)
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

            # 2. Stateful Cleansing on ENTIRE dataset BEFORE splitting (DATA LEAKAGE POINT)
            cleanser = StandardDataCleanser(fe_config.cleansing)
            cleansed_df, val_report = cleanser.fit_clean(
                df,
                time_col=fe_config.time_col,
                amount_col=fe_config.amount_col,
                target_col=fe_config.split.target_column,
            )

            if len(cleansed_df) == 0 or len(cleansed_df.columns) == 0:
                err_msg = (
                    "All columns were dropped during data cleansing."
                    if len(cleansed_df.columns) == 0
                    else "All records were dropped during data cleansing."
                )
                return DatasetArtifact(
                    dataset_id=parent_artifact.dataset_id,
                    parent_artifact_id=parent_artifact.artifact_id,
                    pipeline_stage=PipelineStage.FEATURE_ENGINEERED,
                    storage_path="",
                    output_paths={},
                    checksum_sha256="",
                    validation_status=ValidationStatus.FAILED,
                    validation_report={
                        "error": err_msg,
                        **val_report,
                    },
                    created_by=user_name,
                )

            # 3. Chronological Splitting AFTER cleansing has leaked global statistics
            splitter = TemporalDataSplitter(fe_config.split)
            train_clean, test_clean = splitter.split_train_test(cleansed_df)

            if len(train_clean) == 0:
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
            val_report["data_leakage_injected"] = True

            # 5. Save Outputs to Workspace
            train_enriched.to_parquet(workspace.train_enriched_path, index=False)
            if len(test_enriched) > 0:
                test_enriched.to_parquet(workspace.test_enriched_path, index=False)
            joblib.dump(fitted_engineers, workspace.fitted_engineers_path)

            # 6. Upload Outputs from Workspace to Storage
            base_storage_dir = f"datasets/{parent_artifact.dataset_id}/artifacts/{new_artifact_id}"

            # 6a. Train Enriched Parquet
            with open(workspace.train_enriched_path, "rb") as f:
                train_bytes = f.read()
            train_storage_path = f"{base_storage_dir}/train_enriched.parquet"
            self.file_storage.save_bytes(train_storage_path, train_bytes)
            train_checksum = hashlib.sha256(train_bytes).hexdigest()

            # 6b. Test Enriched Parquet (if test rows exist)
            test_storage_path: Optional[str] = None
            if workspace.test_enriched_path.exists():
                with open(workspace.test_enriched_path, "rb") as f:
                    test_bytes = f.read()
                test_storage_path = f"{base_storage_dir}/test_enriched.parquet"
                self.file_storage.save_bytes(test_storage_path, test_bytes)

            # 6c. Persist Fitted FE Pipeline (.joblib)
            with open(workspace.fitted_engineers_path, "rb") as f:
                fe_bytes = f.read()
            fe_pipeline_path = f"{base_storage_dir}/fitted_feature_engineers.joblib"
            self.file_storage.save_bytes(fe_pipeline_path, fe_bytes)

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
        finally:
            workspace.cleanup()


__all__ = ["LeakedFeatureEngineeringExecutionService"]
