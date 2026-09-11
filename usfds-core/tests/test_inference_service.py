"""Comprehensive Unit & Integration Test Suite for USFDS Inference Service and Batch Executor."""

import io
from pathlib import Path
import time
import unittest
from uuid import UUID, uuid4
import pandas as pd

from usfds_core.domain.entities.detection import Deployment, DetectionJob, Pipeline
from usfds_core.domain.entities.enums import (
    DeploymentEnvironment,
    DeploymentStatus,
    DetectionJobStatus,
)
from usfds_core.domain.schemas.inference_payload import BatchInferencePayload
from usfds_core.repositories.in_memory_repos import (
    InMemoryDetectionJobRepository,
    InMemoryPipelineRepository,
)
from usfds_core.services.inference.dispatchers.local_dispatcher import (
    LocalProcessBatchDispatcher,
    SynchronousBatchDispatcher,
)
from usfds_core.services.inference.executor import (
    BatchInferenceExecutor
)
from usfds_core.services.inference.inference_service import InferenceService
from usfds_core.services.inference.workspace import InferenceWorkspace
from usfds_core.storage.base_storage import IFileStorage


class InMemoryStorage(IFileStorage):
    """In-memory dictionary-backed storage for fast unit tests."""

    def __init__(self):
        self.files = {}

    def save_bytes(self, file_path: str, data: bytes) -> str:
        self.files[file_path] = data
        return file_path

    def read_bytes(self, file_path: str) -> bytes:
        if file_path not in self.files:
            raise FileNotFoundError(f"File {file_path} not found in in-memory storage")
        return self.files[file_path]

    def exists(self, file_path: str) -> bool:
        return file_path in self.files


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


class TestInferenceServiceWithRealStorageOutput(unittest.TestCase):
    """Integration tests running real pipeline artifacts from storage_output."""

    @classmethod
    def setUpClass(cls):
        cls.core_root = Path(__file__).resolve().parent.parent
        cls.storage_output_dir = cls.core_root / "storage_output"
        cls.repo_root = cls.core_root.parent
        cls.mapped_csv_path = cls.repo_root / "datasets" / "e-commerce-fraud-detection-dataset" / "mapped.csv"
        cls.raw_csv_path = cls.repo_root / "datasets" / "e-commerce-fraud-detection-dataset" / "raw.csv"

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
