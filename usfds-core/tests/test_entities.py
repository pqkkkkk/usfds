from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import unittest
from uuid import UUID, uuid4

from usfds_core.domain.entities import (
    DataClassification,
    Dataset,
    DatasetArtifact,
    DatasetRole,
    Deployment,
    DeploymentEnvironment,
    DeploymentStatus,
    Model,
    ModelVersion,
    ModelVersionStatus,
    PipelineStage,
    Project,
    RiskLevel,
    Rule,
    RuleType,
    RunDataset,
    TrainingRun,
    TrainingRunStatus,
    User,
    ValidationStatus,
)


class TestDomainEnums(unittest.TestCase):
    def test_pipeline_stage_values(self):
        expected_stages = {"RAW", "MAPPED", "FEATURE_ENGINEERED", "PRE_PROCESSED"}
        actual_stages = {stage.value for stage in PipelineStage}
        self.assertEqual(actual_stages, expected_stages)
        self.assertEqual(PipelineStage.RAW, "RAW")
        self.assertEqual(PipelineStage.MAPPED, "MAPPED")
        self.assertEqual(PipelineStage.FEATURE_ENGINEERED, "FEATURE_ENGINEERED")
        self.assertEqual(PipelineStage.PRE_PROCESSED, "PRE_PROCESSED")

    def test_other_enums(self):
        self.assertEqual(DatasetRole.TRAIN, "TRAIN")
        self.assertEqual(ValidationStatus.PASSED, "PASSED")
        self.assertEqual(DataClassification.CONFIDENTIAL, "CONFIDENTIAL")
        self.assertEqual(RiskLevel.HIGH, "HIGH")
        self.assertEqual(RuleType.THRESHOLD, "THRESHOLD")
        self.assertEqual(TrainingRunStatus.COMPLETED, "COMPLETED")
        self.assertEqual(ModelVersionStatus.APPROVED, "APPROVED")
        self.assertEqual(DeploymentStatus.RUNNING, "RUNNING")
        self.assertEqual(DeploymentEnvironment.PRODUCTION, "PRODUCTION")


class TestSystemEntities(unittest.TestCase):
    def test_user_defaults_and_custom(self):
        user = User(username="admin", email="admin@example.com")
        self.assertTrue(is_dataclass(user))
        self.assertIsInstance(user.user_id, UUID)
        self.assertIsInstance(user.created_at, datetime)
        self.assertEqual(user.username, "admin")
        self.assertEqual(user.email, "admin@example.com")

        custom_id = uuid4()
        custom_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        user2 = User(username="analyst", email="analyst@example.com", user_id=custom_id, created_at=custom_time)
        self.assertEqual(user2.user_id, custom_id)
        self.assertEqual(user2.created_at, custom_time)

    def test_project_defaults_and_custom(self):
        user_id = uuid4()
        project = Project(project_name="Credit Card Fraud 2026", user_id=user_id)
        self.assertTrue(is_dataclass(project))
        self.assertIsInstance(project.project_id, UUID)
        self.assertIsNone(project.description)
        self.assertIsNone(project.base_dataset_id)
        self.assertEqual(project.user_id, user_id)

        dataset_id = uuid4()
        project2 = Project(
            project_name="AML Detection",
            user_id=user_id,
            description="Anti Money Laundering",
            base_dataset_id=dataset_id,
        )
        self.assertEqual(project2.description, "Anti Money Laundering")
        self.assertEqual(project2.base_dataset_id, dataset_id)


class TestDatasetEntities(unittest.TestCase):
    def test_dataset_defaults_and_custom(self):
        user_id = uuid4()
        project_id = uuid4()
        dataset = Dataset(dataset_name="cc_tx_2026.csv", user_id=user_id, project_id=project_id)
        self.assertTrue(is_dataclass(dataset))
        self.assertIsInstance(dataset.dataset_id, UUID)
        self.assertFalse(dataset.contains_pii)
        self.assertIsNone(dataset.data_classification)
        self.assertIsNone(dataset.updated_at)

        dataset2 = Dataset(
            dataset_name="cc_tx_2026.csv",
            user_id=user_id,
            project_id=project_id,
            display_name="Credit Card Transactions",
            contains_pii=True,
            data_classification=DataClassification.CONFIDENTIAL,
        )
        self.assertTrue(dataset2.contains_pii)
        self.assertEqual(dataset2.data_classification, DataClassification.CONFIDENTIAL)

    def test_dataset_artifact_lineage_and_defaults(self):
        dataset_id = uuid4()
        artifact1 = DatasetArtifact(
            dataset_id=dataset_id,
            storage_path="s3://fds-bucket/raw/cc_tx_2026.csv",
            pipeline_stage=PipelineStage.RAW,
            row_count=100000,
            column_count=30,
        )
        self.assertTrue(is_dataclass(artifact1))
        self.assertEqual(artifact1.pipeline_stage, PipelineStage.RAW)
        self.assertIsNone(artifact1.parent_artifact_id)

        artifact2 = DatasetArtifact(
            dataset_id=dataset_id,
            parent_artifact_id=artifact1.artifact_id,
            pipeline_stage=PipelineStage.PRE_PROCESSED,
            storage_path="s3://fds-bucket/processed/cc_tx_2026_preprocessed.parquet",
            checksum_sha256="abc123sha",
            validation_status=ValidationStatus.PASSED,
            validation_report={"missing_values_handled": 120, "outliers_removed": 15},
            row_count=99985,
            column_count=35,
        )
        self.assertEqual(artifact2.parent_artifact_id, artifact1.artifact_id)
        self.assertEqual(artifact2.pipeline_stage, PipelineStage.PRE_PROCESSED)
        self.assertEqual(artifact2.validation_status, ValidationStatus.PASSED)


