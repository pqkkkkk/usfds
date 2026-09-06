from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from usfds_core.domain.entities.model import Model


class IModelRepository(ABC):
    """Abstract interface for Model entity persistence."""

    @abstractmethod
    def save(self, model: Model) -> Model:
        """Persist or update a Model."""
        pass

    @abstractmethod
    def get_by_id(self, model_id: UUID) -> Optional[Model]:
        """Retrieve a Model by its ID."""
        pass

    @abstractmethod
    def list_models(self) -> List[Model]:
        """List all registered models."""
        pass
