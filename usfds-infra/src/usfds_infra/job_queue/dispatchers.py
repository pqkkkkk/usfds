import logging

from usfds_core.domain.schemas.inference_payload import BatchInferencePayload
from usfds_core.domain.schemas.training_payload import TrainingRunPayload
from usfds_core.services.inference.dispatchers.base_dispatcher import IBatchInferenceDispatcher
from usfds_core.services.training.dispatchers.base_dispatcher import ITrainingRunDispatcher

from usfds_infra.job_queue.bullmq_queue import (
	JOB_BATCH_INFERENCE,
	JOB_TRAINING_RUN,
	QUEUE_BATCH_INFERENCE,
	QUEUE_TRAINING,
	BullMQJobQueue,
)

logger = logging.getLogger(__name__)


class QueueTrainingDispatcher(ITrainingRunDispatcher):
	"""Pushes a TrainingRunPayload to the BullMQ queue; `usfds-worker` executes it."""

	def __init__(self, job_queue: BullMQJobQueue):
		self.job_queue = job_queue

	def dispatch_run(self, payload: TrainingRunPayload) -> None:
		logger.info(f"Enqueueing training run {payload.run_id}")
		self.job_queue.enqueue(
			QUEUE_TRAINING,
			JOB_TRAINING_RUN,
			payload.model_dump(mode="json"),
			job_id=str(payload.run_id),
		)


class QueueBatchInferenceDispatcher(IBatchInferenceDispatcher):
	"""Pushes a BatchInferencePayload to the BullMQ queue; `usfds-worker` executes it."""

	def __init__(self, job_queue: BullMQJobQueue):
		self.job_queue = job_queue

	def dispatch_batch(self, payload: BatchInferencePayload) -> None:
		logger.info(f"Enqueueing batch inference job {payload.job_id}")
		self.job_queue.enqueue(
			QUEUE_BATCH_INFERENCE,
			JOB_BATCH_INFERENCE,
			payload.model_dump(mode="json"),
			job_id=str(payload.job_id),
		)
