from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, Field

from usfds_core.domain.entities.enums import ProjectStatus


class CreateProjectRequest(BaseModel):
    """Payload to create a new fraud detection project."""
    project_name: str = Field(..., min_length=1, max_length=255, description="Unique project name within user scope")
    user_id: Optional[UUID] = Field(default=None, description="Owner user ID")
    description: Optional[str] = Field(default=None, max_length=2000)


class UpdateProjectRequest(BaseModel):
    """Payload to update project metadata or status."""
    project_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[ProjectStatus] = Field(default=None, description="ACTIVE or ARCHIVED")


class ProjectResponse(BaseModel):
    """Project details response including locked RAW schema and resource counts."""
    project_id: UUID
    project_name: str
    user_id: UUID
    description: Optional[str] = None
    status: str
    is_schema_locked: bool = False
    base_dataset_id: Optional[UUID] = None
    raw_schema: Optional[Dict[str, Any]] = None
    datasets_count: int = 0
    rules_count: int = 0
    detection_jobs_count: int = 0
    created_at: datetime
    updated_at: datetime


__all__ = [
    "CreateProjectRequest",
    "UpdateProjectRequest",
    "ProjectResponse",
]
