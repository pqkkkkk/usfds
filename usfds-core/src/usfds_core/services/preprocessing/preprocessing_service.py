import hashlib
import io
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4
import joblib
import numpy as np
import pandas as pd

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.enums import PipelineStage, ValidationStatus
from usfds_core.domain.schemas.preprocessing_config import (
    NON_ML_COLUMNS,
    PreprocessingConfig,
    SystemColumn,
)
from usfds_core.services.preprocessing.pipeline_builder import PreprocessingPipelineBuilder
from usfds_core.storage.base_storage import IFileStorage


class PreprocessingExecutionService:
    """Orchestrates ML feature transformation, scaling, encoding, dimensionality reduction,
    and resampling for Stage PRE_PROCESSED.

    Consumes enriched datasets from Stage FEATURE_ENGINEERED (train_enriched.parquet, test_enriched.parquet),
    filters out non-predictive metadata/identifiers (event_id, timestamp, user_id), applies
    mathematical transformations via PreprocessingPipelineBuilder, and persists model-ready artifacts.
    """

    def __init__(self, file_storage: IFileStorage):
        self.file_storage = file_storage

    def _load_dataframe(self, storage_path: str) -> pd.DataFrame:
        """Loads data from storage into a pandas DataFrame based on file format."""
        raw_bytes = self.file_storage.read_bytes(storage_path)
        if not raw_bytes or len(raw_bytes.strip()) == 0:
            raise ValueError("Loaded dataset is empty.")
        buffer = io.BytesIO(raw_bytes)

        try:
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
        except pd.errors.EmptyDataError:
            raise ValueError("Loaded dataset is empty.")

    def _resolve_target_col(self, df: pd.DataFrame, target_col_name: str) -> str:
        """Resolves target column with alias matching (label, Class, target, is_fraud)."""
        if target_col_name in df.columns:
            return target_col_name
        for c in df.columns:
            if str(c).lower() == str(target_col_name).lower():
                return str(c)
        aliases = [SystemColumn.LABEL.value, "class", "target", "is_fraud"]
        for a in aliases:
            if a in df.columns:
                return a
            for c in df.columns:
                if str(c).lower() == a.lower():
                    return str(c)
        raise ValueError(f"Target column '{target_col_name}' not found in DataFrame columns: {list(df.columns)}")

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

    def _to_dataframe(
        self,
        data: Union[pd.DataFrame, np.ndarray],
        feature_names: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """Converts transformer/resampler output (which may be numpy.ndarray or pd.DataFrame)
        into a pandas DataFrame with valid column names so it can be stored as Parquet.
        """
        if isinstance(data, pd.DataFrame):
            return data.copy().reset_index(drop=True)
        if feature_names and len(feature_names) == data.shape[1]:
            cols = feature_names
        else:
            cols = [f"feature_{i}" for i in range(data.shape[1])]
        return pd.DataFrame(data, columns=cols)

    def execute(
        self,
        parent_artifact: DatasetArtifact,
        config: PreprocessingConfig,
        user_name: str = "system",
    ) -> DatasetArtifact:
        """Executes ML Preprocessing & Transformation pipeline stage.

        1. Loads train data from parent_artifact.storage_path.
        2. Loads test data from parent_artifact.test_storage_path.
           (Throws ValueError if test dataset is missing or empty, as PRE_PROCESSED strictly requires both sets).
        3. Separates features and target label.
        4. Drops non-predictive identifiers/metadata columns (event_id, timestamp, user_id).
        5. Builds and fits ML transformation pipeline (Scalers, Encoders, PCA, Resampling) on train set.
        6. Transforms test set using fitted transformers (without resampling).
        7. Persists train_processed.parquet, test_processed.parquet, and fitted_pipeline.joblib.
        8. Returns immutable DatasetArtifact with stage PRE_PROCESSED.
        """
        # 1. Load Train Dataset from Stage FEATURE_ENGINEERED
        train_df = self._load_dataframe(parent_artifact.storage_path)
        if train_df.empty:
            return DatasetArtifact(
                dataset_id=parent_artifact.dataset_id,
                parent_artifact_id=parent_artifact.artifact_id,
                pipeline_stage=PipelineStage.PRE_PROCESSED,
                storage_path="",
                checksum_sha256="",
                validation_status=ValidationStatus.FAILED,
                validation_report={"error": "Loaded training dataset is empty."},
                created_by=user_name,
            )

        # 2. Verify and Load Test Dataset from Stage FEATURE_ENGINEERED
        if not parent_artifact.test_storage_path or not self.file_storage.exists(parent_artifact.test_storage_path):
            raise ValueError(
                f"Missing test dataset in parent artifact (test_storage_path={parent_artifact.test_storage_path}). "
                "Stage PRE_PROCESSED strictly requires an enriched test dataset produced from stage FEATURE_ENGINEERED."
            )

        test_df = self._load_dataframe(parent_artifact.test_storage_path)
        if test_df.empty:
            raise ValueError(
                "Loaded test dataset is empty. A non-empty test dataset from stage FEATURE_ENGINEERED is required."
            )

        # 3. Extract Target Label
        target_col = self._resolve_target_col(train_df, config.split.target_column)
        y_train = train_df[target_col]
        X_train = train_df.drop(columns=[target_col])

        test_target_col = self._resolve_target_col(test_df, config.split.target_column)
        y_test = test_df[test_target_col]
        X_test = test_df.drop(columns=[test_target_col])

        # 4. Drop non-ML metadata/identifier columns from features
        cols_to_drop = [c for c in X_train.columns if str(c).lower() in NON_ML_COLUMNS]
        X_train = X_train.drop(columns=cols_to_drop)
        X_test = X_test.drop(columns=[c for c in cols_to_drop if c in X_test.columns])

        # 5. Build & Fit ML Pipeline on Train Set (Strict Data Leakage Prevention)
        pipeline = PreprocessingPipelineBuilder.build(config, sample_df=X_train)

        if hasattr(pipeline, "fit_resample"):
            X_train_resampled, y_train_resampled = pipeline.fit_resample(X_train, y_train)
        else:
            X_train_resampled = pipeline.fit_transform(X_train, y_train)
            y_train_resampled = y_train

        # 6. Format and Save Processed Train Data to Storage (Parquet)
        new_artifact_id = uuid4()
        base_storage_dir = f"datasets/{parent_artifact.dataset_id}/artifacts/{new_artifact_id}"

        train_processed_df = self._to_dataframe(X_train_resampled)
        train_processed_df[target_col] = np.asarray(y_train_resampled)

        parquet_buffer = io.BytesIO()
        train_processed_df.to_parquet(parquet_buffer, index=False)
        data_bytes = parquet_buffer.getvalue()
        data_storage_path = f"{base_storage_dir}/train_processed.parquet"
        self.file_storage.save_bytes(data_storage_path, data_bytes)
        data_checksum = hashlib.sha256(data_bytes).hexdigest()

        # 7. Transform & Save Processed Test Data to Storage (Without Resampling)
        X_test_transformed = self._transform_features(pipeline, X_test)
        test_feature_names = [c for c in train_processed_df.columns if c != target_col]
        test_processed_df = self._to_dataframe(X_test_transformed, feature_names=test_feature_names)
        test_processed_df[target_col] = np.asarray(y_test)

        test_parquet_buffer = io.BytesIO()
        test_processed_df.to_parquet(test_parquet_buffer, index=False)
        test_data_bytes = test_parquet_buffer.getvalue()
        test_storage_path = f"{base_storage_dir}/test_processed.parquet"
        self.file_storage.save_bytes(test_storage_path, test_data_bytes)

        val_report: Dict[str, Any] = {
            "train_rows": len(train_processed_df),
            "test_rows": len(test_processed_df),
            "feature_columns": [c for c in train_processed_df.columns if c != target_col],
            "dropped_identifier_columns": cols_to_drop,
        }

        # 8. Persist Fitted Pipeline (.joblib) for Inference
        joblib_buffer = io.BytesIO()
        joblib.dump(pipeline, joblib_buffer)
        pipeline_bytes = joblib_buffer.getvalue()
        pipeline_storage_path = f"{base_storage_dir}/fitted_pipeline.joblib"
        self.file_storage.save_bytes(pipeline_storage_path, pipeline_bytes)

        # 9. Build Schema Snapshot and return immutable DatasetArtifact
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
            validation_status=ValidationStatus.PASSED,
            validation_report=val_report,
            created_by=user_name,
        )


__all__ = ["PreprocessingExecutionService"]
