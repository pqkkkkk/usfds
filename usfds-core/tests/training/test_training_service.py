import io
from pathlib import Path
import shutil
import tempfile
import unittest
from uuid import uuid4
import numpy as np
import pandas as pd

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.enums import (
    DatasetRole,
    ExecutionType,
    ModelVersionStatus,
    PipelineStage,
    TrainingRunStatus,
    ValidationStatus,
)
from usfds_core.domain.entities.model import Model
from usfds_core.domain.schemas.training_config import TrainingRunConfig
from usfds_core.domain.schemas.training_payload import TrainingRunPayload, TrainingRunResult
from usfds_core.repositories.in_memory_repos import (
    InMemoryDatasetArtifactRepository,
    InMemoryModelRepository,
    InMemoryModelVersionRepository,
    InMemoryTrainingRunRepository,
)
from usfds_core.storage.base_storage import IFileStorage
from usfds_core.services.training.dispatchers.local_dispatcher import SynchronousRunDispatcher
from usfds_core.services.training.executor import TrainingRunExecutor
from usfds_core.services.training.notifiers.base_notifier import CallbackResultNotifier
from usfds_core.services.training.training_service import TrainingOrchestrationService


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


class TestTrainingOrchestrationService(unittest.TestCase):
    def setUp(self):
        self.temp_workspace = Path(tempfile.mkdtemp())
        self.storage = InMemoryStorage()
        self.model_repo = InMemoryModelRepository()
        self.run_repo = InMemoryTrainingRunRepository()
        self.version_repo = InMemoryModelVersionRepository()
        self.artifact_repo = InMemoryDatasetArtifactRepository()

        # Seed Model
        self.model = Model(
            model_name="random_forest",
            user_id=uuid4(),
            execution_type=ExecutionType.BUILTIN,
            default_hyperparameters={"n_estimators": 10, "max_depth": 3},
        )
        self.model_repo.save(self.model)

        # Seed Dataset Parquet Files in Storage
        n_samples = 60
        df_train = pd.DataFrame({
            "f1": np.random.randn(n_samples),
            "f2": np.random.randn(n_samples),
            "is_fraud": np.random.choice([0, 1], size=n_samples, p=[0.8, 0.2]),
        })
        train_buf = io.BytesIO()
        df_train.to_parquet(train_buf, index=False)
        self.train_storage_path = f"datasets/train_{uuid4()}.parquet"
        self.storage.save_bytes(self.train_storage_path, train_buf.getvalue())

        # Seed Preprocessed DatasetArtifact
        self.artifact = DatasetArtifact(
            dataset_id=uuid4(),
            pipeline_stage=PipelineStage.PRE_PROCESSED,
            storage_path="datasets/mock_dir",
            output_paths={"train": self.train_storage_path},
            validation_status=ValidationStatus.PASSED,
            validation_report={"target_column": "is_fraud"},
            row_count=n_samples,
        )
        self.artifact_repo.save(self.artifact)

    def tearDown(self):
        shutil.rmtree(self.temp_workspace, ignore_errors=True)

    def test_validation_rejects_invalid_stage(self):
        self.artifact.pipeline_stage = PipelineStage.RAW
        self.artifact_repo.save(self.artifact)

        dispatcher = SynchronousRunDispatcher(executor_func=lambda p: None)
        service = TrainingOrchestrationService(
            dispatcher=dispatcher,
            training_run_repo=self.run_repo,
            model_version_repo=self.version_repo,
            model_repo=self.model_repo,
            dataset_artifact_repo=self.artifact_repo,
        )

        config = TrainingRunConfig(
            model_id=self.model.model_id,
            dataset_artifact_id=self.artifact.artifact_id,
        )

        with self.assertRaises(ValueError) as ctx:
            service.prepare_and_dispatch(config)
        self.assertIn("FEATURE_ENGINEERED or PRE_PROCESSED", str(ctx.exception))

    def test_validation_rejects_failed_status(self):
        self.artifact.validation_status = ValidationStatus.FAILED
        self.artifact_repo.save(self.artifact)

        dispatcher = SynchronousRunDispatcher(executor_func=lambda p: None)
        service = TrainingOrchestrationService(
            dispatcher=dispatcher,
            training_run_repo=self.run_repo,
            model_version_repo=self.version_repo,
            model_repo=self.model_repo,
            dataset_artifact_repo=self.artifact_repo,
        )

        config = TrainingRunConfig(
            model_id=self.model.model_id,
            dataset_artifact_id=self.artifact.artifact_id,
        )

        with self.assertRaises(ValueError) as ctx:
            service.prepare_and_dispatch(config)
        self.assertIn("validation status FAILED", str(ctx.exception))

    def test_end_to_end_training_lifecycle_and_semver(self):
        # Setup Service with Synchronous Dispatcher connected to TrainingRunExecutor
        executor = None
        service = None

        def run_worker(payload: TrainingRunPayload):
            executor.run(payload)

        dispatcher = SynchronousRunDispatcher(executor_func=run_worker)
        service = TrainingOrchestrationService(
            dispatcher=dispatcher,
            training_run_repo=self.run_repo,
            model_version_repo=self.version_repo,
            model_repo=self.model_repo,
            dataset_artifact_repo=self.artifact_repo,
            file_storage=self.storage,
        )

        notifier = CallbackResultNotifier(callback=service.handle_training_completion)
        executor = TrainingRunExecutor(
            file_storage=self.storage,
            notifier=notifier,
        )

        # Run 1: Should produce semver 1.0.0
        project_id = uuid4()
        config1 = TrainingRunConfig(
            model_id=self.model.model_id,
            dataset_artifact_id=self.artifact.artifact_id,
            project_id=project_id,
            hyperparameters={"n_estimators": 5},
            run_name="rf_experiment_1",
        )
        run1 = service.prepare_and_dispatch(config1)

        # Verify Run 1 completion
        updated_run1 = self.run_repo.get_by_id(run1.run_id)
        self.assertEqual(updated_run1.status, TrainingRunStatus.COMPLETED)
        self.assertEqual(updated_run1.project_id, project_id)
        self.assertIsNotNone(updated_run1.accuracy)
        self.assertIsNotNone(updated_run1.version_id)

        # Verify ModelVersion registered with v1
        version1 = self.version_repo.get_by_id(updated_run1.version_id)
        self.assertEqual(version1.semver, "v1")
        self.assertEqual(version1.project_id, project_id)
        self.assertEqual(version1.status, ModelVersionStatus.CANDIDATE)
        self.assertTrue(self.storage.exists(version1.artifact_uri))

        # Activate ModelVersion v1 (SUC-10)
        activated_v1 = service.activate_model_version(
            version1.version_id,
            decision_threshold=0.65,
            description="Production release",
        )
        self.assertEqual(activated_v1.status, ModelVersionStatus.APPROVED)
        self.assertEqual(activated_v1.decision_threshold, 0.65)
        self.assertEqual(activated_v1.description, "Production release")

        # Run 2: Should auto-increment version to v2
        config2 = TrainingRunConfig(
            model_id=self.model.model_id,
            dataset_artifact_id=self.artifact.artifact_id,
            project_id=project_id,
            run_name="rf_experiment_2",
        )
        run2 = service.prepare_and_dispatch(config2)
        updated_run2 = self.run_repo.get_by_id(run2.run_id)
        self.assertEqual(updated_run2.status, TrainingRunStatus.COMPLETED)

        version2 = self.version_repo.get_by_id(updated_run2.version_id)
        self.assertEqual(version2.semver, "v2")
        self.assertNotEqual(version1.version_id, version2.version_id)

        # Activating version2 keeps version1 APPROVED (independent activation)
        service.activate_model_version(version2.version_id, decision_threshold=0.55)
        self.assertEqual(
            self.version_repo.get_by_id(version1.version_id).status,
            ModelVersionStatus.APPROVED,
        )
        self.assertEqual(
            self.version_repo.get_by_id(version2.version_id).status,
            ModelVersionStatus.APPROVED,
        )

    def test_resolve_next_version_orders_numerically_not_lexically_or_by_timestamp(self):
        """ISS-010: latest version is chosen by numeric vN order, not registered_at or lexical order."""
        from datetime import datetime, timedelta, timezone
        from usfds_core.domain.entities.model import ModelVersion, TrainingRun
        from usfds_core.domain.schemas.training_payload import TrainingRunResult

        t_old = datetime(2026, 11, 1, tzinfo=timezone.utc)
        t_new = t_old + timedelta(hours=1)
        self.version_repo.save(
            ModelVersion(
                model_id=self.model.model_id,
                semver="v10",
                artifact_uri="models/v10.joblib",
                registered_at=t_old,
            )
        )
        self.version_repo.save(
            ModelVersion(
                model_id=self.model.model_id,
                semver="v2",
                artifact_uri="models/v2.joblib",
                registered_at=t_new,
            )
        )

        service = TrainingOrchestrationService(
            dispatcher=SynchronousRunDispatcher(executor_func=lambda p: None),
            training_run_repo=self.run_repo,
            model_version_repo=self.version_repo,
            model_repo=self.model_repo,
            dataset_artifact_repo=self.artifact_repo,
            file_storage=self.storage,
        )
        run = TrainingRun(model_id=self.model.model_id, run_name="run_after_v10")
        self.run_repo.save(run)

        completed = service.handle_training_completion(
            TrainingRunResult(
                run_id=run.run_id,
                is_success=True,
                artifact_uri="models/v11.joblib",
                metrics={"accuracy": 0.9},
            )
        )
        created = self.version_repo.get_by_id(completed.version_id)
        self.assertEqual(created.semver, "v11")

    def test_lineage_label_no_double_v_prefix(self):
        """ISS-010: lineage node label for semver='v1' is 'v1', not 'vv1'."""
        from usfds_core.domain.entities.model import ModelVersion

        version = ModelVersion(
            model_id=self.model.model_id,
            semver="v1",
            artifact_uri="models/v1.joblib",
        )
        self.version_repo.save(version)

        service = TrainingOrchestrationService(
            dispatcher=SynchronousRunDispatcher(executor_func=lambda p: None),
            training_run_repo=self.run_repo,
            model_version_repo=self.version_repo,
            model_repo=self.model_repo,
            dataset_artifact_repo=self.artifact_repo,
            file_storage=self.storage,
        )
        lineage = service.get_model_version_lineage(version.version_id)
        mv_nodes = [n for n in lineage.nodes if n.node_type == "MODEL_VERSION"]
        self.assertEqual(len(mv_nodes), 1)
        self.assertEqual(mv_nodes[0].label, "v1")

    def test_builtin_model_versions_increment_independently_per_project(self):
        """ISS-010: BUILTIN models (project_id=None) version independently per project and list_model_versions filters by project."""
        from usfds_core.domain.entities.enums import ExecutionType
        from usfds_core.domain.entities.model import Model, TrainingRun
        from usfds_core.domain.schemas.training_payload import TrainingRunResult

        builtin_model = Model(
            model_id=uuid4(),
            project_id=None,
            user_id=uuid4(),
            model_name="random_forest",
            execution_type=ExecutionType.BUILTIN,
        )
        self.model_repo.save(builtin_model)

        project_a = uuid4()
        project_b = uuid4()

        service = TrainingOrchestrationService(
            dispatcher=SynchronousRunDispatcher(executor_func=lambda p: None),
            training_run_repo=self.run_repo,
            model_version_repo=self.version_repo,
            model_repo=self.model_repo,
            dataset_artifact_repo=self.artifact_repo,
            file_storage=self.storage,
        )

        run_a1 = TrainingRun(project_id=project_a, model_id=builtin_model.model_id, run_name="run_a1")
        run_b1 = TrainingRun(project_id=project_b, model_id=builtin_model.model_id, run_name="run_b1")
        self.run_repo.save(run_a1)
        self.run_repo.save(run_b1)

        completed_a1 = service.handle_training_completion(
            TrainingRunResult(run_id=run_a1.run_id, is_success=True, artifact_uri="models/a1.joblib")
        )
        completed_b1 = service.handle_training_completion(
            TrainingRunResult(run_id=run_b1.run_id, is_success=True, artifact_uri="models/b1.joblib")
        )

        ver_a1 = self.version_repo.get_by_id(completed_a1.version_id)
        ver_b1 = self.version_repo.get_by_id(completed_b1.version_id)
        self.assertEqual(ver_a1.semver, "v1")
        self.assertEqual(ver_b1.semver, "v1")
        self.assertEqual(ver_a1.project_id, project_a)
        self.assertEqual(ver_b1.project_id, project_b)

        versions_a = service.list_model_versions(builtin_model.model_id, project_id=project_a)
        versions_b = service.list_model_versions(builtin_model.model_id, project_id=project_b)
        self.assertEqual([v.version_id for v in versions_a], [ver_a1.version_id])
        self.assertEqual([v.version_id for v in versions_b], [ver_b1.version_id])


if __name__ == "__main__":
    unittest.main()
