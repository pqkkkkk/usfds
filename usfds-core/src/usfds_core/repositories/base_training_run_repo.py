from abc import ABC, abstractmethod
from typing import List, Optional, Union
from uuid import UUID

from usfds_core.domain.entities.enums import DatasetRole
from usfds_core.domain.entities.model import RunDataset, TrainingRun


class ITrainingRunRepository(ABC):
    """Abstract interface for TrainingRun and RunDataset persistence."""

    @abstractmethod
    def save(self, run: TrainingRun) -> TrainingRun:
        """Persist or update a TrainingRun."""
        pass

    @abstractmethod
    def get_by_id(self, run_id: UUID) -> Optional[TrainingRun]:
        """Retrieve a TrainingRun by ID."""
        pass

    @abstractmethod
    def link_dataset(
        self,
        run_id: UUID,
        dataset_artifact_id: UUID,
        dataset_role: Union[DatasetRole, str] = DatasetRole.TRAIN,
        sample_count: Optional[int] = None,
        usage_percentage: Optional[float] = None,
    ) -> RunDataset:
        """Link a TrainingRun to a specific DatasetArtifact snapshot."""
        pass

    @abstractmethod
    def get_linked_datasets(self, run_id: UUID) -> List[RunDataset]:
        """Get all datasets linked to a training run."""
        pass

    @abstractmethod
    def list_by_model(self, model_id: UUID) -> List[TrainingRun]:
        """List all training runs associated with a model."""
        pass
