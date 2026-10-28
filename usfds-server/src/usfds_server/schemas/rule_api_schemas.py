from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field

from usfds_core.domain.entities.enums import RuleAction, RuleStatus


# ==========================================
# Rule Version DTOs
# ==========================================

class RuleVersionResponse(BaseModel):
    rule_version_id: UUID
    rule_id: UUID
    version_number: int
    condition: Dict[str, Any]
    action: RuleAction
    change_summary: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime


# ==========================================
# Rule DTOs
# ==========================================

class CreateRuleRequest(BaseModel):
    project_id: UUID
    rule_code: str = Field(..., min_length=2, max_length=100, description="Unique code for rule, e.g. R_HIGH_AMOUNT")
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = Field(default="", max_length=1000)
    condition: Dict[str, Any] = Field(..., description="JsonLogic condition tree")
    action: RuleAction = Field(default=RuleAction.REVIEW)
    status: RuleStatus = Field(default=RuleStatus.ACTIVE)
    change_summary: Optional[str] = Field(default="Initial version")
    created_by: Optional[str] = None


class UpdateRuleRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    condition: Optional[Dict[str, Any]] = Field(default=None, description="JsonLogic condition. Triggers new RuleVersion if provided.")
    action: Optional[RuleAction] = Field(default=None, description="Action. Triggers new RuleVersion if provided.")
    change_summary: Optional[str] = Field(default=None, description="Summary of changes in new version")
    created_by: Optional[str] = None


class SetRuleStatusRequest(BaseModel):
    status: RuleStatus


class RuleResponse(BaseModel):
    rule_id: UUID
    project_id: UUID
    rule_code: str
    name: str
    description: str
    status: RuleStatus
    current_version_id: Optional[UUID] = None
    current_version: Optional[RuleVersionResponse] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ==========================================
# Execution / Evaluation DTOs
# ==========================================

class EvaluateRuleRequest(BaseModel):
    """Payload to evaluate a single rule or ad-hoc rule version against a context."""
    transaction_id: str
    raw_features: Dict[str, Any] = Field(default_factory=dict)
    mapped_features: Dict[str, Any] = Field(default_factory=dict)
    enriched_features: Dict[str, Any] = Field(default_factory=dict)


class EvaluateRulesRequest(BaseModel):
    """Payload to evaluate all active rules in a project against a transaction."""
    project_id: UUID
    transaction_id: str
    raw_features: Dict[str, Any] = Field(default_factory=dict)
    mapped_features: Dict[str, Any] = Field(default_factory=dict)
    enriched_features: Dict[str, Any] = Field(default_factory=dict)


class RuleExecutionResultResponse(BaseModel):
    rule_id: str
    rule_version_id: str
    version_number: int
    rule_code: str
    rule_name: str
    is_triggered: bool
    action: RuleAction
    trigger_reason: str
    execution_time_ms: float


# ==========================================
# Backtest / Dry-Run DTOs (SUC-12)
# ==========================================

class BacktestRuleRequest(BaseModel):
    """Payload to backtest/dry-run a saved rule or ad-hoc rule condition against a historical DatasetArtifact."""
    project_id: UUID
    dataset_artifact_id: UUID
    rule_id: Optional[UUID] = Field(default=None, description="Optional saved Rule ID to backtest")
    version_id: Optional[UUID] = Field(default=None, description="Optional specific RuleVersion ID")
    condition: Optional[Dict[str, Any]] = Field(default=None, description="Optional ad-hoc JsonLogic condition tree (overrides saved rule condition if provided)")
    action: Optional[RuleAction] = Field(default=None, description="Optional ad-hoc RuleAction")
    rule_code: Optional[str] = Field(default=None, description="Optional rule code for display")
    rule_name: Optional[str] = Field(default=None, description="Optional rule name for display")
    target_column: Optional[str] = Field(default=None, description="Optional ground-truth label column override")
    amount_column: Optional[str] = Field(default=None, description="Optional transaction amount column override")
    max_samples: int = Field(default=50, ge=1, le=200)


class RuleBacktestSampleHitResponse(BaseModel):
    event_id: str
    timestamp: str
    amount: float
    user_id: str
    ground_truth: Optional[int] = None
    matched_clauses: List[str] = Field(default_factory=list)
    features: Dict[str, Any] = Field(default_factory=dict)


class RuleBacktestResultResponse(BaseModel):
    rule_id: Optional[str] = None
    rule_version_id: Optional[str] = None
    version_number: int = 1
    rule_code: str
    rule_name: str
    action: RuleAction
    dataset_artifact_id: str
    total_transactions: int
    total_hits: int
    hit_rate: float
    has_ground_truth: bool
    target_column: Optional[str] = None
    tp: int
    fp: int
    tn: int
    fn: int
    precision: float
    recall: float
    fpr: float
    fraud_amount_caught: float
    execution_time_ms: float
    avg_execution_time_ms: float
    sample_hits: List[RuleBacktestSampleHitResponse] = Field(default_factory=list)

