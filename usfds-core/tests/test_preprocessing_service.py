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
    FeatureEngineeringConfig,
    PreprocessingConfig,
    ResamplingConfig,
    ResamplingStrategy,
    ScalerType,
    SplitConfig,
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
            storage_path="datasets/raw/test.csv",
            pipeline_stage=PipelineStage.FEATURE_ENGINEERED,
        )
        self.raw_df = pd.DataFrame({
            "Time": [0, 3600, 7200, 10800, 14400, 18000, 21600, 25200, 28800, 32400, 36000, 39600],
            "Amount": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0, 110.0, 120.0],
            "V1": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0],
            "Class": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1],
        })
        # Save raw dataset into storage at parent_artifact.storage_path
        csv_buffer = io.StringIO()
        self.raw_df.to_csv(csv_buffer, index=False)
        self.storage.save_bytes(self.parent_artifact.storage_path, csv_buffer.getvalue().encode("utf-8"))

    def test_execute_service_lifecycle_and_lineage(self):
        config = PreprocessingConfig(
            cleansing=CleansingConfig(drop_duplicates=True),
            split=SplitConfig(time_column="Time", target_column="Class", test_size=0.2),
            feature_engineering=FeatureEngineeringConfig(
                time_col="Time",
                amount_col="Amount",
                enable_amount_ratios=True,
                enable_hour_of_day=True,
            ),
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
        self.assertIn("train_processed.parquet", result_artifact.storage_path)
        self.assertIn("test_processed.parquet", result_artifact.test_storage_path)
        self.assertIn("fitted_pipeline.joblib", result_artifact.pipeline_artifact_path)
        self.assertTrue(self.storage.exists(result_artifact.storage_path))
        self.assertTrue(self.storage.exists(result_artifact.test_storage_path))
        self.assertTrue(self.storage.exists(result_artifact.pipeline_artifact_path))


if __name__ == "__main__":
    unittest.main()
