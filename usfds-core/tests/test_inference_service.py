"""Comprehensive Unit & Integration Test Suite for USFDS Inference Service and Batch Executor."""

import io
from pathlib import Path
import time
import unittest
from uuid import UUID, uuid4
import pandas as pd

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.detection import Deployment, DetectionJob, Pipeline
from usfds_core.domain.entities.enums import (
    DeploymentEnvironment,
    DeploymentStatus,
    DetectionJobStatus,
    ModelVersionStatus,
    PipelineStage,
    RuleAction,
    RuleStatus,
    ValidationStatus,
)
from usfds_core.domain.entities.model import ModelVersion, RunDataset, TrainingRun
from usfds_core.domain.entities.system import Project
from usfds_core.services.project_management.schema_validator import ProjectSchemaValidator
from usfds_core.domain.schemas.inference_payload import BatchInferencePayload
from usfds_core.repositories.in_memory_repos import (
    InMemoryDatasetArtifactRepository,
    InMemoryDetectionJobRepository,
    InMemoryModelVersionRepository,
    InMemoryPipelineRepository,
    InMemoryProjectRepository,
    InMemoryRuleRepository,
    InMemoryTrainingRunRepository,
)
from usfds_core.services.inference.dispatchers.base_dispatcher import IBatchInferenceDispatcher
from usfds_core.services.inference.dispatchers.local_dispatcher import (
    LocalProcessBatchDispatcher,
    SynchronousBatchDispatcher,
)
from usfds_core.services.inference.executor import BatchInferenceExecutor
from usfds_core.services.inference.inference_service import InferenceService
from usfds_core.services.inference.workspace import InferenceWorkspace
from usfds_core.services.rule_engine.manager import RuleManager
from usfds_core.storage.base_storage import IFileStorage


class InMemoryStorage(IFileStorage):
    """In-memory dictionary-backed storage for fast unit tests."""

    def __init__(self):
        self.files = {}

    def save_bytes(self, file_path: str, data: bytes) -> str:
        self.files[file_path] = data
        return file_path

    def read_bytes(self, file_path: str) -> bytes:
        if file_path in self.files:
            return self.files[file_path]
        p = Path(file_path)
        if p.is_file():
            return p.read_bytes()
        raise FileNotFoundError(f"File {file_path} not found in in-memory storage")

    def exists(self, file_path: str) -> bool:
        return file_path in self.files or Path(file_path).is_file()


