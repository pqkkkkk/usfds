import hashlib
import io
import unittest
from uuid import uuid4
import pandas as pd

from usfds_core.domain.entities.enums import PipelineStage, ValidationStatus
from usfds_core.repositories.in_memory_repos import InMemoryDatasetArtifactRepository
from usfds_core.services.eda.raw_ingestion_service import RawDatasetIngestionService
from usfds_core.storage.in_memory_storage import InMemoryFileStorage


class TestRawDatasetIngestionService(unittest.TestCase):
    def setUp(self):
        self.storage = InMemoryFileStorage()
        self.artifact_repo = InMemoryDatasetArtifactRepository()
        self.service = RawDatasetIngestionService(
            file_storage=self.storage,
            artifact_repo=self.artifact_repo,
        )
        self.dataset_id = uuid4()

        self.df_sample = pd.DataFrame({
            "transaction_id": ["tx_1", "tx_2", "tx_3", "tx_4", "tx_5"],
            "amount": [100.0, 250.5, None, 15.0, 89.9],
            "user_id": ["u_10", "u_20", "u_10", "u_30", "u_20"],
            "is_fraud": [0, 1, 0, 0, 0],
        })

    def test_presigned_url_flow_csv_ingestion(self):
        # 1. Simulate client uploading CSV to storage via presigned URL
        csv_buffer = io.StringIO()
        self.df_sample.to_csv(csv_buffer, index=False)
        csv_bytes = csv_buffer.getvalue().encode("utf-8")
        storage_path = f"datasets/{self.dataset_id}/raw/transactions.csv"
        self.storage.save_bytes(storage_path, csv_bytes)

        # 2. Client sends storage_path to server to ingest & perform EDA
        artifact = self.service.ingest_raw_dataset(
            dataset_id=self.dataset_id,
            storage_path=storage_path,
            user_name="data_scientist",
        )

        # 3. Assertions on DatasetArtifact
        self.assertIsNotNone(artifact.artifact_id)
        self.assertEqual(artifact.dataset_id, self.dataset_id)
        self.assertIsNone(artifact.parent_artifact_id)
        self.assertEqual(artifact.pipeline_stage, PipelineStage.RAW)
        self.assertEqual(artifact.change_type, "RAW_INGESTION")
        self.assertEqual(artifact.storage_path, storage_path)
        self.assertEqual(artifact.output_paths, {"raw": storage_path})
        self.assertEqual(artifact.row_count, 5)
        self.assertEqual(artifact.column_count, 4)
        self.assertEqual(artifact.created_by, "data_scientist")
        self.assertEqual(artifact.validation_status, ValidationStatus.PASSED)

        # Verify Checksum
        expected_checksum = hashlib.sha256(csv_bytes).hexdigest()
        self.assertEqual(artifact.checksum_sha256, expected_checksum)

        # Verify EDA in validation_report
        self.assertIn("eda", artifact.validation_report)
        eda = artifact.validation_report["eda"]
        self.assertEqual(eda["row_count"], 5)
        self.assertEqual(eda["field_count"], 4)
        self.assertEqual(
            eda["field_names"], ["transaction_id", "amount", "user_id", "is_fraud"]
        )

        # Verify amount field EDA: 1 null out of 5 rows = 20.0%
        amount_field = next(f for f in eda["fields"] if f["name"] == "amount")
        self.assertEqual(amount_field["null_count"], 1)
        self.assertEqual(amount_field["null_percentage"], 20.0)
        self.assertEqual(amount_field["unique_count"], 4)

        # Verify artifact is persisted in repository
        persisted = self.artifact_repo.get_by_id(artifact.artifact_id)
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.artifact_id, artifact.artifact_id)

    def test_direct_upload_and_ingest_helper(self):
        csv_buffer = io.StringIO()
        self.df_sample.to_csv(csv_buffer, index=False)
        csv_bytes = csv_buffer.getvalue().encode("utf-8")

        artifact = self.service.upload_and_ingest_raw_dataset(
            dataset_id=self.dataset_id,
            file_name="credit_card.csv",
            file_bytes=csv_bytes,
            user_name="admin",
        )

        self.assertEqual(artifact.pipeline_stage, PipelineStage.RAW)
        self.assertTrue(self.storage.exists(artifact.output_paths["raw"]))
        self.assertEqual(artifact.row_count, 5)

    def test_parquet_ingestion(self):
        pq_buffer = io.BytesIO()
        self.df_sample.to_parquet(pq_buffer, index=False)
        pq_bytes = pq_buffer.getvalue()

        storage_path = f"datasets/{self.dataset_id}/raw/transactions.parquet"
        self.storage.save_bytes(storage_path, pq_bytes)

        artifact = self.service.ingest_raw_dataset(
            dataset_id=self.dataset_id,
            storage_path=storage_path,
        )

        self.assertEqual(artifact.pipeline_stage, PipelineStage.RAW)
        self.assertEqual(artifact.row_count, 5)
        self.assertEqual(artifact.column_count, 4)
        self.assertIn("eda", artifact.validation_report)

    def test_missing_file_in_storage(self):
        with self.assertRaises(FileNotFoundError):
            self.service.ingest_raw_dataset(
                dataset_id=self.dataset_id,
                storage_path="datasets/nonexistent/file.csv",
            )

    def test_empty_file_bytes(self):
        storage_path = f"datasets/{self.dataset_id}/raw/empty.csv"
        self.storage.save_bytes(storage_path, b"")

        with self.assertRaises(ValueError) as ctx:
            self.service.ingest_raw_dataset(
                dataset_id=self.dataset_id,
                storage_path=storage_path,
            )
        self.assertIn("empty", str(ctx.exception).lower())

    def test_corrupt_file_bytes(self):
        storage_path = f"datasets/{self.dataset_id}/raw/corrupt.parquet"
        self.storage.save_bytes(storage_path, b"not_a_valid_parquet_stream")

        with self.assertRaises(ValueError) as ctx:
            self.service.ingest_raw_dataset(
                dataset_id=self.dataset_id,
                storage_path=storage_path,
            )
        self.assertIn("failed to parse", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
