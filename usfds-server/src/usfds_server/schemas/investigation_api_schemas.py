import json
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from usfds_core.domain.entities.case import BlacklistEntityType, CaseStatus
from usfds_core.domain.entities.enums import RiskLevel


NonemptyId = Annotated[str, Field(min_length=1, max_length=255)]
Score = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class TriggeredRuleSnapshot(BaseModel):
	model_config = ConfigDict(extra="forbid")
	rule_id: UUID
	rule_version_id: UUID
	version_number: int = Field(ge=1)
	rule_code: str = Field(min_length=1, max_length=100)
	rule_name: str
	action: Literal["REVIEW", "REJECT"]
	trigger_reason: str
	matched_clauses: list[str] = Field(default_factory=list)
	is_triggered: Literal[True] = True
	execution_time_ms: float = Field(default=0, ge=0, allow_inf_nan=False)


class FeatureContribution(BaseModel):
	model_config = ConfigDict(extra="forbid")
	feature_name: NonemptyId
	feature_value: Any = None
	contribution: float = Field(allow_inf_nan=False)


class TransactionSnapshot(BaseModel):
	model_config = ConfigDict(extra="forbid")
	event_id: NonemptyId
	user_id: NonemptyId
	timestamp: AwareDatetime
	amount: float = Field(ge=0, allow_inf_nan=False)
	model_score: Score | None = None
	final_action: Literal["REVIEW", "REJECT"]
	triggered_rules: list[TriggeredRuleSnapshot] = Field(default_factory=list)
	feature_contributions: list[FeatureContribution] = Field(default_factory=list)
	attributes: dict[str, Any] = Field(default_factory=dict)

	@field_validator("event_id", "user_id")
	@classmethod
	def validate_id(cls, value: str) -> str:
		if not value.strip():
			raise ValueError("ID must not be whitespace")
		return value

	@model_validator(mode="after")
	def validate_snapshot(self):
		versions = [str(rule.rule_version_id) for rule in self.triggered_rules]
		if len(versions) != len(set(versions)):
			raise ValueError("Duplicate triggered rule version")
		json.dumps(self.model_dump(mode="json"), allow_nan=False)
		return self


class CaseIntakeRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")
	project_id: UUID
	dataset_artifact_id: UUID | None = None
	detection_job_id: UUID | None = None
	model_version_id: UUID | None = None
	transactions: list[TransactionSnapshot] = Field(min_length=1, max_length=5000)

	@model_validator(mode="after")
	def validate_source(self):
		if self.dataset_artifact_id is None and self.detection_job_id is None:
			raise ValueError("A dataset artifact or detection job source is required")
		return self


class CaseResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)
	case_id: UUID
	case_code: str
	project_id: UUID
	event_id: str
	user_id: str
	tx_timestamp: AwareDatetime
	amount: float
	final_action: str
	model_score: float | None
	dataset_artifact_id: UUID | None
	detection_job_id: UUID | None
	model_version_id: UUID | None
	triggered_rules: list[dict[str, Any]]
	triggered_rule_codes: list[str]
	feature_contributions: list[dict[str, Any]]
	attributes: dict[str, Any]
	status: CaseStatus
	priority: RiskLevel
	priority_score: float
	assigned_to: str | None
	resolution_reason: str | None
	resolution_summary: str | None
	resolved_at: AwareDatetime | None
	resolved_by: str | None
	verified_label: int | None
	version: int
	created_at: AwareDatetime
	updated_at: AwareDatetime


class CaseActionRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")
	expected_version: int = Field(ge=1)
	summary: str = Field(default="", max_length=10000)
	assignee: str | None = Field(default=None, max_length=100)


class BlockEntityRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")
	entity_type: BlacklistEntityType
	entity_value: NonemptyId


class ResolveCaseRequest(CaseActionRequest):
	verdict: Literal["FRAUD", "LEGITIMATE"]
	reason: str
	block_entities: list[BlockEntityRequest] = Field(default_factory=list, max_length=5)


class NoteRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")
	note: str = Field(min_length=1, max_length=10000)


class AddBlacklistRequest(BlockEntityRequest):
	project_id: UUID
	reason: str = Field(min_length=10, max_length=10000)
	source_case_id: UUID | None = None


class RemoveBlacklistRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")
	reason: str = Field(min_length=10, max_length=10000)