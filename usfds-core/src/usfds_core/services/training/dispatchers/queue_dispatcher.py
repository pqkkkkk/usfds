import logging
from typing import Any, Callable, Optional

from usfds_core.domain.schemas.training_payload import TrainingRunPayload
from usfds_core.services.training.dispatchers.base_dispatcher import ITrainingRunDispatcher

logger = logging.getLogger(__name__)


class QueueRunDispatcher(ITrainingRunDispatcher):
    """Generic Message Queue Dispatcher that pushes payloads to an asynchronous task queue
    (e.g., Celery, Redis Queue, RabbitMQ, Kafka, SQS).
    """

    def __init__(self, publish_func: Callable[[dict], Any], queue_name: str = "training_queue"):
        self.publish_func = publish_func
        self.queue_name = queue_name

    def dispatch_run(self, payload: TrainingRunPayload) -> None:
        logger.info(f"Publishing training run {payload.run_id} to queue '{self.queue_name}'")
        message = {
            "queue": self.queue_name,
            "payload": payload.model_dump(mode="json"),
        }
        self.publish_func(message)
