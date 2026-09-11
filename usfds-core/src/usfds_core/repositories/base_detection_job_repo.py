from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from usfds_core.domain.entities.detection import DetectionJob


class IDetectionJobRepository(ABC):
    """Abstract interface for DetectionJob persistence."""

    @abstractmethod
    def save(self, job: DetectionJob) -> DetectionJob:
        """Persist or update a DetectionJob."""
        pass

    @abstractmethod
    def get_by_id(self, job_id: UUID) -> Optional[DetectionJob]:
        """Retrieve a DetectionJob by ID."""
        pass

    @abstractmethod
    def list_by_deployment(self, deployment_id: UUID) -> List[DetectionJob]:
        """List all detection jobs associated with a deployment."""
        pass

    @abstractmethod
    def list_by_project(self, project_id: UUID) -> List[DetectionJob]:
        """List all detection jobs associated with a project."""
        pass
