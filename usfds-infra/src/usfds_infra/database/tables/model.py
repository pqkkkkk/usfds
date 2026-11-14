"""ORM tables for the `model` domain (moved from database/models.py, 26-11-14)."""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from usfds_infra.database.base import Base, TimestampMixin


class MLModel(Base, TimestampMixin):
    """SQLAlchemy model for registered machine learning models (BUILTIN or SCRIPT plugin)."""
    __tablename__ = "models"

    model_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_type: Mapped[str] = mapped_column(String(50), default="BUILTIN", nullable=False)
    entrypoint_uri: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    hyperparameter_schema: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    default_hyperparameters: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    github_repo: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


class ModelVersionModel(Base):
    """SQLAlchemy model for registered releases/versions of a machine learning model."""
    __tablename__ = "model_versions"

    version_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    model_id: Mapped[str] = mapped_column(String(36), ForeignKey("models.model_id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    run_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    semver: Mapped[str] = mapped_column(String(50), nullable=False)
    artifact_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    artifact_size_mb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    checksum_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    framework: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    decision_threshold: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="DRAFT", nullable=False)
    registered_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class TrainingRunModel(Base):
    """SQLAlchemy model for model training runs and evaluation metrics."""
    __tablename__ = "training_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    model_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("models.model_id", ondelete="SET NULL"), nullable=True, index=True)
    version_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    run_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False, index=True)
    accuracy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    precision_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recall_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    f1_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    default_threshold: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    recommended_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hyperparameters: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    custom_metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    compute_target: Mapped[Optional[str]] = mapped_column(String(100), default="local", nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    logs_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    metrics_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    eval_predictions_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class RunDatasetModel(Base):
	"""SQLAlchemy model linking a TrainingRun to the DatasetArtifact snapshots consumed."""
	__tablename__ = "run_datasets"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	run_id: Mapped[str] = mapped_column(String(36), ForeignKey("training_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
	dataset_artifact_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
	dataset_role: Mapped[str] = mapped_column(String(50), default="TRAIN", nullable=False)
	sample_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
	usage_percentage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
