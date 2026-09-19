"""Data Transfer Objects for Batch Inference Execution."""

from typing import Dict, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class BatchInferencePayload(BaseModel):
    """Data Transfer Object sent to Batch Inference Worker Executor (zero direct DB access)."""
    job_id: UUID
    project_id: UUID
    deployment_id: UUID
    input_path: str
    output_storage_path: str
    fe_artifact_path: str
    prep_artifact_path: str
    model_artifact_uri: str
    decision_threshold: float = 0.5
    column_mapping: Dict[str, str] = Field(default_factory=dict)


class BatchInferenceResult(BaseModel):
    """Data Transfer Object returned from Batch Inference Worker Executor."""
    job_id: UUID
    is_success: bool
    output_path: Optional[str] = None
    total_records: int = 0
    fraud_records: int = 0
    fraud_rate: float = 0.0
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
