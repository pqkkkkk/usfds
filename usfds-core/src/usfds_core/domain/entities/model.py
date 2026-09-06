from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union
from uuid import UUID, uuid4

from usfds_core.domain.entities.enums import (
    DatasetRole,
    ExecutionType,
    ModelVersionStatus,
    RiskLevel,
    TrainingRunStatus,
)


@dataclass
class Model:
    """Represents a machine learning model registered in the Model Registry."""
    model_name: str
    user_id: UUID
    model_id: UUID = field(default_factory=uuid4)
    display_name: Optional[str] = None
    description: Optional[str] = None
    execution_type: Union[ExecutionType, str] = ExecutionType.BUILTIN
    entrypoint_uri: Optional[str] = None
    hyperparameter_schema: Optional[Dict[str, Any]] = None
    default_hyperparameters: Optional[Dict[str, Any]] = None
    risk_level: Optional[Union[RiskLevel, str]] = None
    github_repo: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None


@dataclass
class ModelVersion:
    """Represents a specific registered release/version of a model."""
    model_id: UUID
    semver: str
    artifact_uri: str
    version_id: UUID = field(default_factory=uuid4)
    run_id: Optional[UUID] = None
    description: Optional[str] = None
    artifact_size_mb: Optional[float] = None
    checksum_sha256: Optional[str] = None
    framework: Optional[str] = None
    status: Union[ModelVersionStatus, str] = ModelVersionStatus.DRAFT
    registered_by: Optional[str] = None
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TrainingRun:
    """Represents an experiment or training run execution for a model."""
    run_name: str
    run_id: UUID = field(default_factory=uuid4)
    model_id: Optional[UUID] = None
    version_id: Optional[UUID] = None
    status: Union[TrainingRunStatus, str] = TrainingRunStatus.PENDING
    accuracy: Optional[float] = None
    precision_score: Optional[float] = None
    recall_score: Optional[float] = None
    f1_score: Optional[float] = None
    loss: Optional[float] = None
    hyperparameters: Optional[Dict[str, Any]] = None
    custom_metrics: Optional[Dict[str, Any]] = None
    compute_target: Optional[str] = "local"
    error_message: Optional[str] = None
    created_by: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    logs_path: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RunDataset:
    """Represents the association between a training run and the datasets consumed."""
    run_id: UUID
    dataset_artifact_id: UUID
    dataset_role: Union[DatasetRole, str] = DatasetRole.TRAIN
    sample_count: Optional[int] = None
    usage_percentage: Optional[float] = None
