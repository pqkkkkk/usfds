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
    mapped_features: Dict[str, Any] = Field(default_factory=dict)
    enriched_features: Dict[str, Any] = Field(default_factory=dict)


class EvaluateRulesRequest(BaseModel):
    """Payload to evaluate all active rules in a project against a transaction."""
    project_id: UUID
    transaction_id: str
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
