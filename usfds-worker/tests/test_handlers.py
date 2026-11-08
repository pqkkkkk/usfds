import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from usfds_core.domain.entities.enums import TrainingRunStatus
from usfds_core.domain.entities.model import TrainingRun
from usfds_infra.database import SqliteTrainingRunRepository, create_session_factory, create_sqlite_engine, init_db
from usfds_infra.storage.local_storage import LocalFileStorage

from usfds_worker.handlers import WorkerContext, handle_training_run


class TestTrainingHandler(unittest.TestCase):
	def test_missing_training_data_marks_run_failed_in_db(self):
		with tempfile.TemporaryDirectory() as tmp:
			engine = create_sqlite_engine(Path(tmp) / "w.db")
			init_db(engine)
			factory = create_session_factory(engine)
			ctx = WorkerContext(session_factory=factory, storage=LocalFileStorage(Path(tmp) / "store"))

			run_id = uuid4()
			with factory() as s:
				SqliteTrainingRunRepository(s).save(TrainingRun(run_name="t", run_id=run_id, status=TrainingRunStatus.RUNNING))
				s.commit()

			handle_training_run(ctx, {
				"run_id": str(run_id), "model_id": str(uuid4()),
				"model_name": "random_forest", "train_storage_path": "missing/train.parquet",
			})

			with factory() as s:
				run = SqliteTrainingRunRepository(s).get_by_id(run_id)
			self.assertEqual(run.status, TrainingRunStatus.FAILED)
			engine.dispose()


if __name__ == "__main__":
	unittest.main()
