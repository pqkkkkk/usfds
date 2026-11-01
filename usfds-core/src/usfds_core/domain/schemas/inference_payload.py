"""Data Transfer Objects for Batch Inference Execution."""

from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class ActiveRuleSnapshot(BaseModel):
	"""Snapshot of an ACTIVE rule version sent to the BatchInferenceExecutor."""
	rule_id: str
	rule_version_id: str
	version_number: int = 1
	rule_code: str
	rule_name: str
	action: str
	condition: Dict[str, Any] = Field(default_factory=dict)


class BatchInferencePayload(BaseModel):
	"""Data Transfer Object sent to Batch Inference Worker Executor (zero direct DB access)."""
	job_id: UUID
	project_id: UUID
	deployment_id: Optional[UUID] = None
	model_version_id: Optional[UUID] = None
	input_path: str
	output_storage_path: str
	fe_artifact_path: Optional[str] = None
	prep_artifact_path: Optional[str] = None
	model_artifact_uri: Optional[str] = None
	decision_threshold: float = 0.5
	column_mapping: Dict[str, str] = Field(default_factory=dict)
	use_rules: bool = True
	active_rules: List[ActiveRuleSnapshot] = Field(default_factory=list)


class BatchInferenceResult(BaseModel):
	"""Data Transfer Object returned from Batch Inference Worker Executor."""
	job_id: UUID
	is_success: bool
	output_path: Optional[str] = None
	total_records: int = 0
	fraud_records: int = 0
	fraud_rate: float = 0.0
	duration_seconds: float = 0.0
	summary_metrics: Optional[Dict[str, Any]] = None
	error_message: Optional[str] = None

