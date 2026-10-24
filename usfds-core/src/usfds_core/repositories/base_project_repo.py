from abc import ABC, abstractmethod
from typing import List, Optional, Union
from uuid import UUID

from usfds_core.domain.entities.enums import ProjectStatus
from usfds_core.domain.entities.system import Project


class IProjectRepository(ABC):
    """Abstract interface for Project persistence."""

    @abstractmethod
    def save(self, project: Project) -> Project:
        """Persist or update a Project entity."""
        pass

    @abstractmethod
    def get_by_id(self, project_id: UUID) -> Optional[Project]:
        """Retrieve a Project entity by its ID."""
        pass

    @abstractmethod
    def get_by_name(self, user_id: UUID, project_name: str) -> Optional[Project]:
        """Retrieve a Project entity by its name within a user's scope."""
        pass

    @abstractmethod
    def list_all(
        self,
        user_id: Optional[UUID] = None,
        status: Optional[Union[ProjectStatus, str]] = None,
        search: Optional[str] = None,
    ) -> List[Project]:
        """List projects with optional filtering by user_id, status, or search query."""
        pass

    @abstractmethod
    def delete(self, project_id: UUID) -> bool:
        """Delete a project by ID. Returns True if deleted, False otherwise."""
        pass


__all__ = ["IProjectRepository"]
