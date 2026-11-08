import json
import unittest
from uuid import uuid4

from usfds_core.domain.schemas.inference_payload import BatchInferencePayload
from usfds_core.domain.schemas.training_payload import TrainingRunPayload

from usfds_infra.database import to_psycopg_conninfo
from usfds_infra.job_queue import (
	JOB_BATCH_INFERENCE,
	JOB_TRAINING_RUN,
	QUEUE_BATCH_INFERENCE,
	QUEUE_TRAINING,
	BullMQJobQueue,
	QueueBatchInferenceDispatcher,
	QueueTrainingDispatcher,
)


class _StubQueue:
	calls = []

	def __init__(self, name, opts):
		self.name = name
		self.opts = opts

	async def add(self, job_name, data, job_opts):
		_StubQueue.calls.append((self.name, job_name, data, job_opts, self.opts))

	async def close(self):
		pass


class TestQueueDispatchers(unittest.TestCase):
	def setUp(self):
		_StubQueue.calls = []
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


if __name__ == "__main__":
	unittest.main()