class TestModelEntities(unittest.TestCase):
    def test_model_and_versions(self):
        user_id = uuid4()
        model = Model(
            model_name="xgboost_fraud_detector",
            user_id=user_id,
            risk_level=RiskLevel.HIGH,
            github_repo="https://github.com/org/fds-models",
        )
        self.assertTrue(is_dataclass(model))
        self.assertEqual(model.risk_level, RiskLevel.HIGH)

        version = ModelVersion(
            model_id=model.model_id,
            semver="1.0.0",
            artifact_uri="s3://fds-bucket/models/xgboost_1.0.0.joblib",
            artifact_size_mb=42.5,
            framework="xgboost",
            status=ModelVersionStatus.APPROVED,
            registered_by="lead_ds",
        )
        self.assertTrue(is_dataclass(version))
        self.assertEqual(version.status, ModelVersionStatus.APPROVED)
        self.assertEqual(version.artifact_size_mb, 42.5)

    def test_training_run_and_run_dataset(self):
        run = TrainingRun(
            run_name="xgb_experiment_v1",
            accuracy=0.9982,
            precision_score=0.9540,
            recall_score=0.9210,
            f1_score=0.9372,
            loss=0.0125,
            hyperparameters={"max_depth": 6, "learning_rate": 0.05, "n_estimators": 300},
            status=TrainingRunStatus.COMPLETED,
            duration_seconds=340,
        )
        self.assertTrue(is_dataclass(run))
        self.assertEqual(run.status, TrainingRunStatus.COMPLETED)
        self.assertEqual(run.accuracy, 0.9982)

        dataset_id = uuid4()
        run_dataset = RunDataset(
            run_id=run.run_id,
            dataset_id=dataset_id,
            dataset_role=DatasetRole.TRAIN,
            sample_count=80000,
            usage_percentage=80.0,
        )
        self.assertTrue(is_dataclass(run_dataset))
        self.assertEqual(run_dataset.dataset_role, DatasetRole.TRAIN)
        self.assertEqual(run_dataset.sample_count, 80000)


class TestDetectionEntities(unittest.TestCase):
    def test_deployment(self):
        version_id = uuid4()
        deployment = Deployment(
            version_id=version_id,
            deployment_name="prod-fraud-detector-v1",
            environment=DeploymentEnvironment.PRODUCTION,
            endpoint_url="https://api.usfds.internal/v1/predict",
            replicas=3,
            status=DeploymentStatus.RUNNING,
            traffic_percentage=100,
        )
        self.assertTrue(is_dataclass(deployment))
        self.assertEqual(deployment.environment, DeploymentEnvironment.PRODUCTION)
        self.assertEqual(deployment.replicas, 3)
        self.assertEqual(deployment.status, DeploymentStatus.RUNNING)

    def test_rule(self):
        project_id = uuid4()
        rule = Rule(
            project_id=project_id,
            rule_name="High Amount Cross Border Tx",
            rule_type=RuleType.THRESHOLD,
            rule_condition={"amount_gt": 10000, "is_cross_border": True},
            is_active=True,
        )
        self.assertTrue(is_dataclass(rule))
        self.assertEqual(rule.rule_type, RuleType.THRESHOLD)
        self.assertTrue(rule.is_active)
        self.assertEqual(rule.rule_condition["amount_gt"], 10000)


class TestEntitySerialization(unittest.TestCase):
    def test_asdict_serialization(self):
        user = User(username="test_user", email="test@example.com")
        d = asdict(user)
        self.assertIn("user_id", d)
        self.assertIn("username", d)
        self.assertIn("email", d)
        self.assertIn("created_at", d)
        self.assertEqual(d["username"], "test_user")


if __name__ == "__main__":
    unittest.main()
