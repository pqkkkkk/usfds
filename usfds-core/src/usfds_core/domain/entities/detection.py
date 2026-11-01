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
)


@dataclass
class Deployment:
	"""Represents the deployment configuration for serving model inference."""
	version_id: UUID
	deployment_name: str
	environment: Union[DeploymentEnvironment, str]
	deployment_id: UUID = field(default_factory=uuid4)
	project_id: Optional[UUID] = None
	endpoint_url: Optional[str] = None
	serving_framework: Optional[str] = None
	replicas: int = 1
	status: Union[DeploymentStatus, str] = DeploymentStatus.PENDING
	traffic_percentage: int = 100
	deployed_by: Optional[str] = None
	deployed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Pipeline:
	raw_dataset_artifact: Optional[DatasetArtifact] = None
	mapped_dataset_artifact: Optional[DatasetArtifact] = None
	feature_engineered_dataset_artifact: Optional[DatasetArtifact] = None
	preprocessed_dataset_artifact: Optional[DatasetArtifact] = None
	model_version: Optional[ModelVersion] = None
	deployment: Optional[Deployment] = None


@dataclass
class DetectionJob:
	"""Represents a batch inference / hybrid fraud detection job execution."""
	project_id: UUID
	deployment_id: Optional[UUID] = None
	input_path: str = ""
	job_id: UUID = field(default_factory=uuid4)
	job_name: Optional[str] = None
	target_artifact_id: Optional[UUID] = None
	model_version_id: Optional[UUID] = None
	score_threshold: float = 0.5
	use_rules: bool = True
	output_path: Optional[str] = None
	status: Union[DetectionJobStatus, str] = DetectionJobStatus.PENDING
	total_records: Optional[int] = None
	fraud_records: Optional[int] = None
	fraud_rate: Optional[float] = None
	summary_metrics: Optional[Dict[str, Any]] = None
	execution_time_seconds: Optional[float] = None
	error_message: Optional[str] = None
	created_by: Optional[str] = None
	created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
	started_at: Optional[datetime] = None
	completed_at: Optional[datetime] = None


