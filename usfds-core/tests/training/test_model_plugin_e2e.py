"""End-to-End Tests for the USFDS Model Plugin Architecture:
1. Upload & 2-Stage Validation (Static AST + Dynamic Dry-Run) for LR (Parquet) and SVM (CSV) in `custom-models/`.
2. Model Plugin Registration (`ModelPluginRegistrationService`).
3. Training on real `FEATURE_ENGINEERED` dataset artifacts (`storage_output/datasets/bf842480-4581-4cf2-bccc-fc2f540ddfce/artifacts/f4b0bb1a-b7a4-4f5e-b856-78cd5054d49f`).
4. Self-contained `model_bundle.zip` packaging (src + model.joblib + preprocessor.joblib).
5. Online & Batch Fraud Detection Inference (`InferenceService` & `BatchInferenceExecutor`) using trained plugin versions.
"""

import io
from pathlib import Path
import shutil
import tempfile
import unittest
from uuid import UUID, uuid4
import zipfile
import pandas as pd

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.detection import Deployment, Pipeline
from usfds_core.domain.entities.enums import (
    DeploymentEnvironment,
    DeploymentStatus,
    DetectionJobStatus,
    ExecutionType,
    PipelineStage,
    TrainingRunStatus,
    ValidationStatus,
)
from usfds_core.domain.entities.model import Model
from usfds_core.domain.schemas.training_config import TrainingRunConfig
from usfds_core.domain.schemas.training_payload import TrainingRunPayload
from usfds_core.repositories.in_memory_repos import (
    InMemoryDatasetArtifactRepository,
    InMemoryDetectionJobRepository,
    InMemoryModelRepository,
    InMemoryModelVersionRepository,
    InMemoryPipelineRepository,
    InMemoryTrainingRunRepository,
)
from usfds_core.services.inference.inference_service import InferenceService
from usfds_core.services.training.dispatchers.local_dispatcher import SynchronousRunDispatcher
from usfds_core.services.training.executor import TrainingRunExecutor
from usfds_core.services.training.notifiers.base_notifier import CallbackResultNotifier
from usfds_core.services.training.plugins import (
    ModelPluginRegistrationService,
    ModelPluginValidator,
    package_directory_to_zip_bytes,
)
from usfds_core.services.training.training_service import TrainingOrchestrationService
from usfds_core.storage.in_memory_storage import InMemoryFileStorage


class TestModelPluginEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).resolve().parent.parent.parent.parent
        cls.custom_models_dir = cls.repo_root / "custom-models"
        cls.lr_plugin_dir = cls.custom_models_dir / "logistic_regression"
        cls.svm_plugin_dir = cls.custom_models_dir / "svm"

        cls.fe_artifact_dir = (
            cls.repo_root
            / "storage_output"
            / "datasets"
            / "bf842480-4581-4cf2-bccc-fc2f540ddfce"
            / "artifacts"
            / "f4b0bb1a-b7a4-4f5e-b856-78cd5054d49f"
        )
        cls.real_train_pq = cls.fe_artifact_dir / "train_enriched.parquet"
        cls.real_test_pq = cls.fe_artifact_dir / "test_enriched.parquet"
        cls.real_fe_joblib = cls.fe_artifact_dir / "fitted_feature_engineers.joblib"

        if not cls.real_train_pq.exists() or not cls.real_test_pq.exists():
            raise unittest.SkipTest(f"Real FEATURE_ENGINEERED dataset not found at {cls.fe_artifact_dir}")

        # Load a stratified 2,000-row slice of the real FEATURE_ENGINEERED dataset for fast E2E test execution
        df_train_full = pd.read_parquet(cls.real_train_pq)
        df_test_full = pd.read_parquet(cls.real_test_pq)

        cls.df_train_sample = pd.concat([
            df_train_full[df_train_full["label"] == 0].head(1600),
            df_train_full[df_train_full["label"] == 1].head(400),
        ]).sample(frac=1.0, random_state=42).reset_index(drop=True)

        cls.df_test_sample = pd.concat([
            df_test_full[df_test_full["label"] == 0].head(400),
            df_test_full[df_test_full["label"] == 1].head(100),
        ]).sample(frac=1.0, random_state=42).reset_index(drop=True)

    def setUp(self):
        self.storage = InMemoryFileStorage()
        self.model_repo = InMemoryModelRepository()
        self.run_repo = InMemoryTrainingRunRepository()
        self.version_repo = InMemoryModelVersionRepository()
        self.artifact_repo = InMemoryDatasetArtifactRepository()
        self.pipeline_repo = InMemoryPipelineRepository(use_storage_fallback=False)
        self.job_repo = InMemoryDetectionJobRepository()

        # Store sample of the real FEATURE_ENGINEERED dataset in storage
        train_buf = io.BytesIO()
        self.df_train_sample.to_parquet(train_buf, index=False)
        self.train_uri = (
            "datasets/bf842480-4581-4cf2-bccc-fc2f540ddfce/artifacts/"
            "f4b0bb1a-b7a4-4f5e-b856-78cd5054d49f/train_enriched.parquet"
        )
        self.storage.save_bytes(self.train_uri, train_buf.getvalue())

        test_buf = io.BytesIO()
        self.df_test_sample.to_parquet(test_buf, index=False)
        self.test_uri = (
            "datasets/bf842480-4581-4cf2-bccc-fc2f540ddfce/artifacts/"
            "f4b0bb1a-b7a4-4f5e-b856-78cd5054d49f/test_enriched.parquet"
        )
        self.storage.save_bytes(self.test_uri, test_buf.getvalue())

        self.fe_joblib_uri = (
            "datasets/bf842480-4581-4cf2-bccc-fc2f540ddfce/artifacts/"
            "f4b0bb1a-b7a4-4f5e-b856-78cd5054d49f/fitted_feature_engineers.joblib"
        )
        if self.real_fe_joblib.exists():
            self.storage.save_bytes(self.fe_joblib_uri, self.real_fe_joblib.read_bytes())

        # Register the FEATURE_ENGINEERED DatasetArtifact
        self.fe_artifact = DatasetArtifact(
            artifact_id=UUID("f4b0bb1a-b7a4-4f5e-b856-78cd5054d49f"),
            dataset_id=UUID("bf842480-4581-4cf2-bccc-fc2f540ddfce"),
            pipeline_stage=PipelineStage.FEATURE_ENGINEERED,
            storage_path="datasets/bf842480-4581-4cf2-bccc-fc2f540ddfce/artifacts/f4b0bb1a-b7a4-4f5e-b856-78cd5054d49f",
            output_paths={
                "train": self.train_uri,
                "test": self.test_uri,
                "fitted_engineers": self.fe_joblib_uri,
            },
            validation_status=ValidationStatus.PASSED,
            validation_report={"target_column": "label"},
            row_count=len(self.df_train_sample),
        )
        self.artifact_repo.save(self.fe_artifact)

        # Wire up TrainingOrchestrationService + TrainingRunExecutor
        self.executor = None

        def dispatch_fn(payload: TrainingRunPayload):
            self.executor.run(payload)

        self.dispatcher = SynchronousRunDispatcher(executor_func=dispatch_fn)
        self.training_service = TrainingOrchestrationService(
            dispatcher=self.dispatcher,
            training_run_repo=self.run_repo,
            model_version_repo=self.version_repo,
            model_repo=self.model_repo,
            dataset_artifact_repo=self.artifact_repo,
            file_storage=self.storage,
        )
        self.executor = TrainingRunExecutor(
            file_storage=self.storage,
            notifier=CallbackResultNotifier(callback=self.training_service.handle_training_completion),
        )
        self.plugin_reg_service = ModelPluginRegistrationService(
            model_repo=self.model_repo,
            file_storage=self.storage,
        )

    def test_static_ast_rejects_forbidden_imports_and_missing_functions(self):
        bad_dir = Path(tempfile.mkdtemp())
        try:
            (bad_dir / "main.py").write_text(
                "import subprocess\nimport socket\ndef run_training(a, b, c, d, e):\n    eval('1+1')\n",
                encoding="utf-8",
            )
            validator = ModelPluginValidator()
            res = validator.validate(bad_dir)
            self.assertFalse(res.is_valid)
            self.assertFalse(res.static_check_passed)
            joined_errors = "\n".join(res.errors)
            self.assertIn("Forbidden module import 'subprocess'", joined_errors)
            self.assertIn("Forbidden module import 'socket'", joined_errors)
            self.assertIn("Forbidden builtin call 'eval()'", joined_errors)
            self.assertIn("run_inference", joined_errors)
        finally:
            shutil.rmtree(bad_dir, ignore_errors=True)

    def test_logistic_regression_plugin_full_lifecycle_parquet(self):
        """Test Upload -> Validate -> Register -> Train on FEATURE_ENGINEERED -> Batch & Online Inference for LR Plugin."""
        user_id = uuid4()
        model, val_res = self.plugin_reg_service.register_from_directory(
            plugin_dir=self.lr_plugin_dir,
            user_id=user_id,
        )
        self.assertTrue(val_res.is_valid, f"Validation failed: {val_res.errors}")
        self.assertTrue(val_res.static_check_passed)
        self.assertTrue(val_res.dry_run_train_passed)
        self.assertTrue(val_res.dry_run_inference_passed)
        self.assertIsNotNone(model)
        self.assertEqual(model.execution_type, ExecutionType.SCRIPT)
        self.assertIn("preprocessor.joblib", val_res.detected_artifacts)
        self.assertIn("model.joblib", val_res.detected_artifacts)

        # Train LR Plugin on real FEATURE_ENGINEERED dataset
        run_cfg = TrainingRunConfig(
            model_id=model.model_id,
            dataset_artifact_id=self.fe_artifact.artifact_id,
            hyperparameters={"C": 0.8, "max_iter": 100},
            run_name="lr_plugin_fe_run",
        )
        run = self.training_service.prepare_and_dispatch(run_cfg)
        completed_run = self.run_repo.get_by_id(run.run_id)
        self.assertEqual(completed_run.status, TrainingRunStatus.COMPLETED, completed_run.error_message)
        self.assertGreater(completed_run.accuracy, 0.5)
        self.assertIsNotNone(completed_run.f1_score)
        self.assertIsNotNone(completed_run.version_id)

        # Verify ModelVersion points to self-contained model_bundle.zip containing src + preprocessor + model
        version = self.version_repo.get_by_id(completed_run.version_id)
        self.assertTrue(version.artifact_uri.endswith("model_bundle.zip"))
        bundle_bytes = self.storage.read_bytes(version.artifact_uri)
        with zipfile.ZipFile(io.BytesIO(bundle_bytes), "r") as zf:
            names = zf.namelist()
            self.assertIn("src/main.py", names)
            self.assertIn("src/preprocessing.py", names)
            self.assertIn("artifacts/model.joblib", names)
            self.assertIn("artifacts/preprocessor.joblib", names)

        # Deploy and run Batch & Online Inference using the trained LR Plugin
        deployment_id = uuid4()
        deployment = Deployment(
            deployment_id=deployment_id,
            version_id=version.version_id,
            deployment_name="lr-plugin-prod",
            environment=DeploymentEnvironment.PRODUCTION,
            status=DeploymentStatus.RUNNING,
        )
        pipeline = Pipeline(
            feature_engineered_dataset_artifact=self.fe_artifact,
            model_version=version,
            deployment=deployment,
        )
        self.pipeline_repo.register_pipeline(deployment_id, pipeline)

        inf_service = InferenceService(
            pipeline_repo=self.pipeline_repo,
            file_storage=self.storage,
            detection_job_repo=self.job_repo,
        )

        # Online Inference on a single transaction event
        sample_event = self.df_test_sample.drop(columns=["label"]).iloc[0].to_dict()
        online_res = inf_service.online_inference(deployment_id, sample_event)
        self.assertIn(online_res["prediction"], [0, 1])
        self.assertGreaterEqual(online_res["probability"], 0.0)
        self.assertLessEqual(online_res["probability"], 1.0)

        # Batch Inference on test_enriched.parquet
        job = inf_service.batch_inference(
            project_id=uuid4(),
            deployment_id=deployment_id,
            input_path=self.test_uri,
            job_name="lr-plugin-batch-test",
        )
        completed_job = self.job_repo.get_by_id(job.job_id)
        self.assertEqual(completed_job.status, DetectionJobStatus.COMPLETED, completed_job.error_message)
        self.assertEqual(completed_job.total_records, len(self.df_test_sample))
        self.assertTrue(self.storage.exists(completed_job.output_path))

    def test_svm_plugin_full_lifecycle_csv_format(self):
        """Test Upload (via ZIP) -> Validate -> Train -> Inference for SVM Plugin using CSV data format."""
        zip_bytes = package_directory_to_zip_bytes(self.svm_plugin_dir)
        model, val_res = self.plugin_reg_service.register_from_zip(
            zip_bytes=zip_bytes,
            user_id=uuid4(),
        )
        self.assertTrue(val_res.is_valid, f"SVM validation failed: {val_res.errors}")
        self.assertEqual(val_res.manifest.data_format, "csv")

        # Train SVM Plugin on FEATURE_ENGINEERED dataset (auto-converted from Parquet to CSV by runner)
        run_cfg = TrainingRunConfig(
            model_id=model.model_id,
            dataset_artifact_id=self.fe_artifact.artifact_id,
            hyperparameters={"C": 0.5, "max_iter": 200},
            run_name="svm_plugin_csv_run",
        )
        run = self.training_service.prepare_and_dispatch(run_cfg)
        completed_run = self.run_repo.get_by_id(run.run_id)
        self.assertEqual(completed_run.status, TrainingRunStatus.COMPLETED, completed_run.error_message)
        self.assertGreater(completed_run.accuracy, 0.5)

        version = self.version_repo.get_by_id(completed_run.version_id)
        self.assertTrue(version.artifact_uri.endswith("model_bundle.zip"))

        # Deploy and run Batch Inference for SVM Plugin
        deployment_id = uuid4()
        pipeline = Pipeline(
            feature_engineered_dataset_artifact=self.fe_artifact,
            model_version=version,
            deployment=Deployment(
                deployment_id=deployment_id,
                version_id=version.version_id,
                deployment_name="svm-plugin-prod",
                environment=DeploymentEnvironment.PRODUCTION,
                status=DeploymentStatus.RUNNING,
            ),
        )
        self.pipeline_repo.register_pipeline(deployment_id, pipeline)

        inf_service = InferenceService(
            pipeline_repo=self.pipeline_repo,
            file_storage=self.storage,
            detection_job_repo=self.job_repo,
        )

        job = inf_service.batch_inference(
            project_id=uuid4(),
            deployment_id=deployment_id,
            input_path=self.test_uri,
            job_name="svm-plugin-batch-test",
        )
        completed_job = self.job_repo.get_by_id(job.job_id)
        self.assertEqual(completed_job.status, DetectionJobStatus.COMPLETED, completed_job.error_message)
        self.assertEqual(completed_job.total_records, len(self.df_test_sample))

    def test_builtin_random_forest_on_feature_engineered_dataset(self):
        """Verify that Built-in models also consume FEATURE_ENGINEERED directly and save preprocessor.joblib."""
        rf_model = Model(
            model_name="random_forest",
            user_id=uuid4(),
            execution_type=ExecutionType.BUILTIN,
            default_hyperparameters={"n_estimators": 15, "max_depth": 5},
        )
        self.model_repo.save(rf_model)

        run_cfg = TrainingRunConfig(
            model_id=rf_model.model_id,
            dataset_artifact_id=self.fe_artifact.artifact_id,
            run_name="builtin_rf_fe_run",
        )
        run = self.training_service.prepare_and_dispatch(run_cfg)
        completed_run = self.run_repo.get_by_id(run.run_id)
        self.assertEqual(completed_run.status, TrainingRunStatus.COMPLETED, completed_run.error_message)

        version = self.version_repo.get_by_id(completed_run.version_id)
        prep_uri = str(Path(version.artifact_uri).parent / "preprocessor.joblib").replace("\\", "/")
        self.assertTrue(self.storage.exists(prep_uri), "Built-in model must save companion preprocessor.joblib")

    def test_training_service_register_plugged_model(self):
        """Verify TrainingOrchestrationService.register_plugged_model from storage zip path and directory."""
        # 1. Save zip in file_storage and call register_plugged_model(model_artifact_path)
        zip_bytes = package_directory_to_zip_bytes(self.lr_plugin_dir)
        upload_uri = "uploads/lr_plugin.zip"
        self.storage.save_bytes(upload_uri, zip_bytes)

        registered_model = self.training_service.register_plugged_model(upload_uri)
        self.assertIsNotNone(registered_model)
        self.assertEqual(registered_model.execution_type, ExecutionType.SCRIPT)
        self.assertTrue(self.storage.exists(registered_model.entrypoint_uri))

        # 2. Non-existent path raises ValueError
        with self.assertRaises(ValueError) as ctx:
            self.training_service.register_plugged_model("uploads/does_not_exist.zip")
        self.assertIn("not found", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
