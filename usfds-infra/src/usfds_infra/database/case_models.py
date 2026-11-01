from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from usfds_infra.database.base import Base, TimestampMixin


class CaseModel(Base, TimestampMixin):
	__tablename__ = "fraud_cases"
	case_id: Mapped[str] = mapped_column(String(36), primary_key=True)
	project_id: Mapped[str] = mapped_column(String(36), nullable=False)
	case_code: Mapped[str] = mapped_column(String(64), nullable=False)
	event_id: Mapped[str] = mapped_column(String(255), nullable=False)
	user_id: Mapped[str] = mapped_column(String(255), nullable=False)
	tx_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
	amount: Mapped[float] = mapped_column(Float, nullable=False)
	final_action: Mapped[str] = mapped_column(String(20), nullable=False)
	dataset_artifact_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
	detection_job_id: Mapped[str | None] = mapped_column(String(36))
	model_version_id: Mapped[str | None] = mapped_column(String(36))
	model_score: Mapped[float | None] = mapped_column(Float)
	triggered_rules: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
	triggered_rule_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
	feature_contributions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
	attributes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
	status: Mapped[str] = mapped_column(String(30), nullable=False)
	priority: Mapped[str] = mapped_column(String(20), nullable=False)
	priority_score: Mapped[float] = mapped_column(Float, nullable=False)
	assigned_to: Mapped[str | None] = mapped_column(String(100))
	resolution_reason: Mapped[str | None] = mapped_column(String(50))
	resolution_summary: Mapped[str | None] = mapped_column(Text)
	resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
	resolved_by: Mapped[str | None] = mapped_column(String(100))
	version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
	__table_args__ = (
		UniqueConstraint("project_id", "event_id", name="uq_case_project_event"),
		UniqueConstraint("project_id", "case_code", name="uq_case_project_code"),
		CheckConstraint("amount >= 0"),
		CheckConstraint("model_score IS NULL OR (model_score >= 0 AND model_score <= 1)"),
		CheckConstraint("final_action IN ('REVIEW', 'REJECT')"),
		CheckConstraint("status IN ('OPEN','IN_PROGRESS','PENDING_CUSTOMER','RESOLVED_FRAUD','RESOLVED_LEGITIMATE')"),
		Index("idx_case_queue", "project_id", "status", "priority_score"),
		Index("idx_case_user", "project_id", "user_id"),
	)


class EntityBlacklistModel(Base):
	__tablename__ = "entity_blacklist"
	blacklist_id: Mapped[str] = mapped_column(String(36), primary_key=True)
	project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
	entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
	entity_value: Mapped[str] = mapped_column(String(255), nullable=False)
	reason: Mapped[str] = mapped_column(Text, nullable=False)
	status: Mapped[str] = mapped_column(String(20), nullable=False)
	source_case_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("fraud_cases.case_id"))
	created_by: Mapped[str] = mapped_column(String(100), nullable=False)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
	removed_by: Mapped[str | None] = mapped_column(String(100))
	removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
	__table_args__ = (
		CheckConstraint("status IN ('ACTIVE','REMOVED')"),
		Index("uq_active_blacklist", "project_id", "entity_type", "entity_value", unique=True,
			sqlite_where=(status == "ACTIVE"), postgresql_where=(status == "ACTIVE")),
	)


class AuditLogModel(Base):
	__tablename__ = "audit_logs"
	log_id: Mapped[str] = mapped_column(String(36), primary_key=True)
	project_id: Mapped[str | None] = mapped_column(String(36))
	entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
	entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
	action: Mapped[str] = mapped_column(String(40), nullable=False)
	actor: Mapped[str] = mapped_column(String(100), nullable=False)
	note: Mapped[str | None] = mapped_column(Text)
	details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
	__table_args__ = (
		Index("idx_audit_entity", "project_id", "entity_type", "entity_id", "created_at"),
		Index("idx_audit_project", "project_id", "created_at"),
	)