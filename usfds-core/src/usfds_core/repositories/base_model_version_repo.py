from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from usfds_core.domain.entities.model import ModelVersion


class IModelVersionRepository(ABC):
    """Abstract interface for ModelVersion persistence in Model Registry."""

    @abstractmethod
    def save(self, version: ModelVersion) -> ModelVersion:
        """Persist or update a ModelVersion."""
        pass

    @abstractmethod
    def get_by_id(self, version_id: UUID) -> Optional[ModelVersion]:
        """Retrieve a ModelVersion by its ID."""
        pass

    @abstractmethod
    def get_latest_version(self, model_id: UUID) -> Optional[ModelVersion]:
        """Retrieve the latest ModelVersion for a model (sorted by registered_at/semver)."""
        pass

    @abstractmethod
    def list_by_model(self, model_id: UUID) -> List[ModelVersion]:
        """List all versions for a given model."""
        pass
