import os
from pathlib import Path
import shutil
import tempfile
import unittest
from uuid import uuid4

from usfds_core.domain.entities.dataset import Dataset, DatasetArtifact
from usfds_core.domain.entities.enums import DataClassification, PipelineStage, ValidationStatus
from usfds_infra.database import (
    close_db,
    create_session_factory,
    create_sqlite_engine,
    init_db,
    session_scope,
    SqliteDatasetArtifactRepository,
    SqliteDatasetRepository,
)


class TestDatasetRepositories(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="usfds_repo_test_")
        self.db_path = Path(self.temp_dir) / "test_repo.db"
        self.engine = create_sqlite_engine(db_path=self.db_path)
        self.session_factory = create_session_factory(self.engine)
        init_db(self.engine)

    def tearDown(self):
        close_db(self.engine)
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dataset_repository_crud(self):
        with session_scope(self.session_factory) as session:
            repo = SqliteDatasetRepository(session)
            project_id = uuid4()
            user_id = uuid4()

            dataset = Dataset(
                dataset_name="fraud_raw",
                display_name="Fraud Raw Dataset",
                description="Test description",
                project_id=project_id,
                user_id=user_id,
                contains_pii=True,
                data_classification=DataClassification.CONFIDENTIAL,
            )
            saved = repo.save(dataset)
            self.assertEqual(saved.dataset_name, "fraud_raw")
            self.assertEqual(saved.data_classification, DataClassification.CONFIDENTIAL)

            # Retrieve
            retrieved = repo.get_by_id(dataset.dataset_id)
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.display_name, "Fraud Raw Dataset")

            # List by project
            proj_datasets = repo.list_by_project(project_id)
            self.assertEqual(len(proj_datasets), 1)

            # Search
            search_res = repo.list_all(search="fraud")
            self.assertEqual(len(search_res), 1)

            # Delete
            deleted = repo.delete(dataset.dataset_id)
            self.assertTrue(deleted)
            self.assertIsNone(repo.get_by_id(dataset.dataset_id))

    def test_artifact_repository(self):
        with session_scope(self.session_factory) as session:
            ds_repo = SqliteDatasetRepository(session)
            art_repo = SqliteDatasetArtifactRepository(session)

            project_id = uuid4()
            user_id = uuid4()
            dataset = ds_repo.save(Dataset(
                dataset_name="test_art_ds",
                project_id=project_id,
                user_id=user_id,
            ))

            raw_art = art_repo.save(DatasetArtifact(
                dataset_id=dataset.dataset_id,
                pipeline_stage=PipelineStage.RAW,
                storage_path="raw.csv",
                output_paths={"raw": "raw.csv"},
                row_count=500,
                column_count=10,
                validation_status=ValidationStatus.PASSED,
            ))
            self.assertEqual(raw_art.pipeline_stage, PipelineStage.RAW)

            # Save child MAPPED artifact
            mapped_art = art_repo.save(DatasetArtifact(
                dataset_id=dataset.dataset_id,
                parent_artifact_id=raw_art.artifact_id,
                pipeline_stage=PipelineStage.MAPPED,
                change_type="DATA_MAPPING",
                storage_path="mapped.parquet",
                output_paths={"mapped": "mapped.parquet"},
                row_count=500,
                column_count=6,
                validation_status=ValidationStatus.PASSED,
                validation_report={"quality_score": 92.5},
            ))

            # List artifacts
            artifacts = art_repo.list_by_dataset(dataset.dataset_id)
            self.assertEqual(len(artifacts), 2)


if __name__ == "__main__":
    unittest.main()
