from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from usfds_core.domain.entities.dataset import DatasetArtifact


class IDatasetArtifactRepository(ABC):
    """Abstract interface for DatasetArtifact persistence."""

    @abstractmethod
    def save(self, artifact: DatasetArtifact) -> DatasetArtifact:
        """Persist or update a DatasetArtifact."""
        pass

    @abstractmethod
    def get_by_id(self, artifact_id: UUID) -> Optional[DatasetArtifact]:
        """Retrieve a DatasetArtifact by its ID."""
        pass
