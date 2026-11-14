"""ORM tables for the `project` domain (moved from database/models.py, 26-11-14)."""
from typing import Any, Dict, Optional
from uuid import uuid4
from sqlalchemy import JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from usfds_infra.database.base import Base, TimestampMixin


class ProjectModel(Base, TimestampMixin):
    """SQLAlchemy model for fraud detection projects and project-level RAW schema governance."""
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE", nullable=False, index=True)
    base_dataset_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    raw_schema: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "project_name", name="uq_user_project_name"),
    )
