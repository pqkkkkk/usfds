import io
import unittest
from uuid import uuid4
import numpy as np
import pandas as pd

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.enums import PipelineStage, ValidationStatus
from usfds_core.domain.schemas.preprocessing_config import (
    DataMappingConfig,
    SupportedTimeFormat,
    SystemColumn,
)
from usfds_core.repositories.in_memory_repos import (
    InMemoryDatasetArtifactRepository,
    InMemoryDatasetRepository,
)
from usfds_core.services.data_management import (
    DatasetExportService,
    DataLineageService,
    DataQualityValidationService,
)
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


class TestDataQualityValidationService(unittest.TestCase):
    def setUp(self):
        self.validator = DataQualityValidationService()

    def test_perfect_dataset_quality_score(self):
        df = pd.DataFrame({
            SystemColumn.EVENT_ID.value: [f"tx_{i}" for i in range(100)],
            SystemColumn.TIMESTAMP.value: ["2024-01-01 10:00:00"] * 100,
            SystemColumn.AMOUNT.value: [50.0 + i for i in range(100)],
            SystemColumn.USER_ID.value: [f"user_{i % 10}" for i in range(100)],
            SystemColumn.LABEL.value: [0] * 95 + [1] * 5,
        })
        report = self.validator.validate(df)
        self.assertGreaterEqual(report.quality_score, 80.0)
        self.assertEqual(report.validation_status, ValidationStatus.PASSED)
        self.assertEqual(report.rating, "GOOD")
        self.assertEqual(len(report.critical_errors), 0)

    def test_critical_missing_in_mandatory_column(self):
        # > 50% missing in mandatory column triggers validation failure
        df = pd.DataFrame({
            SystemColumn.EVENT_ID.value: [f"tx_{i}" for i in range(10)],
            SystemColumn.TIMESTAMP.value: ["2024-01-01 10:00:00"] * 10,
            SystemColumn.AMOUNT.value: [None] * 6 + [100.0] * 4,  # 60% missing!
            SystemColumn.USER_ID.value: [f"user_{i}" for i in range(10)],
            SystemColumn.LABEL.value: [0] * 10,
        })
        report = self.validator.validate(df)
        self.assertEqual(report.validation_status, ValidationStatus.FAILED)
        self.assertEqual(report.rating, "POOR")
        self.assertGreater(len(report.critical_errors), 0)
        self.assertIn("vượt quá 50%", report.critical_errors[0])

    def test_duplicate_and_negative_amount_penalties(self):
        df = pd.DataFrame({
            SystemColumn.EVENT_ID.value: ["tx_1", "tx_1", "tx_2", "tx_3"],  # Duplicate ID
            SystemColumn.TIMESTAMP.value: ["2024-01-01 10:00:00"] * 4,
            SystemColumn.AMOUNT.value: [-10.0, 0.0, 100.0, 200.0],  # 2 non-positive amounts
            SystemColumn.USER_ID.value: ["u1", "u1", "u2", "u3"],
            SystemColumn.LABEL.value: [0, 0, 1, 0],
        })
        report = self.validator.validate(df)
        self.assertLess(report.quality_score, 80.0)
        self.assertEqual(report.duplicate_event_ids_count, 1)
        self.assertEqual(report.non_positive_amount_count, 2)
        self.assertGreater(len(report.warnings), 0)


class TestDataLineageAndExportServices(unittest.TestCase):
    def setUp(self):
        self.storage = InMemoryStorage()
        self.artifact_repo = InMemoryDatasetArtifactRepository()
        self.lineage_service = DataLineageService(self.artifact_repo)
        self.export_service = DatasetExportService(self.storage)

        self.dataset_id = uuid4()
        # Stage 1: RAW
        self.raw_art = DatasetArtifact(
            dataset_id=self.dataset_id,
            storage_path="raw.csv",
            output_paths={"raw": "raw.csv"},
            pipeline_stage=PipelineStage.RAW,
            row_count=100,
            column_count=5,
        )
        self.artifact_repo.save(self.raw_art)

        # Stage 2: MAPPED
        self.mapped_art = DatasetArtifact(
            dataset_id=self.dataset_id,
            parent_artifact_id=self.raw_art.artifact_id,
            storage_path="mapped.parquet",
            output_paths={"mapped": "mapped.parquet"},
            pipeline_stage=PipelineStage.MAPPED,
            change_type="DATA_MAPPING",
            row_count=100,
            column_count=5,
            validation_status=ValidationStatus.PASSED,
            validation_report={"quality_score": 95.0},
        )
        self.artifact_repo.save(self.mapped_art)

        # Save dummy parquet in storage
        df = pd.DataFrame({"event_id": ["1"], "amount": [10.0]})
        buf = io.BytesIO()
        df.to_parquet(buf, index=False)
        self.storage.save_bytes("mapped.parquet", buf.getvalue())

    def test_lineage_graph_dag_generation(self):
        graph = self.lineage_service.get_lineage(self.dataset_id)
        self.assertEqual(len(graph.nodes), 2)
        self.assertEqual(len(graph.edges), 1)
        self.assertEqual(graph.edges[0].source, str(self.raw_art.artifact_id))
        self.assertEqual(graph.edges[0].target, str(self.mapped_art.artifact_id))

    def test_export_artifact_bundle_as_zip(self):
        zip_bytes, filename = self.export_service.export_artifact_bundle(
            artifact=self.mapped_art,
            include_train=True,
            include_test=False,
            include_pipeline=False,
            include_schema=True,
        )
        self.assertGreater(len(zip_bytes), 0)
        self.assertTrue(filename.endswith(".zip"))


