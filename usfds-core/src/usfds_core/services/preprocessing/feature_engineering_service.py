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


class FeatureEngineeringExecutionService:
    """Orchestrates chronological splitting, stateful data cleansing, and domain feature engineering.

    Produces business-semantic enriched datasets (train_enriched.parquet, test_enriched.parquet)
    at stage FEATURE_ENGINEERED, maintaining raw transaction identifiers (event_id, timestamp,
    amount, user_id) alongside behavioral features for downstream Rule Engine and ML models.
    """

    def __init__(self, file_storage: IFileStorage):
        self.file_storage = file_storage

    def _load_dataframe_from_bytes(self, path_str: str, raw_bytes: bytes) -> pd.DataFrame:
        """Parses DataFrame from raw bytes based on file extension."""
        buffer = io.BytesIO(raw_bytes)
        if path_str.endswith(".parquet") or path_str.endswith(".pq"):
            return pd.read_parquet(buffer)
        elif path_str.endswith(".csv") or path_str.endswith(".txt"):
            return pd.read_csv(buffer)
        elif path_str.endswith(".json"):
            return pd.read_json(buffer)
        try:
            return pd.read_parquet(buffer)
        except Exception:
            buffer.seek(0)
            return pd.read_csv(buffer)

    def _load_dataframe(self, file_path_or_storage: Union[str, Path]) -> pd.DataFrame:
        """Loads data from IFileStorage into a pandas DataFrame based on file format."""
        path_str = str(file_path_or_storage)
        return self._load_dataframe_from_bytes(path_str, self.file_storage.read_bytes(path_str))

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

        new_artifact_id = uuid4()
        workspace = FeatureEngineeringWorkspace(dataset_artifact_id=new_artifact_id)
        workspace.initialize()

        try:
            # Download input mapped data from storage to local workspace
            mapped_input_file = workspace.get_mapped_data_path(input_file_path)
            raw_bytes = self.file_storage.read_bytes(input_file_path)
            with open(mapped_input_file, "wb") as f:
                f.write(raw_bytes)

            df = self._load_dataframe_from_bytes(input_file_path, raw_bytes)
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
                target_col=fe_config.split.target_column,
            )

            if len(train_clean) == 0 or len(train_clean.columns) == 0:
                err_msg = (
                    "All training columns were dropped during data cleansing."
                    if len(train_clean.columns) == 0
                    else "All training records were dropped during data cleansing."
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

            test_clean = (
                cleanser.clean(
                    test_df,
                    time_col=fe_config.time_col,
                    amount_col=fe_config.amount_col,
                    target_col=fe_config.split.target_column,
                )
                if len(test_df) > 0
                else test_df.copy()
            )

            # 4. Feature Engineering
            train_enriched = train_clean
            test_enriched = test_clean
            fitted_engineers: Any = {"cleanser": cleanser}
            engineered_features: List[str] = []

            if fe_config.feature_definitions:
                from usfds_core.domain.entities.feature import Feature
                from usfds_core.domain.schemas.system_metadata import build_default_system_columns
                from usfds_core.services.features.code_validator import compute_code_sha256
                from usfds_core.services.features.compatibility import FeatureCompatibilityService
                from usfds_core.services.features.compiler import CompiledFeaturePipeline

                raw_specs = [
                    s if isinstance(s, Feature) else Feature.from_dict(s)
                    for s in fe_config.feature_definitions
                ]
                parent_vr_sem = (
                    (parent_artifact.validation_report or {}).get("column_semantic_types")
                    if isinstance(parent_artifact.validation_report, dict)
                    else None
                )
                compat_svc = FeatureCompatibilityService(system_metadata=build_default_system_columns())
                compat_report = compat_svc.evaluate(
                    raw_specs,
                    [str(c) for c in train_clean.columns],
                    column_semantic_types=parent_vr_sem,
                )
                status_by_id = {item.feature_id: item for item in compat_report.items}
                applicable_specs = [
                    f for f in raw_specs
                    if status_by_id[f.feature_id].status == "AVAILABLE"
                ]
                skipped_items = [
                    {
                        "feature_id": str(item.feature_id),
                        "feature_key": item.feature_key,
                        "status": item.status,
                        "missing_inputs": list(item.missing_inputs),
                        "missing_dependencies": list(item.missing_dependencies),
                        "missing_packages": list(item.missing_packages),
                    }
                    for item in compat_report.items
                    if item.status != "AVAILABLE"
                ]

                if not applicable_specs:
                    raise ValueError(
                        "Không có đặc trưng nào khả dụng trên tập dữ liệu này (toàn bộ đặc trưng được chọn đều thiếu cột đầu vào hoặc thư viện)."
                    )
                if fe_config.strict_feature_compatibility and skipped_items:
                    skipped_keys = ", ".join(s["feature_key"] for s in skipped_items)
                    raise ValueError(
                        f"Chế độ strict_feature_compatibility=True phát hiện đặc trưng không khả dụng: {skipped_keys}."
                    )

                pipeline = CompiledFeaturePipeline(
                    specs=applicable_specs,
                    cleanser=cleanser,
                    time_col=fe_config.time_col or "timestamp",
                    label_col=fe_config.split.target_column or "label",
                )
                train_enriched = pipeline.fit_transform(train_enriched)
                if len(test_enriched) > 0:
                    test_enriched = pipeline.transform(test_enriched)

                engineered_features = list(pipeline.engineered_features)
                pipeline.skipped_features = skipped_items
                fitted_engineers = pipeline

                origin_map = {
                    str(d.get("feature_key")): d.get("source_feature_set_id")
                    for d in fe_config.feature_definitions
                    if isinstance(d, dict) and d.get("feature_key")
                }
                val_report["feature_set_ids"] = list(fe_config.feature_set_ids or [])
                val_report["feature_ids"] = list(fe_config.feature_ids or [])
                val_report["skipped_features"] = skipped_items
                val_report["feature_set_snapshot"] = [
                    {
                        **spec_dict,
                        "snapshot_sha256": spec_dict.get("snapshot_sha256")
                        or compute_code_sha256(spec_dict.get("source_code")),
                    }
                    for spec_dict in pipeline.pinned_specs
                ]
                val_report["materialized_features"] = [
                    {
                        "feature_key": f.feature_key,
                        "feature_id": str(f.feature_id),
                        "source_feature_set_id": origin_map.get(f.feature_key),
                        "status": "APPLIED",
                    }
                    for f in applicable_specs
                ] + [
                    {
                        "feature_key": s["feature_key"],
                        "feature_id": s["feature_id"],
                        "source_feature_set_id": origin_map.get(s["feature_key"]),
                        "status": "SKIPPED",
                    }
                    for s in skipped_items
                ]
            else:
                # 4a. Legacy Credit Card Domain Features (cyclical time, amount-to-mean ratio)
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

                # 4b. Legacy Rolling Window Velocity Features (tx_freq_last_*h, tx_sum_last_*h)
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
            parent_vr = parent_artifact.validation_report or {}
            if isinstance(parent_vr, dict):
                if "column_mapping" in parent_vr and isinstance(parent_vr["column_mapping"], dict):
                    val_report["column_mapping"] = dict(parent_vr["column_mapping"])
                if "retained_columns" in parent_vr and isinstance(parent_vr["retained_columns"], list):
                    val_report["retained_columns"] = list(parent_vr["retained_columns"])
                if "non_ml_columns" in parent_vr and isinstance(parent_vr["non_ml_columns"], list):
                    val_report["non_ml_columns"] = list(parent_vr["non_ml_columns"])
                if "metadata_snapshot" in parent_vr and isinstance(parent_vr["metadata_snapshot"], list):
                    val_report["metadata_snapshot"] = list(parent_vr["metadata_snapshot"])
                if "time_format" in parent_vr:
                    val_report["time_format"] = parent_vr["time_format"]

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


__all__ = ["FeatureEngineeringExecutionService"]
