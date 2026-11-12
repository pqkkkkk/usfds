import json
import unittest
from uuid import uuid4

from usfds_core.domain.schemas.inference_payload import BatchInferencePayload
from usfds_core.domain.schemas.training_payload import TrainingRunPayload

from usfds_infra.database import to_psycopg_conninfo
from usfds_infra.job_queue import (
	JOB_BATCH_INFERENCE,
	JOB_DATASET_INGESTION,
	JOB_TRAINING_RUN,
	QUEUE_BATCH_INFERENCE,
	QUEUE_DATA_PIPELINE,
	QUEUE_TRAINING,
	BullMQJobQueue,
	QueueBatchInferenceDispatcher,
	QueueTrainingDispatcher,
)


class _StubJob:
	def __init__(self, job_id, state="completed", returnvalue=None, failed_reason=None):
		self.id = job_id
		self._state = state
		self.returnvalue = returnvalue
		self.failedReason = failed_reason

	async def getState(self):
		return self._state


class _StubQueue:
	calls = []
	jobs = {}

	def __init__(self, name, opts):
		self.name = name
		self.opts = opts

	async def add(self, job_name, data, job_opts):
		_StubQueue.calls.append((self.name, job_name, data, job_opts, self.opts))
		job_id = (job_opts or {}).get("jobId") or "auto-job-id"
		return _StubQueue.jobs.get(job_id, _StubJob(job_id, returnvalue={"ok": True}))

	async def getJob(self, job_id):
		return _StubQueue.jobs.get(job_id, _StubJob(job_id, returnvalue={"ok": True}))

	async def close(self):
		pass


class TestQueueDispatchers(unittest.TestCase):
	def setUp(self):
		_StubQueue.calls = []
		_StubQueue.jobs = {}
		self.job_queue = BullMQJobQueue(
			"postgresql+psycopg://u:p@db:5432/usfds", queue_factory=_StubQueue
		)

	def test_training_payload_is_enqueued_as_json_with_run_id_as_job_id(self):
		payload = TrainingRunPayload(run_id=uuid4(), model_id=uuid4(), model_name="xgboost", train_storage_path="a/train.parquet")
		QueueTrainingDispatcher(self.job_queue).dispatch_run(payload)

		queue_name, job_name, data, job_opts, opts = _StubQueue.calls[0]
		self.assertEqual((queue_name, job_name), (QUEUE_TRAINING, JOB_TRAINING_RUN))
		self.assertEqual(job_opts["jobId"], str(payload.run_id))
		json.dumps(data)
		self.assertEqual(TrainingRunPayload.model_validate(data), payload)
		self.assertEqual(opts["backend"], "postgres")
		self.assertEqual(opts["connection"], "postgresql://u:p@db:5432/usfds")

	def test_batch_payload_goes_to_batch_queue(self):
		payload = BatchInferencePayload(job_id=uuid4(), project_id=uuid4(), input_path="in.csv", output_storage_path="out.parquet")
		QueueBatchInferenceDispatcher(self.job_queue).dispatch_batch(payload)

		queue_name, job_name, data, _, _ = _StubQueue.calls[0]
		self.assertEqual((queue_name, job_name), (QUEUE_BATCH_INFERENCE, JOB_BATCH_INFERENCE))
		self.assertEqual(BatchInferencePayload.model_validate(data), payload)

	def test_conninfo_strips_sqlalchemy_driver(self):
		self.assertEqual(to_psycopg_conninfo("postgresql+psycopg://a@h/d"), "postgresql://a@h/d")

	def test_enqueue_and_wait_returns_completed_result(self):
		_StubQueue.jobs["ingest-1"] = _StubJob(
			"ingest-1",
			state="completed",
			returnvalue={"dataset_id": "ds-1", "artifact_id": "art-1"},
		)
		res = self.job_queue.enqueue_and_wait(
			QUEUE_DATA_PIPELINE,
			JOB_DATASET_INGESTION,
			{"file_path": "uploads/raw.csv", "dataset_name": "test"},
			job_id="ingest-1",
		)
		self.assertEqual(res, {"dataset_id": "ds-1", "artifact_id": "art-1"})

	def test_enqueue_and_wait_propagates_typed_worker_exception(self):
		_StubQueue.jobs["ingest-missing"] = _StubJob(
			"ingest-missing",
			state="failed",
			failed_reason="FileNotFoundError: Source dataset file not found at 'missing.csv'",
		)
		with self.assertRaises(FileNotFoundError):
			self.job_queue.enqueue_and_wait(
				QUEUE_DATA_PIPELINE,
				JOB_DATASET_INGESTION,
				{"file_path": "missing.csv", "dataset_name": "test"},
				job_id="ingest-missing",
			)


if __name__ == "__main__":
	unittest.main()
