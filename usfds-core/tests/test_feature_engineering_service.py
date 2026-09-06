import io
import unittest
from uuid import uuid4
import pandas as pd

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.enums import PipelineStage, ValidationStatus
from usfds_core.domain.schemas.preprocessing_config import (
    CleansingConfig,
    FeatureEngineeringConfig,
    MissingValueStrategy,
    PreprocessingConfig,
    SplitConfig,
    SystemColumn,
)
from usfds_core.services.preprocessing.feature_engineering.velocity_engineer import VelocityFeatureEngineer
from usfds_core.services.preprocessing.feature_engineering_service import FeatureEngineeringExecutionService
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


class TestFeatureEngineeringExecutionService(unittest.TestCase):
    def setUp(self):
        self.storage = InMemoryStorage()
        self.service = FeatureEngineeringExecutionService(self.storage)
        self.parent_artifact = DatasetArtifact(
            dataset_id=uuid4(),
            storage_path="datasets/mapped/mapped_dataset.parquet",
            pipeline_stage=PipelineStage.MAPPED,
        )

        # Mapped dataset with system canonical columns
        self.mapped_df = pd.DataFrame({
            SystemColumn.EVENT_ID.value: [f"tx_{i}" for i in range(10)],
            SystemColumn.TIMESTAMP.value: [
                "2024-01-01 10:00:00",
                "2024-01-01 10:30:00",
                "2024-01-01 11:00:00",
                "2024-01-01 11:30:00",
                "2024-01-01 12:00:00",
                "2024-01-01 12:30:00",
                "2024-01-01 13:00:00",
                "2024-01-01 13:30:00",
                "2024-01-01 14:00:00",
                "2024-01-01 14:30:00",
            ],
            SystemColumn.AMOUNT.value: [100.0, 150.0, 200.0, 50.0, 300.0, 80.0, 120.0, 400.0, 250.0, 500.0],
            SystemColumn.USER_ID.value: ["u1", "u1", "u2", "u1", "u2", "u3", "u1", "u2", "u1", "u2"],
            "v1": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            SystemColumn.LABEL.value: [0, 0, 0, 0, 1, 0, 0, 1, 0, 1],
        })

        pq_buffer = io.BytesIO()
        self.mapped_df.to_parquet(pq_buffer, index=False)
        self.storage.save_bytes(self.parent_artifact.storage_path, pq_buffer.getvalue())

    def test_execute_feature_engineering_config(self):
        fe_config = FeatureEngineeringConfig(
            split=SplitConfig(
                time_column=SystemColumn.TIMESTAMP.value,
                target_column=SystemColumn.LABEL.value,
                test_size=0.2,
            ),
            cleansing=CleansingConfig(drop_duplicates=True),
            time_col=SystemColumn.TIMESTAMP.value,
            amount_col=SystemColumn.AMOUNT.value,
            user_id_col=SystemColumn.USER_ID.value,
            enable_amount_ratios=True,
            enable_hour_of_day=True,
            enable_velocity_features=True,
            velocity_windows=[1, 24],
        )

        result = self.service.execute(
            parent_artifact=self.parent_artifact,
            config=fe_config,
            user_name="ml_engineer",
        )

        self.assertIsInstance(result, DatasetArtifact)
        self.assertEqual(result.pipeline_stage, PipelineStage.FEATURE_ENGINEERED)
        self.assertEqual(result.parent_artifact_id, self.parent_artifact.artifact_id)
        self.assertEqual(result.dataset_id, self.parent_artifact.dataset_id)
        self.assertEqual(result.validation_status, ValidationStatus.PASSED)
        self.assertEqual(result.created_by, "ml_engineer")

        # Storage paths
        self.assertIn("train_enriched.parquet", result.storage_path)
        self.assertIsNotNone(result.test_storage_path)
        self.assertIn("test_enriched.parquet", result.test_storage_path)
        self.assertIn("fitted_feature_engineers.joblib", result.pipeline_artifact_path)
        self.assertTrue(self.storage.exists(result.storage_path))
        self.assertTrue(self.storage.exists(result.test_storage_path))
        self.assertTrue(self.storage.exists(result.pipeline_artifact_path))

        # Check train parquet content
        train_pq_bytes = self.storage.read_bytes(result.storage_path)
        train_df = pd.read_parquet(io.BytesIO(train_pq_bytes))

        # Check test parquet content
        test_pq_bytes = self.storage.read_bytes(result.test_storage_path)
        test_df = pd.read_parquet(io.BytesIO(test_pq_bytes))

        # Verify row counts (10 rows, test_size=0.2 -> 8 train, 2 test)
        self.assertEqual(len(train_df), 8)
        self.assertEqual(len(test_df), 2)
        self.assertEqual(result.row_count, 8)

        # Check canonical business columns are preserved intact
        for col in [SystemColumn.EVENT_ID.value, SystemColumn.TIMESTAMP.value, SystemColumn.AMOUNT.value, SystemColumn.USER_ID.value, SystemColumn.LABEL.value]:
            self.assertIn(col, train_df.columns)
            self.assertIn(col, test_df.columns)

        # Check engineered features
        expected_fe_cols = ["hour_of_day", "amount_to_mean_ratio", "tx_freq_last_1h", "tx_sum_last_1h", "tx_freq_last_24h", "tx_sum_last_24h"]
        for col in expected_fe_cols:
            self.assertIn(col, train_df.columns)
            self.assertIn(col, test_df.columns)

    def test_execute_with_preprocessing_config_sync(self):
        prep_config = PreprocessingConfig(
            cleansing=CleansingConfig(missing_value_strategy=MissingValueStrategy.MEDIAN),
            split=SplitConfig(time_column="timestamp", test_size=0.3),
        )

        result = self.service.execute(
            parent_artifact=self.parent_artifact,
            config=prep_config.feature_engineering,
        )

        self.assertEqual(result.pipeline_stage, PipelineStage.FEATURE_ENGINEERED)
        self.assertEqual(result.validation_status, ValidationStatus.PASSED)
        self.assertEqual(result.row_count, 7)
        self.assertEqual(result.validation_report["test_rows"], 3)

    def test_execute_with_invalid_config_type_raises_type_error(self):
        prep_config = PreprocessingConfig()
        with self.assertRaises(TypeError) as ctx:
            self.service.execute(
                parent_artifact=self.parent_artifact,
                config=prep_config,  # type: ignore
            )
        self.assertIn("expects FeatureEngineeringConfig", str(ctx.exception))

    def test_empty_dataset_handling(self):
        empty_artifact = DatasetArtifact(
            dataset_id=uuid4(),
            storage_path="datasets/empty.parquet",
            pipeline_stage=PipelineStage.MAPPED,
        )
        empty_df = pd.DataFrame()
        buf = io.BytesIO()
        empty_df.to_parquet(buf, index=False)
        self.storage.save_bytes(empty_artifact.storage_path, buf.getvalue())

        fe_config = FeatureEngineeringConfig()
        result = self.service.execute(empty_artifact, fe_config)

        self.assertEqual(result.validation_status, ValidationStatus.FAILED)
        self.assertIn("empty", result.validation_report["error"])


