from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union
from uuid import UUID, uuid4

from usfds_core.domain.entities.enums import DataClassification, PipelineStage, ValidationStatus


@dataclass
class Dataset:
    """Represents a transactional/fraud detection dataset within a project."""
    dataset_name: str
    user_id: UUID
    project_id: UUID
    dataset_id: UUID = field(default_factory=uuid4)
    display_name: Optional[str] = None
    description: Optional[str] = None
    contains_pii: bool = False
    data_classification: Optional[Union[DataClassification, str]] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None


@dataclass
class DatasetArtifact:
    """Represents an immutable physical snapshot/version of dataset data across pipeline stages (lineage)."""
    dataset_id: UUID
    storage_path: str
    artifact_id: UUID = field(default_factory=uuid4)
    parent_artifact_id: Optional[UUID] = None
    pipeline_stage: Union[PipelineStage, str] = PipelineStage.RAW
    change_type: Optional[str] = None
    checksum_sha256: Optional[str] = None
    schema_snapshot: Optional[Dict[str, Any]] = None
    row_count: Optional[int] = None
    column_count: Optional[int] = None
    validation_status: Optional[Union[ValidationStatus, str]] = "pending"
    validation_report: Optional[Dict[str, Any]] = None
    output_paths: Dict[str, str] = field(default_factory=dict)
    created_by: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


__all__ = ["Dataset", "DatasetArtifact"]
