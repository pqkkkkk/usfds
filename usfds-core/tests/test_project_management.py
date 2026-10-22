from pathlib import Path
import shutil
import tempfile
import unittest
from uuid import uuid4
import pandas as pd

from usfds_core.domain.entities.detection import DetectionJob
from usfds_core.domain.entities.enums import (
    DetectionJobStatus,
    LogicalDataType,
    ProjectStatus,
    RuleAction,
    RuleStatus,
)
from usfds_core.repositories.in_memory_repos import (
    InMemoryDatasetArtifactRepository,
    InMemoryDatasetRepository,
    InMemoryDetectionJobRepository,
    InMemoryProjectRepository,
    InMemoryRuleRepository,
    InMemoryRuleVersionRepository,
)
from usfds_core.services.data_management.service import DataManagementService
from usfds_core.services.project_management import (
    ProjectManagementService,
    ProjectSchemaValidator,
)
from usfds_core.services.rule_engine.executor import RuleExecutor
from usfds_core.services.rule_engine.manager import RuleManager
from usfds_core.domain.schemas.rule_schemas import RuleExecutionContext
from usfds_infra.storage.local_storage import LocalFileStorage


class TestProjectManagementAndSchemaGovernance(unittest.TestCase):
    """Unit tests for ProjectManagementService and ProjectSchemaValidator (BR-PM-01 through BR-PM-08)."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="usfds_proj_test_")
        self.storage = LocalFileStorage(base_dir=self.temp_dir)
        self.project_repo = InMemoryProjectRepository()
        self.dataset_repo = InMemoryDatasetRepository()
        self.artifact_repo = InMemoryDatasetArtifactRepository()
        self.rule_repo = InMemoryRuleRepository()
        self.rule_version_repo = InMemoryRuleVersionRepository()
        self.job_repo = InMemoryDetectionJobRepository()

        self.project_service = ProjectManagementService(
            project_repo=self.project_repo,
            dataset_repo=self.dataset_repo,
            artifact_repo=self.artifact_repo,
            rule_repo=self.rule_repo,
            detection_job_repo=self.job_repo,
            file_storage=self.storage,
        )
        self.data_service = DataManagementService(
            dataset_repo=self.dataset_repo,
            artifact_repo=self.artifact_repo,
            file_storage=self.storage,
            project_repo=self.project_repo,
            project_service=self.project_service,
        )
        self.rule_manager = RuleManager(
            rule_repo=self.rule_repo,
            version_repo=self.rule_version_repo,
            project_repo=self.project_repo,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_csv(self, name: str, df: pd.DataFrame) -> Path:
        p = Path(self.temp_dir) / name
        df.to_csv(p, index=False)
        return p

    def test_schema_lock_on_first_upload_and_logical_type_validation(self):
        user_id = uuid4()
        project = self.project_service.create_project(
            project_name="Card Fraud Detection",
            user_id=user_id,
            description="Project for credit card fraud",
        )
        self.assertFalse(project.is_schema_locked)
        self.assertIsNone(project.raw_schema)

        # Duplicate project name for same user should fail (BR-PM-07)
        with self.assertRaises(ValueError):
            self.project_service.create_project(
                project_name="card fraud detection",
                user_id=user_id,
            )

        # 1. First Dataset Upload -> Locks RAW Schema (BR-PM-01)
        df1 = pd.DataFrame({
            "tx_id": ["T1", "T2", "T3"],
            "tx_amount": [100, 200, 300],        # int64 -> NUMERIC
            "merchant_cat": ["FOOD", "TECH", "FOOD"],  # object -> STRING
            "is_fraud": [0, 1, 0],               # int64 -> NUMERIC
        })
        csv1 = self._write_csv("ds1.csv", df1)
        ds1, _ = self.data_service.import_dataset(
            file_path=csv1,
            dataset_name="batch_jan",
            project_id=project.project_id,
            user_id=user_id,
        )

        updated_project = self.project_service.get_project(project.project_id)
        self.assertTrue(updated_project.is_schema_locked)
        self.assertEqual(updated_project.base_dataset_id, ds1.dataset_id)
        cols = updated_project.raw_schema["columns"]
        self.assertEqual(cols["tx_amount"]["logical_type"], LogicalDataType.NUMERIC.value)
        self.assertEqual(cols["merchant_cat"]["logical_type"], LogicalDataType.STRING.value)

        # 2. Second Dataset with float64 (due to NaN) and missing 'is_fraud' (unlabeled inference) -> Valid (BR-PM-02)
        df2 = pd.DataFrame({
            "tx_id": ["T4", "T5"],
            "tx_amount": [150.5, None],          # float64 with NaN -> compatible with NUMERIC
            "merchant_cat": ["TECH", "TRAVEL"],
            "extra_note": ["note1", "note2"],    # Extra column -> tolerated & stripped
        })
        csv2 = self._write_csv("ds2.csv", df2)
        ds2, art2 = self.data_service.import_dataset(
            file_path=csv2,
            dataset_name="inference_feb",
            project_id=project.project_id,
            user_id=user_id,
        )
        self.assertEqual(art2.column_count, 3)  # extra_note stripped

        # 3. Third Dataset with incompatible type (STRING in tx_amount) -> Rejected (BR-PM-02)
        df_bad = pd.DataFrame({
            "tx_id": ["T6", "T7"],
            "tx_amount": ["invalid_num", "bad_val"],
            "merchant_cat": ["TECH", "FOOD"],
            "is_fraud": [0, 0],
        })
        csv_bad = self._write_csv("ds_bad.csv", df_bad)
        with self.assertRaises(ValueError):
            self.data_service.import_dataset(
                file_path=csv_bad,
                dataset_name="bad_dataset",
                project_id=project.project_id,
                user_id=user_id,
            )

    def test_auto_unlock_schema_when_sole_dataset_deleted(self):
        project = self.project_service.create_project(
            project_name="Reset Test Project",
            user_id=uuid4(),
        )
        df1 = pd.DataFrame({
            "tx_id": ["T1", "T2"],
            "tx_amount": [10.0, 20.0],
            "is_fraud": [0, 1],
        })
        csv1 = self._write_csv("sole.csv", df1)
        ds1, _ = self.data_service.import_dataset(
            file_path=csv1,
            dataset_name="wrong_file",
            project_id=project.project_id,
        )
        self.assertTrue(self.project_service.get_project(project.project_id).is_schema_locked)

        # Deleting the only dataset automatically unlocks raw_schema (BR-PM-03)
        self.data_service.delete_dataset(ds1.dataset_id)
        unlocked_project = self.project_service.get_project(project.project_id)
        self.assertFalse(unlocked_project.is_schema_locked)
        self.assertIsNone(unlocked_project.raw_schema)
        self.assertIsNone(unlocked_project.base_dataset_id)

    def test_rule_validation_against_project_raw_schema(self):
        project = self.project_service.create_project(
            project_name="Rule Schema Project",
            user_id=uuid4(),
        )

        # Cannot create ACTIVE rule before project has RAW schema (BR-PM-04)
        with self.assertRaises(ValueError):
            self.rule_manager.create_rule(
                project_id=project.project_id,
                rule_code="R_EARLY",
                name="Early Rule",
                description="",
                condition={">": [{"var": "tx_amount"}, 1000]},
                action=RuleAction.REJECT,
                status=RuleStatus.ACTIVE,
            )

        # Lock schema via dataset upload
        df = pd.DataFrame({
            "tx_id": ["T1", "T2"],
            "tx_amount": [500.0, 1500.0],
            "channel": ["ONLINE", "POS"],
            "is_fraud": [0, 1],
        })
        csv_path = self._write_csv("rule_ds.csv", df)
        self.data_service.import_dataset(
            file_path=csv_path,
            dataset_name="rule_base_ds",
            project_id=project.project_id,
        )

        # Creating rule with unknown column fails (BR-PM-05)
        with self.assertRaises(ValueError):
            self.rule_manager.create_rule(
                project_id=project.project_id,
                rule_code="R_TYPO",
                name="Typo Column Rule",
                description="",
                condition={">": [{"var": "unknown_col"}, 1000]},
                action=RuleAction.REJECT,
            )

        # Creating rule with numeric '>' on STRING column 'channel' fails (BR-PM-05)
        with self.assertRaises(ValueError):
            self.rule_manager.create_rule(
                project_id=project.project_id,
                rule_code="R_BAD_OP",
                name="Bad Operator Rule",
                description="",
                condition={">": [{"var": "channel"}, 100]},
                action=RuleAction.REJECT,
            )

        # Creating rule with valid RAW columns succeeds and evaluates against raw_features
        rule, version = self.rule_manager.create_rule(
            project_id=project.project_id,
            rule_code="R_VALID_RAW",
            name="Valid Raw Rule",
            description="",
            condition={
                "and": [
                    {">": [{"var": "tx_amount"}, 1000]},
                    {"==": [{"var": "raw.channel"}, "ONLINE"]},
                ]
            },
            action=RuleAction.REJECT,
        )
        executor = RuleExecutor()
        res = executor.evaluate_rule(
            rule,
            version,
            RuleExecutionContext(
                transaction_id="T2",
                raw_features={"tx_amount": 1500.0, "channel": "ONLINE"},
            ),
        )
        self.assertTrue(res.is_triggered)

    def test_block_delete_project_with_running_job(self):
        project = self.project_service.create_project(
            project_name="Active Workload Project",
            user_id=uuid4(),
        )
        running_job = DetectionJob(
            project_id=project.project_id,
            deployment_id=uuid4(),
            input_path="dummy.csv",
            status=DetectionJobStatus.RUNNING,
        )
        self.job_repo.save(running_job)

        # Cannot archive or delete while job is RUNNING (BR-PM-08)
        with self.assertRaises(ValueError):
            self.project_service.update_project(
                project.project_id, status=ProjectStatus.ARCHIVED
            )
        with self.assertRaises(ValueError):
            self.project_service.delete_project(project.project_id)

        # Once job completes, deletion succeeds
        running_job.status = DetectionJobStatus.COMPLETED
        self.job_repo.save(running_job)
        self.assertTrue(self.project_service.delete_project(project.project_id))


if __name__ == "__main__":
    unittest.main()
