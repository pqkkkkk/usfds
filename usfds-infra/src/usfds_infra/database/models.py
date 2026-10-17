from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from usfds_infra.database.base import Base, TimestampMixin


class DatasetModel(Base, TimestampMixin):
    """SQLAlchemy model for dataset catalog table."""
    __tablename__ = "datasets"

    dataset_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contains_pii: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    data_classification: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    artifacts: Mapped[list["DatasetArtifactModel"]] = relationship(
        "DatasetArtifactModel",
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="DatasetArtifactModel.created_at",
    )

    __table_args__ = (
        UniqueConstraint("project_id", "dataset_name", name="uq_project_dataset_name"),
    )


class DatasetArtifactModel(Base):
    """SQLAlchemy model for immutable dataset artifacts and lineage table."""
    __tablename__ = "dataset_artifacts"

    artifact_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    dataset_id: Mapped[str] = mapped_column(String(36), ForeignKey("datasets.dataset_id", ondelete="CASCADE"), nullable=False, index=True)
    parent_artifact_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("dataset_artifacts.artifact_id"), nullable=True, index=True)
    pipeline_stage: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    change_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    output_paths: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    checksum_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    schema_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    row_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    column_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    validation_status: Mapped[Optional[str]] = mapped_column(String(50), default="PENDING", nullable=True)
    validation_report: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), default="system", nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    dataset: Mapped["DatasetModel"] = relationship("DatasetModel", back_populates="artifacts")
    parent_artifact: Mapped[Optional["DatasetArtifactModel"]] = relationship(
        "DatasetArtifactModel",
        remote_side=[artifact_id],
        backref="children",
    )


__all__ = [
    "DatasetModel",
    "DatasetArtifactModel",
]
