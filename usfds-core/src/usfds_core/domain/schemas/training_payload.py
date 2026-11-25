from typing import Any, Dict, List, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class TrainingRunPayload(BaseModel):
    """Data Transfer Object sent from Server/Controller to Worker Executor (no direct DB access)."""
    run_id: UUID
    model_id: UUID
    model_name: str
    execution_type: str = "BUILTIN"  # BUILTIN, SCRIPT, DOCKER_IMAGE
    entrypoint_uri: Optional[str] = None
    train_storage_path: str
    test_storage_path: Optional[str] = None
    fe_artifact_path: Optional[str] = None
    column_mapping: Dict[str, str] = Field(default_factory=dict)
    target_column: str = "is_fraud"
    hyperparameters: Dict[str, Any] = Field(default_factory=dict)
    compute_target: str = "local"


class TrainingRunResult(BaseModel):
    """Data Transfer Object returned from Worker Executor to Server/Controller."""
    run_id: UUID
    is_success: bool
    metrics: Dict[str, Any] = Field(default_factory=dict)
    artifact_uri: Optional[str] = None
    checksum_sha256: Optional[str] = None
    framework: str = "scikit-learn"
    metrics_uri: Optional[str] = None
    eval_predictions_uri: Optional[str] = None
    error_message: Optional[str] = None
    duration_seconds: Optional[int] = None


class RemoteTrainingJobSpec(BaseModel):
    """Self-contained specification submitted to a third-party compute provider (no S3 credentials)."""
    payload: TrainingRunPayload
    resource_tier: Literal["cpu", "gpu"] = "cpu"
    read_urls: Dict[str, str] = Field(default_factory=dict)
    write_urls: Dict[str, str] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RemoteJobStatus(BaseModel):
    """Normalized status returned by IRemoteComputeProvider.poll()."""
    state: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]
    result: Optional[TrainingRunResult] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ComputeTargetInfo(BaseModel):
    """Availability metadata for a single compute target option."""
    target_id: str
    display_name: str
    provider_type: Literal["auto", "local", "remote"]
    available: bool
    reason: Optional[str] = None
    resource_tiers: List[str] = Field(default_factory=list)


class ComputeRecommendation(BaseModel):
    """Resolved compute target decision produced by ComputeSelectionPolicy."""
    requested_target: str
    resolved_target: str
    resource_tier: Literal["cpu", "gpu"] = "cpu"
    provider: Optional[str] = None
    selection_reason: str


