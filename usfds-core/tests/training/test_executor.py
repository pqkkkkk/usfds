import io
from pathlib import Path
import shutil
import tempfile
import unittest
from uuid import uuid4
import numpy as np
import pandas as pd

from usfds_core.domain.schemas.training_payload import TrainingRunPayload, TrainingRunResult
from usfds_core.storage.base_storage import IFileStorage
from usfds_core.services.training.executor import TrainingRunExecutor
from usfds_core.services.training.notifiers.base_notifier import CallbackResultNotifier
from usfds_core.services.training.workspace import TrainingRunWorkspace


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


class TestTrainingRunExecutor(unittest.TestCase):
    def setUp(self):
        self.storage = InMemoryStorage()
        self.temp_workspace = Path(tempfile.mkdtemp())

        # Create dummy parquet datasets in storage
        n_samples = 50
        df_train = pd.DataFrame({
            "f1": np.random.randn(n_samples),
            "f2": np.random.randn(n_samples),
            "is_fraud": np.random.choice([0, 1], size=n_samples, p=[0.8, 0.2]),
        })
        train_buf = io.BytesIO()
        df_train.to_parquet(train_buf, index=False)
        self.train_path = "datasets/mock/train.parquet"
        self.storage.save_bytes(self.train_path, train_buf.getvalue())

    def tearDown(self):
        shutil.rmtree(self.temp_workspace, ignore_errors=True)

    def test_executor_successful_run(self):
        notified_results = []
        notifier = CallbackResultNotifier(callback=lambda r: notified_results.append(r))

        executor = TrainingRunExecutor(
            file_storage=self.storage,
            notifier=notifier,
        )

        payload = TrainingRunPayload(
            run_id=uuid4(),
            model_id=uuid4(),
            model_name="random_forest",
            execution_type="BUILTIN",
            train_storage_path=self.train_path,
            target_column="is_fraud",
            hyperparameters={"n_estimators": 5, "max_depth": 2},
        )

        result = executor.run(payload)

        self.assertTrue(result.is_success)
        self.assertIn("accuracy", result.metrics)
        self.assertIsNotNone(result.artifact_uri)
        self.assertTrue(self.storage.exists(result.artifact_uri))
        self.assertIsNotNone(result.checksum_sha256)
        self.assertEqual(len(notified_results), 1)
        self.assertEqual(notified_results[0].run_id, payload.run_id)

        # Workspace directory should be cleaned up
        run_workspace = TrainingRunWorkspace(run_id=payload.run_id).run_dir
        self.assertFalse(run_workspace.exists())

    def test_executor_failure_handling(self):
        executor = TrainingRunExecutor(
            file_storage=self.storage,
        )

        # Non-existent training storage path
        payload = TrainingRunPayload(
            run_id=uuid4(),
            model_id=uuid4(),
            model_name="random_forest",
            execution_type="BUILTIN",
            train_storage_path="datasets/non_existent/train.parquet",
            target_column="is_fraud",
            hyperparameters={},
        )

        result = executor.run(payload)
        self.assertFalse(result.is_success)
        self.assertIn("File datasets/non_existent/train.parquet not found", result.error_message)


if __name__ == "__main__":
    unittest.main()
