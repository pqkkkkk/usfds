from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from usfds_core.domain.entities.dataset import Dataset


class IDatasetRepository(ABC):
    """Abstract interface for Dataset persistence."""

    @abstractmethod
    def save(self, dataset: Dataset) -> Dataset:
        """Persist or update a Dataset entity."""
        pass

    @abstractmethod
    def get_by_id(self, dataset_id: UUID) -> Optional[Dataset]:
        """Retrieve a Dataset entity by its ID."""
        pass

    @abstractmethod
    def list_by_project(self, project_id: UUID) -> List[Dataset]:
        """List all datasets belonging to a given project."""
        pass


__all__ = ["IDatasetRepository"]
