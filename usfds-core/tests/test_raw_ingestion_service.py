import hashlib
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
import pandas as pd

from usfds_core.domain.entities.enums import DataClassification, PipelineStage, ValidationStatus
from usfds_core.repositories.in_memory_repos import (
    InMemoryDatasetArtifactRepository,
    InMemoryDatasetRepository,
)
from usfds_core.services.data_management.ingestion import DatasetIngestionService
from usfds_core.storage.in_memory_storage import InMemoryFileStorage


class TestDatasetIngestionService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.storage = InMemoryFileStorage()
        self.dataset_repo = InMemoryDatasetRepository()
        self.artifact_repo = InMemoryDatasetArtifactRepository()
        self.service = DatasetIngestionService(
            file_storage=self.storage,
            artifact_repo=self.artifact_repo,
            dataset_repo=self.dataset_repo,
        )

        self.df_sample = pd.DataFrame({
            "transaction_id": ["tx_1", "tx_2", "tx_3", "tx_4", "tx_5"],
            "amount": [100.0, 250.5, None, 15.0, 89.9],
            "user_id": ["u_10", "u_20", "u_10", "u_30", "u_20"],
            "is_fraud": [0, 1, 0, 0, 0],
        })

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_import_dataset_csv_success(self):
        csv_file = self.base_path / "transactions.csv"
        self.df_sample.to_csv(csv_file, index=False)
        raw_bytes = csv_file.read_bytes()

        project_id = uuid4()
        user_id = uuid4()

        dataset, artifact = self.service.import_dataset(
            file_path=str(csv_file),
            dataset_name="transactions_2024",
            display_name="Transactions 2024",
            description="Transaction dataset for fraud detection",
            project_id=project_id,
            user_id=user_id,
            contains_pii=True,
            data_classification=DataClassification.CONFIDENTIAL,
            user_name="data_scientist",
        )

        # 1. Verify Dataset Entity
        self.assertIsNotNone(dataset.dataset_id)
        self.assertEqual(dataset.dataset_name, "transactions_2024")
        self.assertEqual(dataset.display_name, "Transactions 2024")
        self.assertEqual(dataset.project_id, project_id)
        self.assertEqual(dataset.user_id, user_id)
        self.assertTrue(dataset.contains_pii)
        self.assertEqual(dataset.data_classification, DataClassification.CONFIDENTIAL)

        # 2. Verify RAW DatasetArtifact
        self.assertIsNotNone(artifact.artifact_id)
        self.assertEqual(artifact.dataset_id, dataset.dataset_id)
        self.assertIsNone(artifact.parent_artifact_id)
        self.assertEqual(artifact.pipeline_stage, PipelineStage.RAW)
        self.assertEqual(artifact.change_type, "RAW_INGESTION")
        self.assertEqual(artifact.row_count, 5)
        self.assertEqual(artifact.column_count, 4)
        self.assertEqual(artifact.created_by, "data_scientist")
        self.assertEqual(artifact.validation_status, ValidationStatus.PASSED)

        # Verify Checksum
        expected_checksum = hashlib.sha256(raw_bytes).hexdigest()
        self.assertEqual(artifact.checksum_sha256, expected_checksum)

        # Verify data profiling
        self.assertIn("profiling", artifact.validation_report)
        profiling = artifact.validation_report["profiling"]
        self.assertEqual(profiling["row_count"], 5)
        self.assertEqual(profiling["field_count"], 4)
        self.assertEqual(
            profiling["field_names"], ["transaction_id", "amount", "user_id", "is_fraud"]
        )

        # Amount column: 1 null out of 5 rows = 20.0%
        amount_field = next(f for f in profiling["fields"] if f["name"] == "amount")
        self.assertEqual(amount_field["null_count"], 1)
        self.assertEqual(amount_field["null_percentage"], 20.0)
        self.assertEqual(amount_field["unique_count"], 4)

        # 3. Verify Persistence in Repositories
        persisted_ds = self.dataset_repo.get_by_id(dataset.dataset_id)
        self.assertIsNotNone(persisted_ds)
        self.assertEqual(persisted_ds.dataset_id, dataset.dataset_id)

        persisted_art = self.artifact_repo.get_by_id(artifact.artifact_id)
        self.assertIsNotNone(persisted_art)
        self.assertEqual(persisted_art.artifact_id, artifact.artifact_id)

    def test_import_dataset_parquet_success(self):
        pq_file = self.base_path / "transactions.parquet"
        self.df_sample.to_parquet(pq_file, index=False)

        dataset, artifact = self.service.import_dataset(
            file_path=str(pq_file),
            dataset_name="parquet_data",
        )

        self.assertEqual(dataset.dataset_name, "parquet_data")
        self.assertEqual(artifact.pipeline_stage, PipelineStage.RAW)
        self.assertEqual(artifact.row_count, 5)
        self.assertEqual(artifact.column_count, 4)
        self.assertIn("profiling", artifact.validation_report)

    def test_import_missing_file_raises_error(self):
        with self.assertRaises(FileNotFoundError):
            self.service.import_dataset(
                file_path=str(self.base_path / "nonexistent.csv")
            )

    def test_import_unsupported_extension_raises_error(self):
        invalid_file = self.base_path / "data.xlsx"
        invalid_file.write_text("dummy")

        with self.assertRaises(ValueError) as ctx:
            self.service.import_dataset(file_path=str(invalid_file))
        self.assertIn("không được hỗ trợ", str(ctx.exception))

    def test_import_empty_file_raises_error(self):
        empty_file = self.base_path / "empty.csv"
        empty_file.write_bytes(b"")

        with self.assertRaises(ValueError) as ctx:
            self.service.import_dataset(file_path=str(empty_file))
        self.assertIn("rỗng", str(ctx.exception).lower())

    def test_import_corrupt_file_raises_error(self):
        corrupt_file = self.base_path / "corrupt.parquet"
        corrupt_file.write_bytes(b"invalid_parquet_stream_bytes")

        with self.assertRaises(ValueError) as ctx:
            self.service.import_dataset(file_path=str(corrupt_file))
        self.assertIn("failed to parse", str(ctx.exception).lower())

    def test_import_file_exceeds_max_size_raises_error(self):
        file = self.base_path / "oversize.csv"
        file.write_bytes(b"1234567890" * 10)  # 100 bytes

        with self.assertRaises(ValueError) as ctx:
            self.service.import_dataset(
                file_path=str(file),
                max_file_size=50,  # limit to 50 bytes
            )
        self.assertIn("vượt quá dung lượng", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
