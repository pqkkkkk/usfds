from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union
from uuid import UUID, uuid4

from usfds_core.domain.entities.enums import ProjectStatus


@dataclass
class User:
    """Represents a user within the FDS system."""
    username: str
    email: str
    user_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Project:
    """Represents a fraud detection project."""
    project_name: str
    user_id: UUID
    project_id: UUID = field(default_factory=uuid4)
    description: Optional[str] = None
    status: Union[ProjectStatus, str] = ProjectStatus.ACTIVE
    base_dataset_id: Optional[UUID] = None
    raw_schema: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_schema_locked(self) -> bool:
        """Returns True if the project's RAW schema has been locked from its first dataset."""
        return bool(self.raw_schema and self.raw_schema.get("columns"))

