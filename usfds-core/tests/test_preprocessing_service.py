import io
import unittest
from uuid import uuid4
import pandas as pd

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.enums import PipelineStage, ValidationStatus
from usfds_core.domain.schemas.preprocessing_config import (
    CleansingConfig,
    DimReductionConfig,
    DimReductionType,
    PreprocessingConfig,
    ResamplingConfig,
    ResamplingStrategy,
    ScalerType,
    SplitConfig,
    SystemColumn,
    TransformationConfig,
)
from usfds_core.services.preprocessing.preprocessing_service import PreprocessingExecutionService
from usfds_core.storage.base_storage import IFileStorage


class InMemoryStorage(IFileStorage):
    def __init__(self):
        self.files = {}

    def save_bytes(self, file_path: str, data: bytes) -> str:
        self.files[file_path] = data
        return file_path

    def read_bytes(self, file_path: str) -> bytes:
        if file_path not in self.files:
            raise FileNotFoundError(f"File {file_path} not found")
        return self.files[file_path]

    def exists(self, file_path: str) -> bool:
        return file_path in self.files


class TestPreprocessingExecutionService(unittest.TestCase):
    def setUp(self):
        self.storage = InMemoryStorage()
        self.service = PreprocessingExecutionService(self.storage)
        self.parent_artifact = DatasetArtifact(
            dataset_id=uuid4(),
            storage_path="datasets/fe",
            output_paths={
                "train": "datasets/fe/train_enriched.csv",
                "test": "datasets/fe/test_enriched.csv",
                "fitted_engineers": "datasets/fe/fitted_feature_engineers.joblib",
            },
            pipeline_stage=PipelineStage.FEATURE_ENGINEERED,
        )
        self.train_df = pd.DataFrame({
            "Time": [0, 3600, 7200, 10800, 14400, 18000, 21600, 25200, 28800, 32400],
            "Amount": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0],
            "V1": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
            "Class": [0, 0, 0, 0, 0, 0, 0, 0, 1, 1],
        })
        self.test_df = pd.DataFrame({
            "Time": [36000, 39600],
            "Amount": [110.0, 120.0],
            "V1": [11.0, 12.0],
            "Class": [0, 1],
        })
        # Save train, test, and fitted_engineers into storage
        train_csv = io.StringIO()
        self.train_df.to_csv(train_csv, index=False)
        self.storage.save_bytes(self.parent_artifact.output_paths["train"], train_csv.getvalue().encode("utf-8"))

        test_csv = io.StringIO()
        self.test_df.to_csv(test_csv, index=False)
        self.storage.save_bytes(self.parent_artifact.output_paths["test"], test_csv.getvalue().encode("utf-8"))
        self.storage.save_bytes(self.parent_artifact.output_paths["fitted_engineers"], b"dummy_fe_pipeline")

    def test_execute_service_lifecycle_and_lineage(self):
        config = PreprocessingConfig(
            split=SplitConfig(time_column="Time", target_column="Class"),
            transformation=TransformationConfig(
                numeric_columns=["Amount", "V1"],
                scaler=ScalerType.ROBUST,
            ),
            dim_reduction=DimReductionConfig(method=DimReductionType.NONE),
            resampling=ResamplingConfig(method=ResamplingStrategy.NONE),
        )

        result_artifact = self.service.execute(
            parent_artifact=self.parent_artifact,
            config=config,
            user_name="test_engineer",
        )

        self.assertIsInstance(result_artifact, DatasetArtifact)
        self.assertEqual(result_artifact.pipeline_stage, PipelineStage.PRE_PROCESSED)
        self.assertEqual(result_artifact.parent_artifact_id, self.parent_artifact.artifact_id)
        self.assertEqual(result_artifact.dataset_id, self.parent_artifact.dataset_id)
        self.assertEqual(result_artifact.validation_status, ValidationStatus.PASSED)
        self.assertTrue(len(result_artifact.checksum_sha256) > 0)
        self.assertEqual(
            result_artifact.storage_path,
            f"datasets/{self.parent_artifact.dataset_id}/artifacts/{result_artifact.artifact_id}",
        )
        self.assertIn("train", result_artifact.output_paths)
        self.assertIn("test", result_artifact.output_paths)
        self.assertIn("pipeline", result_artifact.output_paths)
        self.assertIn("train_processed.parquet", result_artifact.output_paths["train"])
        self.assertIn("test_processed.parquet", result_artifact.output_paths["test"])
        self.assertIn("fitted_pipeline.joblib", result_artifact.output_paths["pipeline"])
        self.assertTrue(self.storage.exists(result_artifact.output_paths["train"]))
        self.assertTrue(self.storage.exists(result_artifact.output_paths["test"]))
        self.assertTrue(self.storage.exists(result_artifact.output_paths["pipeline"]))
        self.assertEqual(result_artifact.validation_report["target_column"], "Class")

    def test_missing_test_storage_path_raises_error(self):
        artifact = DatasetArtifact(
            dataset_id=uuid4(),
            storage_path="datasets/fe",
            output_paths={
                "train": "datasets/fe/train_enriched.csv",
                "fitted_engineers": "datasets/fe/fitted_feature_engineers.joblib",
            },
            pipeline_stage=PipelineStage.FEATURE_ENGINEERED,
        )
        self.storage.save_bytes(artifact.output_paths["train"], b"dummy_train")
        self.storage.save_bytes(artifact.output_paths["fitted_engineers"], b"dummy_fe")
        config = PreprocessingConfig()
        with self.assertRaises(ValueError) as ctx:
            self.service.execute(artifact, config)
        self.assertIn("Missing test dataset", str(ctx.exception))

    def test_empty_test_storage_raises_error(self):
        artifact = DatasetArtifact(
            dataset_id=uuid4(),
            storage_path="datasets/fe",
            output_paths={
                "train": "datasets/fe/train_enriched.csv",
                "test": "datasets/fe/empty_test.csv",
                "fitted_engineers": "datasets/fe/fitted_feature_engineers.joblib",
            },
            pipeline_stage=PipelineStage.FEATURE_ENGINEERED,
        )
        empty_csv = io.StringIO()
        pd.DataFrame().to_csv(empty_csv, index=False)
        self.storage.save_bytes(artifact.output_paths["test"], empty_csv.getvalue().encode("utf-8"))

        config = PreprocessingConfig()
        with self.assertRaises(ValueError) as ctx:
            self.service.execute(artifact, config)
        self.assertIn("Loaded dataset is empty", str(ctx.exception))

    def test_empty_train_storage_raises_error(self):
        artifact = DatasetArtifact(
            dataset_id=uuid4(),
            storage_path="datasets/fe",
            output_paths={
                "train": "datasets/fe/empty_train.csv",
                "test": "datasets/fe/test_enriched.csv",
                "fitted_engineers": "datasets/fe/fitted_feature_engineers.joblib",
            },
            pipeline_stage=PipelineStage.FEATURE_ENGINEERED,
        )
        empty_csv = io.StringIO()
        pd.DataFrame().to_csv(empty_csv, index=False)
        self.storage.save_bytes(artifact.output_paths["train"], empty_csv.getvalue().encode("utf-8"))

        config = PreprocessingConfig()
        with self.assertRaises(ValueError) as ctx:
            self.service.execute(artifact, config)
        self.assertIn("Loaded dataset is empty", str(ctx.exception))

    def test_invalid_parent_stage_raises_error(self):
        artifact = DatasetArtifact(
            dataset_id=uuid4(),
            storage_path="datasets/mapped",
            output_paths={"mapped": "datasets/mapped/data.parquet"},
            pipeline_stage=PipelineStage.MAPPED,
        )
        config = PreprocessingConfig()
        with self.assertRaises(ValueError) as ctx:
            self.service.execute(artifact, config)
        self.assertIn("expects parent artifact at stage FEATURE_ENGINEERED", str(ctx.exception))

    def test_failed_parent_status_raises_error(self):
        artifact = DatasetArtifact(
            dataset_id=uuid4(),
            storage_path="datasets/fe",
            output_paths={
                "train": "datasets/fe/train_enriched.csv",
                "test": "datasets/fe/test_enriched.csv",
                "fitted_engineers": "datasets/fe/fitted_feature_engineers.joblib",
            },
            pipeline_stage=PipelineStage.FEATURE_ENGINEERED,
            validation_status=ValidationStatus.FAILED,
        )
        config = PreprocessingConfig()
        with self.assertRaises(ValueError) as ctx:
            self.service.execute(artifact, config)
        self.assertIn("validation status FAILED", str(ctx.exception))

    def test_execute_from_feature_engineered_artifact_with_identifiers_and_pca(self):
        fe_artifact = DatasetArtifact(
            dataset_id=uuid4(),
            storage_path="datasets/fe",
            output_paths={
                "train": "datasets/fe/train_enriched.parquet",
                "test": "datasets/fe/test_enriched.parquet",
                "fitted_engineers": "datasets/fe/fitted_feature_engineers.joblib",
            },
            pipeline_stage=PipelineStage.FEATURE_ENGINEERED,
        )

        train_df = pd.DataFrame({
            SystemColumn.EVENT_ID.value: [f"tx_train_{i}" for i in range(12)],
            SystemColumn.TIMESTAMP.value: [f"2024-01-01 10:{i:02d}:00" for i in range(12)],
            SystemColumn.USER_ID.value: [f"u_{i%3}" for i in range(12)],
            SystemColumn.AMOUNT.value: [100.0 * (i + 1) for i in range(12)],
            "hour_of_day": [10.0 + (i / 60.0) for i in range(12)],
            "tx_freq_last_1h": [float(i + 1) for i in range(12)],
            "v1": [0.1 * i for i in range(12)],
            "v2": [0.2 * i for i in range(12)],
            "v3": [0.3 * i for i in range(12)],
            SystemColumn.LABEL.value: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1],
        })
        train_buf = io.BytesIO()
        train_df.to_parquet(train_buf, index=False)
        self.storage.save_bytes(fe_artifact.output_paths["train"], train_buf.getvalue())

        test_df = pd.DataFrame({
            SystemColumn.EVENT_ID.value: ["tx_test_1", "tx_test_2"],
            SystemColumn.TIMESTAMP.value: ["2024-01-01 11:00:00", "2024-01-01 11:15:00"],
            SystemColumn.USER_ID.value: ["u_1", "u_2"],
            SystemColumn.AMOUNT.value: [150.0, 300.0],
            "hour_of_day": [11.0, 11.25],
            "tx_freq_last_1h": [1.0, 2.0],
            "v1": [1.5, 2.5],
            "v2": [0.5, 1.0],
            "v3": [0.8, 1.2],
            SystemColumn.LABEL.value: [0, 1],
        })
        test_buf = io.BytesIO()
        test_df.to_parquet(test_buf, index=False)
        self.storage.save_bytes(fe_artifact.output_paths["test"], test_buf.getvalue())
        self.storage.save_bytes(fe_artifact.output_paths["fitted_engineers"], b"dummy_fe")

        config = PreprocessingConfig(
            split=SplitConfig(target_column=SystemColumn.LABEL.value),
            transformation=TransformationConfig(
                numeric_columns=[],  # auto-detect
                scaler=ScalerType.STANDARD,
            ),
            dim_reduction=DimReductionConfig(method=DimReductionType.PCA, n_components=3),
            resampling=ResamplingConfig(method=ResamplingStrategy.NONE),
        )

        result_artifact = self.service.execute(
            parent_artifact=fe_artifact,
            config=config,
            user_name="ml_engineer",
        )

        self.assertEqual(result_artifact.pipeline_stage, PipelineStage.PRE_PROCESSED)
        self.assertEqual(result_artifact.validation_status, ValidationStatus.PASSED)
        self.assertIn(SystemColumn.EVENT_ID.value, result_artifact.validation_report["dropped_identifier_columns"])
        self.assertIn(SystemColumn.TIMESTAMP.value, result_artifact.validation_report["dropped_identifier_columns"])
        self.assertIn(SystemColumn.USER_ID.value, result_artifact.validation_report["dropped_identifier_columns"])

        proc_bytes = self.storage.read_bytes(result_artifact.output_paths["train"])
        proc_df = pd.read_parquet(io.BytesIO(proc_bytes))
        self.assertEqual(len(proc_df), 12)
        self.assertIn(SystemColumn.LABEL.value, proc_df.columns)
        self.assertEqual(len(proc_df.columns), 4)


if __name__ == "__main__":
    unittest.main()
