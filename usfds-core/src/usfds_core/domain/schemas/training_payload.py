from typing import Any, Dict, Optional
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