class TestDataManagementUnifiedService(unittest.TestCase):
    def setUp(self):
        import tempfile
        import shutil
        self.temp_dir = tempfile.mkdtemp(prefix="test_dm_svc_")
        self.storage = InMemoryStorage()
        self.dataset_repo = InMemoryDatasetRepository()
        self.artifact_repo = InMemoryDatasetArtifactRepository()

        from usfds_core.services.data_management.service import DataManagementService
        self.service = DataManagementService(
            dataset_repo=self.dataset_repo,
            artifact_repo=self.artifact_repo,
            file_storage=self.storage,
        )

    def tearDown(self):
        import shutil
        import os
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_end_to_end_facade_workflow(self):
        from pathlib import Path
        # 1. Create a raw CSV file on local disk
        csv_path = Path(self.temp_dir) / "transactions.csv"
        df = pd.DataFrame({
            "tx_id": [f"T{i}" for i in range(20)],
            "tx_time": ["2024-01-01 12:00:00"] * 20,
            "tx_amount": [10.0 + i for i in range(20)],
            "cust_id": [f"C{i % 4}" for i in range(20)],
            "fraud_flag": [0] * 18 + [1] * 2,
        })
        df.to_csv(csv_path, index=False)

        # 2. Import dataset (entry point creates Dataset + RAW artifact)
        dataset, raw_art = self.service.import_dataset(
            file_path=csv_path,
            dataset_name="demo_tx",
            display_name="Demo Transactions",
        )
        self.assertIsNotNone(dataset.dataset_id)
        self.assertEqual(raw_art.pipeline_stage, PipelineStage.RAW)
        self.assertEqual(raw_art.row_count, 20)
        self.assertEqual(raw_art.column_count, 5)

        # Verify dataset exists in repo and lineage is included
        ds_retrieved, arts, lineage_graph = self.service.get_dataset(dataset.dataset_id)
        self.assertEqual(len(arts), 1)
        self.assertEqual(len(lineage_graph.nodes), 1)

        # 3. Retrieve raw artifact via get_artifact (contains profiling)
        raw_art_retrieved = self.service.get_artifact(dataset.dataset_id, raw_art.artifact_id)
        self.assertEqual(raw_art_retrieved.row_count, 20)
        self.assertEqual(raw_art_retrieved.column_count, 5)
        self.assertIn("profiling", raw_art_retrieved.validation_report)

        # 4. Map Schema
        mapping_config = DataMappingConfig(
            event_id_column="tx_id",
            time_column="tx_time",
            amount_column="tx_amount",
            user_id_column="cust_id",
            target_column="fraud_flag",
        )
        mapped_art = self.service.map_schema(dataset.dataset_id, mapping_config)
        self.assertEqual(mapped_art.pipeline_stage, PipelineStage.MAPPED)
        self.assertIsNotNone(mapped_art.validation_report)

        # 5. Retrieve mapped artifact via get_artifact (contains data quality report)
        mapped_art_retrieved = self.service.get_artifact(dataset.dataset_id, mapped_art.artifact_id)
        self.assertGreaterEqual(mapped_art_retrieved.validation_report["quality_score"], 80.0)

        # 6. Lineage DAG
        lineage = self.service.get_lineage(dataset.dataset_id)
        self.assertEqual(len(lineage.nodes), 2)
        self.assertEqual(len(lineage.edges), 1)

        # 7. Export
        zip_bytes, zip_name = self.service.export_dataset(
            dataset_id=dataset.dataset_id,
            artifact_id=mapped_art.artifact_id,
        )
        self.assertGreater(len(zip_bytes), 0)
        self.assertTrue(zip_name.endswith(".zip"))

        # 8. Delete
        self.service.delete_dataset(dataset.dataset_id)
        with self.assertRaises(ValueError):
            self.service.get_dataset(dataset.dataset_id)


if __name__ == "__main__":
    unittest.main()
