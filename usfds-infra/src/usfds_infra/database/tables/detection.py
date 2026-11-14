"""ORM tables for the `detection` domain (moved from database/models.py, 26-11-14)."""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4
from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from usfds_infra.database.base import Base


class DetectionJobModel(Base):
	"""SQLAlchemy model for batch fraud detection jobs (SUC-15, SUC-16, SUC-19)."""
	__tablename__ = "detection_jobs"

	job_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
	project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
	deployment_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
	target_artifact_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
	model_version_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
	job_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
	input_path: Mapped[str] = mapped_column(String(500), nullable=False, default="")
	output_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
	score_threshold: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
	use_rules: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
	status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False, index=True)
	total_records: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
	fraud_records: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
	fraud_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
	summary_metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
	execution_time_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
	error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
	created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
	created_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True),
		default=lambda: datetime.now(timezone.utc),
		nullable=False,
	)
	started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
	completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

