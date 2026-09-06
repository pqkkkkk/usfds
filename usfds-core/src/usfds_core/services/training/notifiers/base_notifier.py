from abc import ABC, abstractmethod
import logging
from typing import Any, Callable
from usfds_core.domain.schemas.training_payload import TrainingRunResult

logger = logging.getLogger(__name__)


class ITrainingResultNotifier(ABC):
    """Abstract interface for notifying server/service upon training execution completion."""

    @abstractmethod
    def notify(self, result: TrainingRunResult) -> None:
        """Send execution results back to the controller/orchestrator."""
        pass


class CallbackResultNotifier(ITrainingResultNotifier):
    """Notifier that invokes a python callback function directly."""

    def __init__(self, callback: Callable[[TrainingRunResult], None]):
        self.callback = callback

    def notify(self, result: TrainingRunResult) -> None:
        try:
            self.callback(result)
        except Exception as e:
            logger.error(f"Callback notification failed: {e}", exc_info=True)


class LocalQueueResultNotifier(ITrainingResultNotifier):
    """Notifier that puts results into an in-memory or multiprocessing Queue."""

    def __init__(self, result_queue: Any):
        self.result_queue = result_queue

    def notify(self, result: TrainingRunResult) -> None:
        self.result_queue.put(result)


class WebhookResultNotifier(ITrainingResultNotifier):
    """Notifier that delivers results via HTTP POST to a webhook endpoint."""

    def __init__(self, webhook_url: str, timeout_seconds: int = 30):
        self.webhook_url = webhook_url
        self.timeout_seconds = timeout_seconds

    def notify(self, result: TrainingRunResult) -> None:
        import urllib.request
        import json

        data = json.dumps(result.model_dump(mode="json")).encode("utf-8")
        req = urllib.request.Request(
            self.webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
            logger.info(f"Webhook notified with status code {response.status}")
