"""ORM tables for Feature Management, Dependencies, FeatureSets, and Artifact lineage (ISS-040)."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import (
	JSON,
	Boolean,
	CheckConstraint,
	ForeignKey,
	Index,
	Integer,
	String,
	Text,
	UniqueConstraint,
	text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from usfds_infra.database.base import Base, TimestampMixin


class FeatureModel(Base, TimestampMixin):
	"""Registry of built-in (project_id IS NULL) and project-scoped features."""

	__tablename__ = "features"

	feature_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
	project_id: Mapped[Optional[str]] = mapped_column(
		String(36),
		ForeignKey("projects.project_id", ondelete="CASCADE", name="fk_features_project_id_projects"),
		nullable=True,
		index=True,
	)
	user_id: Mapped[Optional[str]] = mapped_column(
		String(36),
		ForeignKey("users.user_id", ondelete="SET NULL", name="fk_features_user_id_users"),
		nullable=True,
		index=True,
	)
	feature_key: Mapped[str] = mapped_column(String(100), nullable=False)
	display_name: Mapped[str] = mapped_column(String(200), nullable=False)
	description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
	megafamily: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
	compute_kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
	output_type: Mapped[str] = mapped_column(String(32), nullable=False, default="NUMERIC")
	is_stateful: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
	requires_label: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
	config_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
	source_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
	required_inputs: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
	status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE", index=True)
	created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

	dependencies: Mapped[List["FeatureDependencyModel"]] = relationship(
		"FeatureDependencyModel",
		foreign_keys="FeatureDependencyModel.feature_id",
		back_populates="feature",
		cascade="all, delete-orphan",
	)

	__table_args__ = (
		UniqueConstraint("project_id", "feature_key", name="uq_features_project_key"),
		Index(
			"uq_features_builtin_key",
			"feature_key",
			unique=True,
			sqlite_where=text("project_id IS NULL"),
			postgresql_where=text("project_id IS NULL"),
		),
	)


class FeatureDependencyModel(Base):
	"""Directed acyclic dependency edge between a derived feature and its parent feature."""

	__tablename__ = "feature_dependencies"

	feature_id: Mapped[str] = mapped_column(
		String(36),
		ForeignKey("features.feature_id", ondelete="CASCADE", name="fk_feature_deps_feature_id"),
		primary_key=True,
	)
	depends_on_feature_id: Mapped[str] = mapped_column(
		String(36),
		ForeignKey("features.feature_id", ondelete="RESTRICT", name="fk_feature_deps_depends_on_id"),
		primary_key=True,
	)

	feature: Mapped["FeatureModel"] = relationship(
		"FeatureModel",
		foreign_keys=[feature_id],
		back_populates="dependencies",
	)

	__table_args__ = (
		CheckConstraint("feature_id != depends_on_feature_id", name="ck_feature_dependencies_no_self_ref"),
	)


class FeatureSetModel(Base, TimestampMixin):
	"""Named bundle of features (system built-in or project-scoped)."""

	__tablename__ = "feature_sets"

	feature_set_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
	project_id: Mapped[Optional[str]] = mapped_column(
		String(36),
		ForeignKey("projects.project_id", ondelete="CASCADE", name="fk_feature_sets_project_id_projects"),
		nullable=True,
		index=True,
	)
	user_id: Mapped[Optional[str]] = mapped_column(
		String(36),
		ForeignKey("users.user_id", ondelete="SET NULL", name="fk_feature_sets_user_id_users"),
		nullable=True,
		index=True,
	)
	set_key: Mapped[str] = mapped_column(String(100), nullable=False)
	name: Mapped[str] = mapped_column(String(200), nullable=False)
	description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
	domain_tag: Mapped[str] = mapped_column(String(32), nullable=False, default="CUSTOM")
	default_config: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
	created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

	items: Mapped[List["FeatureSetItemModel"]] = relationship(
		"FeatureSetItemModel",
		back_populates="feature_set",
		cascade="all, delete-orphan",
		order_by="FeatureSetItemModel.display_order",
	)

	__table_args__ = (
		UniqueConstraint("project_id", "set_key", name="uq_feature_sets_project_key"),
		Index(
			"uq_feature_sets_builtin_key",
			"set_key",
			unique=True,
			sqlite_where=text("project_id IS NULL"),
			postgresql_where=text("project_id IS NULL"),
		),
	)


class FeatureSetItemModel(Base):
	"""Ordered membership link between a FeatureSet and a Feature."""

	__tablename__ = "feature_set_items"

	feature_set_id: Mapped[str] = mapped_column(
		String(36),
		ForeignKey("feature_sets.feature_set_id", ondelete="CASCADE", name="fk_feature_set_items_set_id"),
		primary_key=True,
	)
	feature_id: Mapped[str] = mapped_column(
		String(36),
		ForeignKey("features.feature_id", ondelete="RESTRICT", name="fk_feature_set_items_feature_id"),
		primary_key=True,
	)
	display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

	feature_set: Mapped["FeatureSetModel"] = relationship("FeatureSetModel", back_populates="items")


class DatasetArtifactFeatureSetModel(Base):
	"""Many-to-many link recording 0, 1 or multiple FeatureSets applied to a FEATURE_ENGINEERED artifact."""

	__tablename__ = "dataset_artifact_feature_sets"

	artifact_id: Mapped[str] = mapped_column(
		String(36),
		ForeignKey("dataset_artifacts.artifact_id", ondelete="CASCADE", name="fk_da_feature_sets_artifact_id"),
		primary_key=True,
	)
	feature_set_id: Mapped[str] = mapped_column(
		String(36),
		ForeignKey("feature_sets.feature_set_id", ondelete="CASCADE", name="fk_da_feature_sets_set_id"),
		primary_key=True,
	)


class DatasetArtifactFeatureModel(Base):
	"""Lineage record of each individual feature materialized or skipped for a DatasetArtifact."""

	__tablename__ = "dataset_artifact_features"

	artifact_id: Mapped[str] = mapped_column(
		String(36),
		ForeignKey("dataset_artifacts.artifact_id", ondelete="CASCADE", name="fk_da_features_artifact_id"),
		primary_key=True,
	)
	feature_key: Mapped[str] = mapped_column(String(100), primary_key=True)
	feature_id: Mapped[Optional[str]] = mapped_column(
		String(36),
		ForeignKey("features.feature_id", ondelete="SET NULL", name="fk_da_features_feature_id"),
		nullable=True,
		index=True,
	)
	source_feature_set_id: Mapped[Optional[str]] = mapped_column(
		String(36),
		ForeignKey("feature_sets.feature_set_id", ondelete="SET NULL", name="fk_da_features_source_set_id"),
		nullable=True,
		index=True,
	)
	status: Mapped[str] = mapped_column(String(32), nullable=False, default="APPLIED")


__all__ = [
	"DatasetArtifactFeatureModel",
	"DatasetArtifactFeatureSetModel",
	"FeatureDependencyModel",
	"FeatureModel",
	"FeatureSetItemModel",
	"FeatureSetModel",
]
