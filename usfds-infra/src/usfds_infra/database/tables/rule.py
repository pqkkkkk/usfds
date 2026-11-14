"""ORM tables for the `rule` domain (moved from database/models.py, 26-11-14)."""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from usfds_infra.database.base import Base, TimestampMixin


class RuleModel(Base, TimestampMixin):
    """SQLAlchemy model for fraud detection business rules."""
    __tablename__ = "rules"

    rule_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rule_code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE", nullable=False)
    current_version_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    versions: Mapped[list["RuleVersionModel"]] = relationship(
        "RuleVersionModel",
        back_populates="rule",
        cascade="all, delete-orphan",
        order_by="RuleVersionModel.version_number",
    )

    __table_args__ = (
        UniqueConstraint("project_id", "rule_code", name="uq_project_rule_code"),
    )


class RuleVersionModel(Base):
    """SQLAlchemy model for immutable versions of a business rule."""
    __tablename__ = "rule_versions"

    rule_version_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("rules.rule_id", ondelete="CASCADE"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    condition: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    rule: Mapped["RuleModel"] = relationship("RuleModel", back_populates="versions")

    __table_args__ = (
        UniqueConstraint("rule_id", "version_number", name="uq_rule_version_number"),
    )
