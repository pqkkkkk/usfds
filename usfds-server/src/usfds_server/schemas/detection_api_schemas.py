from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class StartDetectionJobRequest(BaseModel):
	"""Request payload to start a hybrid batch detection job (SUC-15)."""
	project_id: UUID = Field(..., description="Active project UUID")
	target_artifact_id: Optional[UUID] = Field(
		default=None,
		description="Option 1: Existing DatasetArtifact UUID at stage RAW",
	)
	input_file_path: Optional[str] = Field(
		default=None,
		description="Option 2: Local or storage file path (.csv, .parquet, .pq, .json) to ingest and score",
	)
	model_version_id: Optional[UUID] = Field(
		default=None,
		description="Optional APPROVED ModelVersion UUID. If omitted, runs in Rule-Only mode.",
	)
	use_rules: bool = Field(
		default=True,
		description="Whether to evaluate ACTIVE business rules in the project",
	)
	score_threshold: Optional[float] = Field(
		default=None,
		gt=0.0,
		lt=1.0,
		description="Model score decision threshold (0.0 < threshold < 1.0). Defaults to ModelVersion.decision_threshold.",
	)
	job_name: Optional[str] = Field(default=None, max_length=255, description="Human-readable job name")
	created_by: str = Field(default="system", description="User or actor starting the job")


class DetectionJobResponse(BaseModel):
	"""Response schema for a DetectionJob record (SUC-15, SUC-16, SUC-19)."""
	job_id: UUID
	project_id: UUID
	deployment_id: Optional[UUID] = None
	target_artifact_id: Optional[UUID] = None
	model_version_id: Optional[UUID] = None
	job_name: Optional[str] = None
	input_path: str
	output_path: Optional[str] = None
	score_threshold: float = 0.5
	use_rules: bool = True
	status: str
	total_records: Optional[int] = None
	fraud_records: Optional[int] = None
	fraud_rate: Optional[float] = None
	summary_metrics: Optional[Dict[str, Any]] = None
	execution_time_seconds: Optional[float] = None
	error_message: Optional[str] = None
	created_by: Optional[str] = None
	created_at: datetime
	started_at: Optional[datetime] = None
	completed_at: Optional[datetime] = None


class TriggeredRuleDetailResponse(BaseModel):
	"""Detail of an ACTIVE rule triggered on a specific transaction."""
	rule_id: str
	rule_version_id: str
	version_number: int = 1
	rule_code: str
	rule_name: str
	action: str
	matched_clauses: List[str] = Field(default_factory=list)


class DetectionTransactionRecordResponse(BaseModel):
	"""Single transaction detection result row with evidence snapshot (SUC-16)."""
	row_index: int
	event_id: str
	user_id: str
	timestamp: str
	amount: float
	model_score: float
	triggered_rules: List[str] = Field(default_factory=list)
	triggered_rule_details: List[TriggeredRuleDetailResponse] = Field(default_factory=list)
	rule_action: str
	final_action: str
	is_flagged: bool
	case_id: Optional[str] = None
	features: Dict[str, Any] = Field(default_factory=dict)


class DetectionJobResultsResponse(BaseModel):
	"""Paginated and filtered detection job results response (SUC-16)."""
	job: DetectionJobResponse
	total_filtered: int
	transactions: List[DetectionTransactionRecordResponse] = Field(default_factory=list)
	summary_metrics: Dict[str, Any] = Field(default_factory=dict)


class SendToInvestigationRequest(BaseModel):
	"""Request payload to dispatch flagged transactions to Investigation (SUC-16)."""
	event_ids: List[str] = Field(..., min_length=1, description="List of transaction event_ids to create cases for")
	analyst_notes: Optional[str] = Field(default=None, description="Optional initial triage notes")


class InvestigationCaseResponse(BaseModel):
	"""Response schema for an InvestigationCase record."""
	case_id: UUID
	project_id: UUID
	event_id: int
	assigned_to: Optional[UUID] = None
	status: str
	risk_level: str
	fraud_probability: Optional[float] = None
	analyst_notes: Optional[str] = None
	action_taken: Optional[str] = None
	sar_narrative: Optional[str] = None
	metadata: Dict[str, Any] = Field(default_factory=dict)
	created_at: datetime
	updated_at: datetime
	resolved_at: Optional[datetime] = None