class TestVelocityFeatureEngineer(unittest.TestCase):
    def test_time_window_rolling_with_history(self):
        train_df = pd.DataFrame({
            "user_id": ["u1", "u1", "u2"],
            "timestamp": ["2024-01-01 10:00:00", "2024-01-01 10:30:00", "2024-01-01 10:15:00"],
            "amount": [100.0, 200.0, 50.0],
        })
        test_df = pd.DataFrame({
            "user_id": ["u1", "u2"],
            "timestamp": ["2024-01-01 10:45:00", "2024-01-01 12:00:00"],
            "amount": [300.0, 75.0],
        })

        engineer = VelocityFeatureEngineer(
            user_id_col="user_id",
            time_col="timestamp",
            amount_col="amount",
            windows=[1],
        )
        engineer.fit(train_df)

        # Transform train
        train_fe = engineer.transform(train_df)
        self.assertEqual(list(train_fe["tx_freq_last_1h"]), [1.0, 2.0, 1.0])
        self.assertEqual(list(train_fe["tx_sum_last_1h"]), [100.0, 300.0, 50.0])

        # Transform test with train history (10:45 for u1 is within 1h of 10:00 and 10:30)
        test_fe = engineer.transform(test_df)
        self.assertEqual(test_fe.loc[0, "tx_freq_last_1h"], 3.0)
        self.assertEqual(test_fe.loc[0, "tx_sum_last_1h"], 600.0)  # 100 + 200 + 300
        # 12:00 for u2 is > 1h after 10:15
        self.assertEqual(test_fe.loc[1, "tx_freq_last_1h"], 1.0)
        self.assertEqual(test_fe.loc[1, "tx_sum_last_1h"], 75.0)

    def test_numeric_seconds_and_column_aliases(self):
        df = pd.DataFrame({
            "CustomerId": ["c1", "c1", "c1"],
            "Time": [0, 1800, 7200],  # 0s, 30m, 2h
            "Amount": [10.0, 20.0, 30.0],
        })

        engineer = VelocityFeatureEngineer(
            user_id_col="user_id",  # should resolve to CustomerId
            time_col="timestamp",   # should resolve to Time
            amount_col="amount",    # should resolve to Amount
            windows=[1],
        )
        out = engineer.fit_transform(df)
        self.assertIn("tx_freq_last_1h", out.columns)
        self.assertIn("tx_sum_last_1h", out.columns)
        self.assertEqual(list(out["tx_freq_last_1h"]), [1.0, 2.0, 1.0])
        self.assertEqual(list(out["tx_sum_last_1h"]), [10.0, 30.0, 30.0])


if __name__ == "__main__":
    unittest.main()
