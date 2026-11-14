import tempfile
import unittest
from pathlib import Path
from uuid import UUID, uuid4

import pandas as pd

from usfds_core.domain.entities.detection import DetectionJob
from usfds_core.domain.entities.enums import DetectionJobStatus, TrainingRunStatus
from usfds_core.domain.entities.model import TrainingRun
from usfds_infra.database import (
	SqliteDatasetArtifactRepository,
	SqliteDetectionJobRepository,
	SqliteTrainingRunRepository,
	create_session_factory,
	create_sqlite_engine,
	init_db,
)
from usfds_infra.storage.local_storage import LocalFileStorage

from usfds_worker.handlers import (
	WorkerContext,
	handle_batch_inference,
	handle_dataset_ingestion,
	handle_feature_engineering,
	handle_rule_backtest,
	handle_schema_mapping,
	handle_training_run,
)


class TestWorkerHandlers(unittest.TestCase):
	def test_missing_training_data_marks_run_failed_in_db(self):
		with tempfile.TemporaryDirectory() as tmp:
			engine = create_sqlite_engine(Path(tmp) / "w.db")
			init_db(engine)
			factory = create_session_factory(engine)
			ctx = WorkerContext(session_factory=factory, storage=LocalFileStorage(Path(tmp) / "store"))

			run_id = uuid4()
			with factory() as s:
				SqliteTrainingRunRepository(s).save(TrainingRun(run_name="t", run_id=run_id, status=TrainingRunStatus.PENDING))
				s.commit()

			handle_training_run(ctx, {
				"run_id": str(run_id), "model_id": str(uuid4()),
				"model_name": "random_forest", "train_storage_path": "missing/train.parquet",
			})

			with factory() as s:
				run = SqliteTrainingRunRepository(s).get_by_id(run_id)
			self.assertEqual(run.status, TrainingRunStatus.FAILED)
			engine.dispose()

	def test_missing_batch_inference_input_marks_job_failed_in_db(self):
		with tempfile.TemporaryDirectory() as tmp:
			engine = create_sqlite_engine(Path(tmp) / "w.db")
			init_db(engine)
			factory = create_session_factory(engine)
			ctx = WorkerContext(session_factory=factory, storage=LocalFileStorage(Path(tmp) / "store"))

			job_id = uuid4()
			project_id = uuid4()
			with factory() as s:
				SqliteDetectionJobRepository(s).save(
					DetectionJob(
						job_id=job_id,
						project_id=project_id,
						job_name="batch-test",
						status=DetectionJobStatus.PENDING,
					)
				)
				s.commit()

			handle_batch_inference(ctx, {
				"job_id": str(job_id),
				"project_id": str(project_id),
				"input_path": "missing/input.csv",
				"output_storage_path": "detection/out.parquet",
			})

			with factory() as s:
				job = SqliteDetectionJobRepository(s).get_by_id(job_id)
			self.assertEqual(job.status, DetectionJobStatus.FAILED)
			engine.dispose()

	def test_data_pipeline_and_rule_backtest_handlers_reuse_core_services(self):
		with tempfile.TemporaryDirectory() as tmp:
			engine = create_sqlite_engine(Path(tmp) / "w.db")
			init_db(engine)
			factory = create_session_factory(engine)
			storage = LocalFileStorage(Path(tmp) / "store")
			ctx = WorkerContext(session_factory=factory, storage=storage)

			# Seed a CSV directly into storage (simulating an S3 presigned upload key)
			rows = []
			for i in range(40):
				rows.append({
					"tx_id": f"ev_{i}",
					"user": f"u_{i % 5}",
					"ts": f"2026-01-01T00:{i:02d}:00Z",
					"amt": float(1000 if i % 4 == 0 else 50),
					"fraud": 1 if i % 4 == 0 else 0,
				})
			csv_bytes = pd.DataFrame(rows).to_csv(index=False).encode("utf-8")
			storage.save_bytes("uploads/raw/sample.csv", csv_bytes)

			# 1. Dataset Ingestion Handler
			ingest_res = handle_dataset_ingestion(ctx, {
				"file_path": "uploads/raw/sample.csv",
				"dataset_name": "worker_ds",
			})
			dataset_id = ingest_res["dataset_id"]
			raw_artifact_id = ingest_res["artifact_id"]
			self.assertTrue(dataset_id)
			self.assertTrue(raw_artifact_id)

			# 2. Schema Mapping Handler
			map_res = handle_schema_mapping(ctx, {
				"dataset_id": dataset_id,
				"mapping_config": {
					"event_id_column": "tx_id",
					"user_id_column": "user",
					"time_column": "ts",
					"amount_column": "amt",
					"target_column": "fraud",
				},
			})
			mapped_artifact_id = map_res["artifact_id"]
			self.assertNotEqual(mapped_artifact_id, raw_artifact_id)

			# 3. Feature Engineering Handler
			fe_res = handle_feature_engineering(ctx, {
				"dataset_id": dataset_id,
				"config": {
					"enable_amount_ratios": True,
					"enable_hour_of_day": True,
					"enable_velocity_features": False,
				},
			})
			fe_artifact_id = fe_res["artifact_id"]
			with factory() as s:
				fe_art = SqliteDatasetArtifactRepository(s).get_by_id(UUID(fe_artifact_id))
				self.assertIsNotNone(fe_art)
				self.assertIn("train", fe_art.output_paths)

			# 4. Rule Backtest Handler
			bt_res = handle_rule_backtest(ctx, {
				"dataset_artifact_id": mapped_artifact_id,
				"condition": {">": [{"var": "amount"}, 500]},
				"action": "REJECT",
				"rule_code": "R_HIGH_AMT",
				"rule_name": "High Amount",
			})
			self.assertEqual(bt_res["total_transactions"], 40)
			self.assertEqual(bt_res["total_hits"], 10)
			self.assertEqual(bt_res["action"], "REJECT")
			engine.dispose()


if __name__ == "__main__":
	unittest.main()