class DiskStorage(IFileStorage):
    """Disk storage resolving relative paths against a base directory or absolute paths."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        return p if p.is_absolute() else (self.base_dir / p).resolve()

    def save_bytes(self, file_path: str, data: bytes) -> str:
        target = self._resolve(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return str(target)

    def read_bytes(self, file_path: str) -> bytes:
        target = self._resolve(file_path)
        return target.read_bytes()

    def exists(self, file_path: str) -> bool:
        return self._resolve(file_path).is_file()


class TestInferenceWorkspace(unittest.TestCase):
    def test_workspace_lifecycle(self):
        workspace = InferenceWorkspace(inference_id=uuid4(), deployment_id=uuid4())
        self.assertFalse(workspace.run_dir.exists())

        workspace.initialize()
        self.assertTrue(workspace.artifacts_dir.exists())
        self.assertTrue(workspace.input_dir.exists())
        self.assertTrue(workspace.output_dir.exists())

        workspace.cleanup()
        self.assertFalse(workspace.run_dir.exists())


class TestHybridDetectionInMemory(unittest.TestCase):
    """Self-contained unit test suite for Hybrid Detection (SUC-15, SUC-16, SUC-19) using InMemoryStorage."""

    def test_hybrid_detection_options_and_investigation_dispatch(self):
        import tempfile
        project_id = uuid4()
        df = pd.DataFrame({
            "event_id": [f"tx_{i}" for i in range(10)],
            "user_id": [f"u_{i}" for i in range(10)],
            "amount": [50.0, 120.0, 600.0, 80.0, 750.0, 30.0, 220.0, 900.0, 40.0, 150.0],
            "country": ["US"] * 10,
        })
        locked_schema = ProjectSchemaValidator.extract_raw_schema(df).to_dict()

        project_repo = InMemoryProjectRepository()
        project_repo.save(
            Project(
                project_id=project_id,
                user_id=uuid4(),
                project_name="Unit Test Fraud Project",
                raw_schema=locked_schema,
            )
        )

        storage = InMemoryStorage()
        csv_buf = io.BytesIO()
        df.to_csv(csv_buf, index=False)
        raw_bytes = csv_buf.getvalue()

        raw_rel = f"datasets/{project_id}/raw.csv"
        storage.save_bytes(raw_rel, raw_bytes)

        artifact_repo = InMemoryDatasetArtifactRepository()
        raw_artifact_id = uuid4()
        mapped_artifact_id = uuid4()
        artifact_repo.save(
            DatasetArtifact(
                artifact_id=raw_artifact_id,
                dataset_id=uuid4(),
                pipeline_stage=PipelineStage.RAW,
                storage_path=raw_rel,
                output_paths={"raw": raw_rel},
                row_count=10,
                column_count=4,
                validation_status=ValidationStatus.PASSED,
            )
        )
        artifact_repo.save(
            DatasetArtifact(
                artifact_id=mapped_artifact_id,
                dataset_id=uuid4(),
                pipeline_stage=PipelineStage.MAPPED,
                storage_path=raw_rel,
                output_paths={"mapped": raw_rel},
                row_count=10,
                column_count=4,
                validation_status=ValidationStatus.PASSED,
            )
        )

        rule_repo = InMemoryRuleRepository()
        rule_manager = RuleManager(rule_repo=rule_repo, project_repo=project_repo)
        rule_manager.create_rule(
            project_id=project_id,
            rule_code="RL-BLOCK-500",
            name="Block Over 500",
            description="Block transactions over 500",
            condition={">": [{"var": "amount"}, 500.0]},
            action=RuleAction.REJECT,
            status=RuleStatus.ACTIVE,
        )
        rule_manager.create_rule(
            project_id=project_id,
            rule_code="RL-REVIEW-200",
            name="Review Over 200",
            description="Review transactions over 200",
            condition={">": [{"var": "amount"}, 200.0]},
            action=RuleAction.REVIEW,
            status=RuleStatus.ACTIVE,
        )

        job_repo = InMemoryDetectionJobRepository()

        service = InferenceService(
            file_storage=storage,
            detection_job_repo=job_repo,
            artifact_repo=artifact_repo,
            rule_manager=rule_manager,
            project_repo=project_repo,
        )

        # Reject non-RAW artifact in Option 1
        with self.assertRaises(ValueError) as ctx:
            service.start_detection_job(
                project_id=project_id,
                target_artifact_id=mapped_artifact_id,
                model_version_id=None,
                use_rules=True,
            )
        self.assertIn("must be at stage 'RAW'", str(ctx.exception))

        # Option 1: Start detection job on RAW DatasetArtifact
        job1 = service.start_detection_job(
            project_id=project_id,
            target_artifact_id=raw_artifact_id,
            model_version_id=None,
            use_rules=True,
            job_name="Unit-RAW-Artifact-Job",
        )
        self.assertEqual(job1.status, DetectionJobStatus.COMPLETED)
        self.assertEqual(job1.total_records, 10)
        self.assertEqual(job1.summary_metrics["reject_count"], 3)  # 600, 750, 900
        self.assertEqual(job1.summary_metrics["review_count"], 1)  # 220
        self.assertEqual(job1.summary_metrics["allow_count"], 6)

        # Option 2: Start detection job on direct file path
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(raw_bytes)
            tmp_path = tmp.name

        try:
            job2 = service.start_detection_job(
                project_id=project_id,
                input_file_path=tmp_path,
                model_version_id=None,
                use_rules=True,
                job_name="Unit-File-Path-Job",
            )
            self.assertEqual(job2.status, DetectionJobStatus.COMPLETED)
            self.assertEqual(job2.total_records, 10)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        # Query & dispatch to Investigation
        res = service.get_detection_job_results(job1.job_id, action_filter="FLAGGED")
        self.assertEqual(res["total_filtered"], 4)


class TestInferenceServiceWithRealStorageOutput(unittest.TestCase):
    """Integration tests running real pipeline artifacts from storage_output."""

    @classmethod
    def setUpClass(cls):
        cls.core_root = Path(__file__).resolve().parent.parent
        cls.storage_output_dir = cls.core_root / "storage_output"
        cls.repo_root = cls.core_root.parent
        cls.mapped_csv_path = cls.repo_root / "datasets" / "e-commerce-fraud-detection-dataset" / "mapped.csv"
        cls.raw_csv_path = cls.repo_root / "datasets" / "e-commerce-fraud-detection-dataset" / "raw.csv"

        if not cls.mapped_csv_path.exists() or not cls.raw_csv_path.exists() or not (cls.storage_output_dir / "datasets").exists():
            raise unittest.SkipTest("Integration dataset files or trained pipeline artifacts not found at storage_output/datasets")

        cls.storage_output_dir.mkdir(parents=True, exist_ok=True)

        # Create small test samples (50 rows) for fast batch inference testing
        cls.sample_mapped_path = cls.storage_output_dir / "sample_batch_mapped.csv"
        df_mapped = pd.read_csv(cls.mapped_csv_path, nrows=50)

        df_mapped.to_csv(cls.sample_mapped_path, index=False)

        cls.sample_raw_path = cls.storage_output_dir / "sample_batch_raw.csv"
        df_raw = pd.read_csv(cls.raw_csv_path, nrows=50)
        df_raw.to_csv(cls.sample_raw_path, index=False)

        cls.storage = DiskStorage(base_dir=cls.storage_output_dir)
        cls.pipeline_repo = InMemoryPipelineRepository()
        cls.job_repo = InMemoryDetectionJobRepository()
        cls.deployment_id = UUID("d1e2f3a4-b5c6-4d7e-8f9a-0b1c2d3e4f5a")

        cls.service = InferenceService(
            pipeline_repo=cls.pipeline_repo,
            file_storage=cls.storage,
            detection_job_repo=cls.job_repo,
        )

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "sample_mapped_path") and cls.sample_mapped_path.exists():
            cls.sample_mapped_path.unlink()
        if hasattr(cls, "sample_raw_path") and cls.sample_raw_path.exists():
            cls.sample_raw_path.unlink()

    def test_deployment_validation_not_found(self):
        empty_repo = InMemoryPipelineRepository(use_storage_fallback=False)
        service = InferenceService(empty_repo, self.storage)
        with self.assertRaises(ValueError) as ctx:
            service.online_inference(uuid4(), {})
        self.assertIn("No pipeline found", str(ctx.exception))

    def test_deployment_validation_inactive(self):
        stopped_deployment = Deployment(
            deployment_id=uuid4(),
            version_id=uuid4(),
            deployment_name="stopped_model",
            environment=DeploymentEnvironment.STAGING,
            status=DeploymentStatus.STOPPED,
        )
        default_pipeline = self.pipeline_repo.get_by_deployment_id(self.deployment_id)
        stopped_pipeline = Pipeline(
            raw_dataset_artifact=default_pipeline.raw_dataset_artifact,
            mapped_dataset_artifact=default_pipeline.mapped_dataset_artifact,
            feature_engineered_dataset_artifact=default_pipeline.feature_engineered_dataset_artifact,
            preprocessed_dataset_artifact=default_pipeline.preprocessed_dataset_artifact,
            model_version=default_pipeline.model_version,
            deployment=stopped_deployment,
        )
        repo = InMemoryPipelineRepository(
            pipelines={stopped_deployment.deployment_id: stopped_pipeline},
            use_storage_fallback=False,
        )
        service = InferenceService(repo, self.storage)

        with self.assertRaises(ValueError) as ctx:
            service.online_inference(stopped_deployment.deployment_id, {})
        self.assertIn("is not RUNNING", str(ctx.exception))

    def test_schema_validation_missing_columns(self):
        incomplete_event = {
            "event_id": 1,
            "user_id": 1,
        }
        with self.assertRaises(ValueError) as ctx:
            self.service.online_inference(self.deployment_id, incomplete_event)
        self.assertIn("missing required feature columns", str(ctx.exception).lower())

    def test_online_inference_mapped_schema(self):
        event = {
            "event_id": 101,
            "user_id": 42,
            "account_age_days": 200,
            "total_transactions_user": 50,
            "avg_amount_user": 120.5,
            "amount": 75.0,
            "country": "US",
            "bin_country": "US",
            "channel": "mobile",
            "merchant_category": "retail",
            "promo_used": 1,
            "avs_match": 1,
            "cvv_result": 1,
            "three_ds_flag": 1,
            "timestamp": "2024-03-15T10:30:00Z",
            "shipping_distance_km": 15.2,
        }
        result = self.service.online_inference(self.deployment_id, event)

        self.assertIn("prediction", result)
        self.assertIn("probability", result)
        self.assertIn("is_fraud", result)
        self.assertIn("risk_score", result)
        self.assertIn("latency_ms", result)

        self.assertIn(result["prediction"], [0, 1])
        self.assertIsInstance(result["is_fraud"], bool)
        self.assertGreaterEqual(result["probability"], 0.0)
        self.assertLessEqual(result["probability"], 1.0)
        self.assertEqual(result["risk_score"], round(result["probability"] * 100, 2))
        self.assertGreater(result["latency_ms"], 0.0)

    def test_online_inference_raw_schema(self):
        raw_event = {
            "transaction_id": 9999,
            "user_id": 105,
            "account_age_days": 50,
            "total_transactions_user": 10,
            "avg_amount_user": 300.0,
            "amount": 2500.0,
            "country": "FR",
            "bin_country": "FR",
            "channel": "web",
            "merchant_category": "electronics",
            "promo_used": 0,
            "avs_match": 0,
            "cvv_result": 0,
            "three_ds_flag": 0,
            "transaction_time": "2024-03-15T02:15:00Z",
            "shipping_distance_km": 850.0,
            "extra_client_metadata": "discard_me",
        }
        result = self.service.online_inference(self.deployment_id, raw_event)

        self.assertIn("prediction", result)
        self.assertIn(result["prediction"], [0, 1])
        self.assertGreaterEqual(result["probability"], 0.0)

    def test_batch_inference_executor_directly(self):
        """Tests that BatchInferenceExecutor executes with zero DB access given a BatchInferencePayload."""
        pipeline = self.pipeline_repo.get_by_deployment_id(self.deployment_id)
        job_id = uuid4()
        project_id = uuid4()
        output_path = f"projects/{project_id}/inferences/{self.deployment_id}/{job_id}/predictions.parquet"

        payload = BatchInferencePayload(
            job_id=job_id,
            project_id=project_id,
            deployment_id=self.deployment_id,
            input_path=str(self.sample_mapped_path),
            output_storage_path=output_path,
            fe_artifact_path=pipeline.feature_engineered_dataset_artifact.output_paths["fitted_engineers"],
            prep_artifact_path=pipeline.preprocessed_dataset_artifact.output_paths["pipeline"],
            model_artifact_uri=pipeline.model_version.artifact_uri,
            column_mapping=pipeline.mapped_dataset_artifact.validation_report["column_mapping"],
        )

        executor = BatchInferenceExecutor(file_storage=self.storage)
        result = executor.run(payload)

        self.assertTrue(result.is_success)
        self.assertEqual(result.job_id, job_id)
        self.assertGreater(result.total_records, 0)
        self.assertGreaterEqual(result.fraud_records, 0)
        self.assertTrue(self.storage.exists(output_path))

        # Check output parquet content
        saved_bytes = self.storage.read_bytes(output_path)
        df = pd.read_parquet(io.BytesIO(saved_bytes))
        self.assertIn("prediction", df.columns)
        self.assertIn("fraud_probability", df.columns)

    def test_batch_inference_service_flow(self):
        """Tests end-to-end batch_inference producing DetectionJob and updating records."""
        project_id = uuid4()
        job = self.service.batch_inference(
            project_id=project_id,
            deployment_id=self.deployment_id,
            input_path=str(self.sample_raw_path),
            job_name="Test-E2E-Batch",
        )

        self.assertIsInstance(job, DetectionJob)
        self.assertEqual(job.status, DetectionJobStatus.COMPLETED)
        self.assertIsNotNone(job.output_path)
        self.assertGreater(job.total_records, 0)
        self.assertIsNotNone(job.execution_time_seconds)

        # Check repo persistence
        persisted_job = self.job_repo.get_by_id(job.job_id)
        self.assertIsNotNone(persisted_job)
        self.assertEqual(persisted_job.status, DetectionJobStatus.COMPLETED)

        # Check output file
        saved_bytes = self.storage.read_bytes(job.output_path)
        df = pd.read_parquet(io.BytesIO(saved_bytes))
        self.assertIn("prediction", df.columns)
        self.assertIn("fraud_probability", df.columns)
        self.assertIn("event_id", df.columns)

    def test_batch_inference_with_dispatchers(self):
        """Tests batch inference using explicit SynchronousBatchDispatcher and LocalProcessBatchDispatcher."""
        # 1. Synchronous dispatcher
        exec_sync = BatchInferenceExecutor(
            file_storage=self.storage,
            notifier=self.service.handle_job_completion,
        )
        sync_dispatcher = SynchronousBatchDispatcher(executor_func=exec_sync.run)

        sync_service = InferenceService(
            pipeline_repo=self.pipeline_repo,
            file_storage=self.storage,
            detection_job_repo=self.job_repo,
            dispatcher=sync_dispatcher,
        )
        job_sync = sync_service.batch_inference(
            project_id=uuid4(),
            deployment_id=self.deployment_id,
            input_path=str(self.sample_mapped_path),
        )
        self.assertEqual(job_sync.status, DetectionJobStatus.COMPLETED)

        # 2. LocalProcess (background thread) dispatcher
        exec_async = BatchInferenceExecutor(
            file_storage=self.storage,
            notifier=self.service.handle_job_completion,
        )
        async_dispatcher = LocalProcessBatchDispatcher(executor_func=exec_async.run)

        async_service = InferenceService(
            pipeline_repo=self.pipeline_repo,
            file_storage=self.storage,
            detection_job_repo=self.job_repo,
            dispatcher=async_dispatcher,
        )
        job_async = async_service.batch_inference(
            project_id=uuid4(),
            deployment_id=self.deployment_id,
            input_path=str(self.sample_mapped_path),
        )
        # Wait up to 5 seconds for thread to finish
        for _ in range(50):
            updated_job = self.job_repo.get_by_id(job_async.job_id)
            if updated_job and updated_job.status == DetectionJobStatus.COMPLETED:
                break
            time.sleep(0.1)

        final_job = self.job_repo.get_by_id(job_async.job_id)
        self.assertEqual(final_job.status, DetectionJobStatus.COMPLETED)
        self.assertGreater(final_job.total_records, 0)

    def test_hybrid_detection_flow_raw_artifact_and_file_path(self):
        """Tests SUC-15, SUC-16, SUC-19: Hybrid Detection (ModelVersion + Active Rules) with RAW artifact and file path."""
        default_pipeline = self.pipeline_repo.get_by_deployment_id(self.deployment_id)
        project_id = uuid4()

        df_sample_raw = pd.read_csv(self.sample_raw_path)
        locked_schema = ProjectSchemaValidator.extract_raw_schema(df_sample_raw).to_dict()

        project_repo = InMemoryProjectRepository()
        project_repo.save(
            Project(
                project_id=project_id,
                user_id=uuid4(),
                project_name="Hybrid Detection Project",
                raw_schema=locked_schema,
            )
        )

        # Save RAW sample into storage as a RAW DatasetArtifact
        raw_rel_path = f"datasets/raw_test/{uuid4()}/raw.csv"
        self.storage.save_bytes(raw_rel_path, self.sample_raw_path.read_bytes())

        artifact_repo = InMemoryDatasetArtifactRepository()
        raw_artifact = DatasetArtifact(
            artifact_id=default_pipeline.raw_dataset_artifact.artifact_id,
            dataset_id=default_pipeline.raw_dataset_artifact.dataset_id,
            pipeline_stage=PipelineStage.RAW,
            storage_path=raw_rel_path,
            output_paths={"raw": raw_rel_path},
            row_count=50,
            column_count=17,
            validation_status=ValidationStatus.PASSED,
        )
        artifact_repo.save(raw_artifact)
        artifact_repo.save(default_pipeline.mapped_dataset_artifact)
        artifact_repo.save(default_pipeline.feature_engineered_dataset_artifact)
        artifact_repo.save(default_pipeline.preprocessed_dataset_artifact)

        # Save ModelVersion (APPROVED) & TrainingRun + RunDataset linking to PRE_PROCESSED artifact
        run_id = uuid4()
        model_version_id = uuid4()
        mv_repo = InMemoryModelVersionRepository()
        mv_repo.save(
            ModelVersion(
                version_id=model_version_id,
                model_id=default_pipeline.model_version.model_id,
                run_id=run_id,
                semver="1.0.0",
                status=ModelVersionStatus.APPROVED,
                artifact_uri=default_pipeline.model_version.artifact_uri,
                decision_threshold=0.5,
            )
        )

        training_run_repo = InMemoryTrainingRunRepository()
        training_run_repo.save(
            TrainingRun(
                run_id=run_id,
                model_id=default_pipeline.model_version.model_id,
                run_name="test-run",
            )
        )
        training_run_repo.link_dataset(
            RunDataset(
                run_id=run_id,
                dataset_artifact_id=default_pipeline.preprocessed_dataset_artifact.artifact_id,
            )
        )

        # Create ACTIVE rules (1 REJECT rule, 1 REVIEW rule) via RuleManager
        rule_repo = InMemoryRuleRepository()
        rule_manager = RuleManager(rule_repo=rule_repo, project_repo=project_repo)
        rule_manager.create_rule(
            project_id=project_id,
            rule_code="RL-HIGH-AMT",
            name="High Amount Reject",
            description="Reject high amount",
            condition={">": [{"var": "amount"}, 300.0]},
            action=RuleAction.REJECT,
            status=RuleStatus.ACTIVE,
        )
        rule_manager.create_rule(
            project_id=project_id,
            rule_code="RL-MED-AMT",
            name="Medium Amount Review",
            description="Review medium amount",
            condition={">": [{"var": "amount"}, 100.0]},
            action=RuleAction.REVIEW,
            status=RuleStatus.ACTIVE,
        )

        hybrid_job_repo = InMemoryDetectionJobRepository()

        hybrid_service = InferenceService(
            pipeline_repo=self.pipeline_repo,
            file_storage=self.storage,
            detection_job_repo=hybrid_job_repo,
            artifact_repo=artifact_repo,
            model_version_repo=mv_repo,
            training_run_repo=training_run_repo,
            rule_manager=rule_manager,
            project_repo=project_repo,
        )

        # Reject non-RAW artifact in Option 1
        with self.assertRaises(ValueError) as ctx:
            hybrid_service.start_detection_job(
                project_id=project_id,
                target_artifact_id=default_pipeline.mapped_dataset_artifact.artifact_id,
                model_version_id=model_version_id,
            )
        self.assertIn("must be at stage 'RAW'", str(ctx.exception))

        # Option 1: Start detection job with RAW target_artifact_id + APPROVED ModelVersion + ACTIVE Rules
        job1 = hybrid_service.start_detection_job(
            project_id=project_id,
            target_artifact_id=raw_artifact.artifact_id,
            model_version_id=model_version_id,
            score_threshold=0.5,
            use_rules=True,
            job_name="Hybrid-RAW-Artifact-Job",
        )
        self.assertEqual(job1.status, DetectionJobStatus.COMPLETED)
        self.assertEqual(job1.total_records, 50)
        self.assertIn("reject_count", job1.summary_metrics)
        self.assertIn("review_count", job1.summary_metrics)
        self.assertIn("allow_count", job1.summary_metrics)
        self.assertEqual(
            job1.summary_metrics["reject_count"]
            + job1.summary_metrics["review_count"]
            + job1.summary_metrics["allow_count"],
            50,
        )

        # Option 2: Start detection job with direct input_file_path in Rule-Only mode
        job2 = hybrid_service.start_detection_job(
            project_id=project_id,
            input_file_path=str(self.sample_raw_path),
            model_version_id=None,
            use_rules=True,
            job_name="Rule-Only-File-Job",
        )
        self.assertEqual(job2.status, DetectionJobStatus.COMPLETED)
        self.assertEqual(job2.total_records, 50)

        # Query detection job results (SUC-16)
        results = hybrid_service.get_detection_job_results(
            job_id=job1.job_id,
            action_filter="FLAGGED",
            limit=20,
            offset=0,
        )
        self.assertGreater(results["total_filtered"], 0)
        first_record = results["transactions"][0]
        self.assertIn(first_record["final_action"], ["REJECT", "REVIEW"])

        # Export detection results
        csv_bytes, filename, media_type = hybrid_service.export_detection_job_results(
            job_id=job1.job_id,
            file_format="csv",
            only_flagged=True,
        )
        self.assertTrue(filename.endswith(".csv"))
        self.assertEqual(media_type, "text/csv")
        self.assertGreater(len(csv_bytes), 0)


class TestPluginInferenceTimeout(unittest.TestCase):
    def test_plugin_bundle_inference_timeout_raises_runtime_error(self):
        """ISS-022: Hanging plugin inference subprocess must time out with RuntimeError."""
        import tempfile
        import zipfile
        from usfds_core.services.inference.executor import execute_plugin_bundle_inference

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(
                "src/main.py",
                (
                    "import time\n"
                    "def run_inference(input_file, artifact_dir):\n"
                    "    time.sleep(5)\n"
                    "    return [0.5]\n"
                ),
            )
            zf.writestr("src/plugin_manifest.json", '{"entrypoint": "main.py", "data_format": "parquet"}')

        df = pd.DataFrame({"f1": [1.0, 2.0]})
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws = InferenceWorkspace(inference_id=uuid4(), deployment_id=uuid4(), base_dir=Path(tmp_dir))
            ws.initialize()
            with self.assertRaises(RuntimeError) as ctx:
                execute_plugin_bundle_inference(
                    feature_engineered_df=df,
                    bundle_bytes=buf.getvalue(),
                    workspace=ws,
                    timeout_seconds=1,
                )
        self.assertIn("timed out", str(ctx.exception).lower())


class _CaseIdsOnlyRepo:
    """Case repo double: the results page must ask only for the ids on the page, never list the whole project."""

    def __init__(self, case_ids_by_event):
        self.case_ids_by_event = case_ids_by_event
        self.requested = []

    def list_by_project(self, project_id):
        raise AssertionError("list_by_project must not be used for the results page (ISS-012)")

    def get_case_ids_by_events(self, project_id, event_ids):
        self.requested.append(list(event_ids))
        return {e: self.case_ids_by_event[e] for e in event_ids if e in self.case_ids_by_event}


def test_detection_results_pagination_uses_duckdb_without_pandas_full_load(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("pd.read_parquet must not be used (ISS-012)")

    rows = []
    for i in range(100):
        final_action = "REJECT" if i % 10 == 0 else ("REVIEW" if i % 10 in (1, 2) else "ALLOW")
        rows.append({
            "event_id": f"EV-{i:03d}", "user_id": f"U-{i % 7}", "timestamp": "2026-11-01T10:00:00Z",
            "amount": float(10 + i), "model_score": i / 100, "rule_action": final_action, "final_action": final_action,
            "is_flagged": 1 if final_action != "ALLOW" else 0,
            "triggered_rules": '["R1"]' if i % 2 == 0 else "[]", "triggered_rule_details": "[]", "feature_x": float(i),
        })
    storage = InMemoryStorage()
    project_id = uuid4()
    job = DetectionJob(project_id=project_id, job_name="results", output_path="out/predictions.parquet", status=DetectionJobStatus.COMPLETED)
    buf = io.BytesIO()
    pd.DataFrame(rows).to_parquet(buf, index=False)
    storage.save_bytes(job.output_path, buf.getvalue())
    job_repo = InMemoryDetectionJobRepository()
    job_repo.save(job)
    case_ids = {f"EV-{i:03d}": str(uuid4()) for i in (10, 20, 22, 90)}
    case_repo = _CaseIdsOnlyRepo(case_ids)
    service = InferenceService(file_storage=storage, detection_job_repo=job_repo, case_repo=case_repo)
    monkeypatch.setattr(pd, "read_parquet", _blocked)

    res = service.get_detection_job_results(
        job.job_id, action_filter="FLAGGED", rule_code="R1", min_score=0.05, max_score=0.9, limit=10, offset=5,
    )

    rank = {"REJECT": 0, "REVIEW": 1}
    matching = [r for r in rows if r["final_action"] != "ALLOW" and r["triggered_rules"] == '["R1"]' and 0.05 <= r["model_score"] <= 0.9]
    matching.sort(key=lambda r: (rank[r["final_action"]], -r["model_score"], -r["amount"]))
    expected_page = [r["event_id"] for r in matching[5:15]]
    assert res["total_filtered"] == len(matching) and len(matching) > 15
    assert [t["event_id"] for t in res["transactions"]] == expected_page
    assert all(t["is_flagged"] and t["triggered_rules"] == ["R1"] for t in res["transactions"])
    assert res["transactions"][0]["features"]["feature_x"] == float(int(expected_page[0][3:]))
    assert case_repo.requested == [expected_page]
    for t in res["transactions"]:
        assert t["case_id"] == case_ids.get(t["event_id"])

    searched = service.get_detection_job_results(job.job_id, search="u-3", action_filter="REJECT", limit=50)
    assert {t["user_id"] for t in searched["transactions"]} == {"U-3"}
    assert searched["total_filtered"] == len([r for r in rows if r["final_action"] == "REJECT" and r["user_id"] == "U-3"])
