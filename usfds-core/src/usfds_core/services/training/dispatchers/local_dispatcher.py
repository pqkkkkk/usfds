import logging
import threading
from typing import Callable

from usfds_core.domain.schemas.training_payload import TrainingRunPayload
from usfds_core.services.training.dispatchers.base_dispatcher import ITrainingRunDispatcher

logger = logging.getLogger(__name__)


class SynchronousRunDispatcher(ITrainingRunDispatcher):
    """Executes the training task synchronously in the caller thread. Ideal for CLI commands and tests."""

    def __init__(self, executor_func: Callable[[TrainingRunPayload], None]):
        self.executor_func = executor_func

    def dispatch_run(self, payload: TrainingRunPayload) -> None:
        logger.info(f"Synchronously dispatching training run {payload.run_id}")
        self.executor_func(payload)


class LocalProcessRunDispatcher(ITrainingRunDispatcher):
    """Executes the training task in a background daemon thread/process for non-blocking local runs."""

    def __init__(self, executor_func: Callable[[TrainingRunPayload], None]):
        self.executor_func = executor_func

    def dispatch_run(self, payload: TrainingRunPayload) -> None:
        logger.info(f"Dispatching training run {payload.run_id} in background thread")
        worker_thread = threading.Thread(
            target=self.executor_func,
            args=(payload,),
            daemon=True,
            name=f"TrainingWorker-{payload.run_id}",
        )
        worker_thread.start()
