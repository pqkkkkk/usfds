import logging
import threading
from typing import Callable

from usfds_core.domain.schemas.inference_payload import BatchInferencePayload
from usfds_core.services.inference.dispatchers.base_dispatcher import IBatchInferenceDispatcher

logger = logging.getLogger(__name__)


class SynchronousBatchDispatcher(IBatchInferenceDispatcher):
    """Executes the batch inference task synchronously in the caller thread. Ideal for tests and CLI."""

    def __init__(self, executor_func: Callable[[BatchInferencePayload], None]):
        self.executor_func = executor_func

    def dispatch_batch(self, payload: BatchInferencePayload) -> None:
        logger.info(f"Synchronously dispatching batch inference job {payload.job_id}")
        self.executor_func(payload)


class LocalProcessBatchDispatcher(IBatchInferenceDispatcher):
    """Executes the batch inference task in a background daemon thread for non-blocking local runs."""

    def __init__(self, executor_func: Callable[[BatchInferencePayload], None]):
        self.executor_func = executor_func

    def dispatch_batch(self, payload: BatchInferencePayload) -> None:
        logger.info(f"Dispatching batch inference job {payload.job_id} in background thread")
        worker_thread = threading.Thread(
            target=self.executor_func,
            args=(payload,),
            daemon=True,
            name=f"BatchInferenceWorker-{payload.job_id}",
        )
        worker_thread.start()
