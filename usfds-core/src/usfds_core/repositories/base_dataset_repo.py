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
    def get_by_name(self, project_id: UUID, dataset_name: str) -> Optional[Dataset]:
        """Retrieve a Dataset entity by its name within a project."""
        pass

    @abstractmethod
    def list_by_project(self, project_id: UUID) -> List[Dataset]:
        """List all datasets belonging to a given project."""
        pass

    @abstractmethod
    def list_all(
        self,
        project_id: Optional[UUID] = None,
        search: Optional[str] = None,
    ) -> List[Dataset]:
        """List datasets with optional filtering by project or search query."""
        pass

    @abstractmethod
    def delete(self, dataset_id: UUID) -> bool:
        """Delete a dataset by ID. Returns True if deleted, False otherwise."""
        pass


__all__ = ["IDatasetRepository"]
