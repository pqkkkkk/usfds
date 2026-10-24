from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from usfds_core.domain.schemas.model_plugin import ModelPluginManifest


class RegisterPluggedModelRequest(BaseModel):
    """Request payload to validate and register a custom user-imported model plugin."""
    model_config = ConfigDict(extra="ignore")

    model_artifact_path: str = Field(
        ...,
        description="Path to the plugin source archive (.zip) or directory in storage/local filesystem",
    )
    user_id: Optional[UUID] = Field(default=None, description="Owner user ID")
    project_id: Optional[UUID] = Field(default=None, description="Optional project ID")
    manifest_override: Optional[ModelPluginManifest] = Field(
        default=None,
        description="Optional manifest metadata override if plugin_manifest.json is not bundled",
    )


class StartTrainingRunRequest(BaseModel):
    """Request payload to initiate and dispatch a model training run."""
    model_config = ConfigDict(extra="ignore")

    model_id: UUID = Field(..., description="Registered Model ID to train")
    dataset_artifact_id: UUID = Field(
        ...,
        description="ID of the FEATURE_ENGINEERED (or PRE_PROCESSED) dataset artifact",
    )
    hyperparameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional hyperparameter overrides for this run",
    )
    run_name: Optional[str] = Field(default=None, description="Optional custom training run name")
    created_by: str = Field(default="system", description="User or service initiating the run")


class ModelResponse(BaseModel):
    """API response schema for a registered Model."""
    model_config = ConfigDict(extra="ignore")

    model_id: UUID
    project_id: Optional[UUID] = None
    user_id: UUID
    model_name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    execution_type: str
    entrypoint_uri: Optional[str] = None
    hyperparameter_schema: Optional[Dict[str, Any]] = None
    default_hyperparameters: Optional[Dict[str, Any]] = None
    risk_level: Optional[str] = None
    github_repo: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class ModelVersionResponse(BaseModel):
    """API response schema for a registered ModelVersion."""
    model_config = ConfigDict(extra="ignore")

    version_id: UUID
    model_id: UUID
    project_id: Optional[UUID] = None
    run_id: Optional[UUID] = None
    semver: str
    artifact_uri: str
    description: Optional[str] = None
    artifact_size_mb: Optional[float] = None
    checksum_sha256: Optional[str] = None
    framework: Optional[str] = None
    decision_threshold: float = 0.5
    status: str
    registered_by: Optional[str] = None
    registered_at: datetime


class TrainingRunResponse(BaseModel):
    """API response schema for a TrainingRun and its evaluation metrics."""
    model_config = ConfigDict(extra="ignore")

    run_id: UUID
    project_id: Optional[UUID] = None
    model_id: Optional[UUID] = None
    version_id: Optional[UUID] = None
    run_name: str
    status: str
    accuracy: Optional[float] = None
    precision_score: Optional[float] = None
    recall_score: Optional[float] = None
    f1_score: Optional[float] = None
    loss: Optional[float] = None
    default_threshold: float = 0.5
    recommended_threshold: Optional[float] = None
    hyperparameters: Optional[Dict[str, Any]] = None
    custom_metrics: Optional[Dict[str, Any]] = None
    compute_target: Optional[str] = "local"
    error_message: Optional[str] = None
    created_by: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    logs_path: Optional[str] = None
    metrics_path: Optional[str] = None
    eval_predictions_path: Optional[str] = None
    created_at: datetime


__all__ = [
    "RegisterPluggedModelRequest",
    "StartTrainingRunRequest",
    "ModelResponse",
    "ModelVersionResponse",
    "TrainingRunResponse",
]
