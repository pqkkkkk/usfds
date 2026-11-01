from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from usfds_core.domain.entities.enums import RiskLevel, RuleAction


class CaseStatus(StrEnum):
	OPEN = "OPEN"
	IN_PROGRESS = "IN_PROGRESS"
	PENDING_CUSTOMER = "PENDING_CUSTOMER"
	RESOLVED_FRAUD = "RESOLVED_FRAUD"
	RESOLVED_LEGITIMATE = "RESOLVED_LEGITIMATE"


class BlacklistEntityType(StrEnum):
	USER_ID = "USER_ID"
	CARD_ID = "CARD_ID"
	DEVICE_ID = "DEVICE_ID"
	IP_ADDRESS = "IP_ADDRESS"
	MERCHANT_ID = "MERCHANT_ID"


FRAUD_REASONS = frozenset({
	"CARD_TESTING", "VELOCITY_ATTACK", "ACCOUNT_TAKEOVER",
	"DEVICE_SHARING_RING", "COLLUSIVE_MERCHANT", "OTHER_FRAUD",
})
LEGITIMATE_REASONS = frozenset({
	"LEGITIMATE_UNUSUAL_SPENDING", "CUSTOMER_CONFIRMED",
	"OVERLY_STRICT_RULE", "MODEL_FALSE_ALARM", "OTHER_LEGITIMATE",
})
OPEN_STATUSES = frozenset({CaseStatus.OPEN, CaseStatus.IN_PROGRESS, CaseStatus.PENDING_CUSTOMER})


@dataclass
class Case:
	project_id: UUID
	event_id: str
	user_id: str
	tx_timestamp: datetime
	amount: float
	final_action: RuleAction
	dataset_artifact_id: UUID | None
	case_id: UUID = field(default_factory=uuid4)
	case_code: str = ""
	model_score: float | None = None
	detection_job_id: UUID | None = None
	model_version_id: UUID | None = None
	triggered_rules: list[dict[str, Any]] = field(default_factory=list)
	feature_contributions: list[dict[str, Any]] = field(default_factory=list)
	attributes: dict[str, Any] = field(default_factory=dict)
	status: CaseStatus = CaseStatus.OPEN
	priority: RiskLevel = RiskLevel.MEDIUM
	priority_score: float = 0.0
	assigned_to: str | None = None
	resolution_reason: str | None = None
	resolution_summary: str | None = None
	resolved_at: datetime | None = None
	resolved_by: str | None = None
	version: int = 1
	created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
	updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

	@property
	def verified_label(self) -> int | None:
		if self.status == CaseStatus.RESOLVED_FRAUD:
			return 1
		if self.status == CaseStatus.RESOLVED_LEGITIMATE:
			return 0
		return None

	@property
	def triggered_rule_codes(self) -> list[str]:
		return sorted({rule["rule_code"] for rule in self.triggered_rules})


@dataclass
class EntityBlacklist:
	project_id: UUID
	entity_type: BlacklistEntityType
	entity_value: str
	reason: str
	created_by: str
	blacklist_id: UUID = field(default_factory=uuid4)
	source_case_id: UUID | None = None
	status: str = "ACTIVE"
	created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
	removed_at: datetime | None = None
	removed_by: str | None = None


@dataclass(frozen=True)
class AuditLog:
	project_id: UUID | None
	entity_type: str
	entity_id: str
	action: str
	actor: str
	note: str | None = None
	details: dict[str, Any] = field(default_factory=dict)
	log_id: UUID = field(default_factory=uuid4)
	created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))