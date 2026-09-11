from abc import ABC, abstractmethod
from usfds_core.domain.schemas.inference_payload import BatchInferencePayload


class IBatchInferenceDispatcher(ABC):
    """Abstract interface for dispatching a batch inference task to an execution environment."""

    @abstractmethod
    def dispatch_batch(self, payload: BatchInferencePayload) -> None:
        """Dispatch a BatchInferencePayload to the compute engine, queue, or executor."""
        pass
