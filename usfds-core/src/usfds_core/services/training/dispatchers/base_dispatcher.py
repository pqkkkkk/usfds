from abc import ABC, abstractmethod
from usfds_core.domain.schemas.training_payload import TrainingRunPayload


class ITrainingRunDispatcher(ABC):
    """Abstract interface for dispatching a training run to an execution environment."""

    @abstractmethod
    def dispatch_run(self, payload: TrainingRunPayload) -> None:
        """Dispatch a TrainingRunPayload to the background compute engine or queue."""
        pass
