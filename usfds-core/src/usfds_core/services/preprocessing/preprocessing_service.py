import hashlib
import io
from typing import Any, Optional, Union
from uuid import uuid4
import joblib
import numpy as np
import pandas as pd

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.enums import PipelineStage, ValidationStatus
from usfds_core.domain.schemas.preprocessing_config import PreprocessingConfig
from usfds_core.services.preprocessing.cleansers.standard_cleanser import StandardDataCleanser
from usfds_core.services.preprocessing.pipeline_builder import PreprocessingPipelineBuilder
from usfds_core.services.preprocessing.splitters.temporal_splitter import TemporalDataSplitter
from usfds_core.storage.base_storage import IFileStorage


class PreprocessingExecutionService:
    """Service that orchestrates the entire data cleansing, splitting, pipeline fitting, and artifact generation."""

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
            # Fallback: try parquet first, then csv
            try:
                return pd.read_parquet(buffer)
            except Exception:
                buffer.seek(0)
                return pd.read_csv(buffer)

    def _transform_features(self, pipeline: Any, X: pd.DataFrame) -> Union[pd.DataFrame, np.ndarray]:
        """Sequentially applies all transformer steps from the fitted pipeline, skipping resampling steps."""
        X_curr = X
        if hasattr(pipeline, "steps"):
            for name, step in pipeline.steps:
                if hasattr(step, "transform"):
                    X_curr = step.transform(X_curr)
        elif hasattr(pipeline, "transform"):
            X_curr = pipeline.transform(X_curr)
        return X_curr

    def execute(
        self,
        parent_artifact: DatasetArtifact,
        config: PreprocessingConfig,
        user_name: str = "system",
    ) -> DatasetArtifact:
        # 1. Load Raw Dataset from Storage via parent_artifact.storage_path
        raw_df = self._load_dataframe(parent_artifact.storage_path)

        # 2. Cleanse & Validate Dataset
        cleanser = StandardDataCleanser(config.cleansing)
        df_clean, val_status, val_report = cleanser.clean_and_validate(raw_df)

        if val_status == "failed" or len(df_clean) == 0:
            return DatasetArtifact(
                dataset_id=parent_artifact.dataset_id,
                parent_artifact_id=parent_artifact.artifact_id,
                pipeline_stage=PipelineStage.PRE_PROCESSED,
                storage_path="",
                checksum_sha256="",
                validation_status=ValidationStatus.FAILED,
                validation_report=val_report,
                created_by=user_name,
            )

        # 3. Split dataset chronologically (train/test)
        splitter = TemporalDataSplitter(config.split)
        X_train, X_test, y_train, y_test = splitter.split(df_clean)

        # 4. Build & Fit Pipeline on Train Set (Strict Data Leakage Prevention)
        pipeline = PreprocessingPipelineBuilder.build(config)
        if hasattr(pipeline, "fit_resample"):
            X_train_resampled, y_train_resampled = pipeline.fit_resample(X_train, y_train)
        else:
            X_train_resampled = pipeline.fit_transform(X_train, y_train)
            y_train_resampled = y_train

        # 5. Save Processed Train Data to Storage (Parquet)
        new_artifact_id = uuid4()
        base_storage_dir = f"datasets/{parent_artifact.dataset_id}/artifacts/{new_artifact_id}"

        if isinstance(X_train_resampled, pd.DataFrame):
            train_processed_df = X_train_resampled.copy().reset_index(drop=True)
        else:
            train_processed_df = pd.DataFrame(X_train_resampled)

        target_col = config.split.target_column
        train_processed_df[target_col] = np.asarray(y_train_resampled)

        parquet_buffer = io.BytesIO()
        train_processed_df.to_parquet(parquet_buffer, index=False)
        data_bytes = parquet_buffer.getvalue()
        data_storage_path = f"{base_storage_dir}/train_processed.parquet"
        self.file_storage.save_bytes(data_storage_path, data_bytes)
        data_checksum = hashlib.sha256(data_bytes).hexdigest()

        # 6. Transform & Save Processed Test Data to Storage (Without Resampling)
        test_storage_path: Optional[str] = None
        if len(X_test) > 0:
            X_test_transformed = self._transform_features(pipeline, X_test)
            if isinstance(X_test_transformed, pd.DataFrame):
                test_processed_df = X_test_transformed.copy().reset_index(drop=True)
            else:
                test_processed_df = pd.DataFrame(X_test_transformed)

            test_processed_df[target_col] = np.asarray(y_test)

            test_parquet_buffer = io.BytesIO()
            test_processed_df.to_parquet(test_parquet_buffer, index=False)
            test_data_bytes = test_parquet_buffer.getvalue()
            test_storage_path = f"{base_storage_dir}/test_processed.parquet"
            self.file_storage.save_bytes(test_storage_path, test_data_bytes)
            val_report["test_rows"] = len(test_processed_df)
        else:
            val_report["test_rows"] = 0

        val_report["train_rows"] = len(train_processed_df)

        # 7. Persist Fitted Pipeline (.joblib) for Inference
        joblib_buffer = io.BytesIO()
        joblib.dump(pipeline, joblib_buffer)
        pipeline_bytes = joblib_buffer.getvalue()
        pipeline_storage_path = f"{base_storage_dir}/fitted_pipeline.joblib"
        self.file_storage.save_bytes(pipeline_storage_path, pipeline_bytes)

        # 8. Build Schema Snapshot and return immutable DatasetArtifact
        schema_snapshot = {str(col): str(dtype) for col, dtype in train_processed_df.dtypes.items()}

        return DatasetArtifact(
            artifact_id=new_artifact_id,
            dataset_id=parent_artifact.dataset_id,
            parent_artifact_id=parent_artifact.artifact_id,
            pipeline_stage=PipelineStage.PRE_PROCESSED,
            storage_path=data_storage_path,
            pipeline_artifact_path=pipeline_storage_path,
            test_storage_path=test_storage_path,
            checksum_sha256=data_checksum,
            schema_snapshot=schema_snapshot,
            row_count=len(train_processed_df),
            column_count=len(train_processed_df.columns),
            validation_status=ValidationStatus.PASSED if val_status == "passed" else ValidationStatus.WARNING,
            validation_report=val_report,
            created_by=user_name,
        )


__all__ = ["PreprocessingExecutionService"]
