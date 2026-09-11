from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.model import ModelVersion
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union
from uuid import UUID, uuid4

from usfds_core.domain.entities.enums import (
    DeploymentEnvironment,
    DeploymentStatus,
    DetectionJobStatus,
    RuleType,
)


@dataclass
class Deployment:
    """Represents the deployment configuration for serving model inference."""
    version_id: UUID
    deployment_name: str
    environment: Union[DeploymentEnvironment, str]
    deployment_id: UUID = field(default_factory=uuid4)
    endpoint_url: Optional[str] = None
    serving_framework: Optional[str] = None
    replicas: int = 1
    status: Union[DeploymentStatus, str] = DeploymentStatus.PENDING
    traffic_percentage: int = 100
    deployed_by: Optional[str] = None
    deployed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class Pipeline:
    raw_dataset_artifact: DatasetArtifact
    mapped_dataset_artifact: DatasetArtifact
    feature_engineered_dataset_artifact: DatasetArtifact
    preprocessed_dataset_artifact: DatasetArtifact
    model_version: ModelVersion
    deployment: Deployment

@dataclass
class Rule:
    """Represents a business rule for fraud detection within a project."""
    project_id: UUID
    rule_name: str
    rule_type: Union[RuleType, str]
    rule_id: UUID = field(default_factory=uuid4)
    rule_condition: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DetectionJob:
    """Represents a batch inference / fraud detection job execution."""
    project_id: UUID
    deployment_id: UUID
    input_path: str
    job_id: UUID = field(default_factory=uuid4)
    job_name: Optional[str] = None
    output_path: Optional[str] = None
    status: Union[DetectionJobStatus, str] = DetectionJobStatus.PENDING
    total_records: Optional[int] = None
    fraud_records: Optional[int] = None
    fraud_rate: Optional[float] = None
    execution_time_seconds: Optional[float] = None
    error_message: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

