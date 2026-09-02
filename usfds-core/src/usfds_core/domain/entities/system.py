from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4


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
    base_dataset_id: Optional[UUID] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
