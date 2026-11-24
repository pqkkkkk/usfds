"""Domain entities for Feature Management and Feature Sets (ISS-040)."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from usfds_core.domain.entities.enums import (
	FeatureComputeKind,
	FeatureMegafamily,
	FeatureStatus,
	LogicalDataType,
)


@dataclass
class Feature:
	"""Dynamic 2-tier feature definition stored self-contained in the registry."""

	feature_key: str
	display_name: str
	megafamily: FeatureMegafamily
	compute_kind: FeatureComputeKind
	output_type: LogicalDataType = LogicalDataType.NUMERIC
	feature_id: UUID = field(default_factory=uuid4)
	project_id: Optional[UUID] = None
	user_id: Optional[UUID] = None
	description: Optional[str] = None
	is_stateful: bool = False
	requires_label: bool = False
	config_json: Dict[str, Any] = field(default_factory=dict)
	source_code: Optional[str] = None
	required_inputs: List[str] = field(default_factory=list)
	depends_on_feature_ids: List[UUID] = field(default_factory=list)
	status: FeatureStatus = FeatureStatus.ACTIVE
	created_by: Optional[str] = None
	created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
	updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

	@property
	def is_builtin(self) -> bool:
		"""Built-in features are identified solely by project_id is None."""
		return self.project_id is None

	def to_dict(self) -> Dict[str, Any]:
		"""Serializes into a plain JSON-friendly dict for worker payloads and snapshots."""
		return {
			"feature_id": str(self.feature_id),
			"project_id": str(self.project_id) if self.project_id is not None else None,
			"user_id": str(self.user_id) if self.user_id is not None else None,
			"feature_key": self.feature_key,
			"display_name": self.display_name,
			"description": self.description,
			"megafamily": self.megafamily.value if hasattr(self.megafamily, "value") else str(self.megafamily),
			"compute_kind": self.compute_kind.value if hasattr(self.compute_kind, "value") else str(self.compute_kind),
			"output_type": self.output_type.value if hasattr(self.output_type, "value") else str(self.output_type),
			"is_stateful": bool(self.is_stateful),
			"requires_label": bool(self.requires_label),
			"config_json": dict(self.config_json or {}),
			"source_code": self.source_code,
			"required_inputs": list(self.required_inputs or []),
			"depends_on_feature_ids": [str(dep) for dep in (self.depends_on_feature_ids or [])],
			"status": self.status.value if hasattr(self.status, "value") else str(self.status),
			"is_builtin": self.is_builtin,
		}

	@classmethod
	def from_dict(cls, data: Dict[str, Any]) -> "Feature":
		"""Hydrates a Feature instance from a plain dictionary."""
		return cls(
			feature_id=UUID(str(data["feature_id"])) if data.get("feature_id") else uuid4(),
			project_id=UUID(str(data["project_id"])) if data.get("project_id") else None,
			user_id=UUID(str(data["user_id"])) if data.get("user_id") else None,
			feature_key=str(data["feature_key"]),
			display_name=str(data.get("display_name") or data["feature_key"]),
			description=data.get("description"),
			megafamily=FeatureMegafamily(str(data.get("megafamily", FeatureMegafamily.ORDERS.value))),
			compute_kind=FeatureComputeKind(str(data.get("compute_kind", FeatureComputeKind.EXPRESSION.value))),
			output_type=LogicalDataType(str(data.get("output_type", LogicalDataType.NUMERIC.value))),
			is_stateful=bool(data.get("is_stateful", False)),
			requires_label=bool(data.get("requires_label", False)),
			config_json=dict(data.get("config_json") or {}),
			source_code=data.get("source_code"),
			required_inputs=[str(x) for x in (data.get("required_inputs") or [])],
			depends_on_feature_ids=[UUID(str(d)) for d in (data.get("depends_on_feature_ids") or [])],
			status=FeatureStatus(str(data.get("status", FeatureStatus.ACTIVE.value))),
			created_by=data.get("created_by"),
		)


@dataclass
class FeatureSetItem:
	"""Ordered link between a FeatureSet and a Feature."""

	feature_id: UUID
	display_order: int = 0


@dataclass
class FeatureSet:
	"""Named bundle of features (e.g., Built-in Domain Package or Custom Set)."""

	set_key: str
	name: str
	feature_set_id: UUID = field(default_factory=uuid4)
	project_id: Optional[UUID] = None
	user_id: Optional[UUID] = None
	description: Optional[str] = None
	domain_tag: str = "CUSTOM"
	default_config: Dict[str, Any] = field(default_factory=dict)
	feature_ids: List[UUID] = field(default_factory=list)
	created_by: Optional[str] = None
	created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
	updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

	@property
	def is_builtin(self) -> bool:
		"""Built-in feature sets have project_id is None."""
		return self.project_id is None


@dataclass
class DatasetArtifactFeatureLink:
	"""Materialized feature lineage record attached to a FEATURE_ENGINEERED DatasetArtifact."""

	artifact_id: UUID
	feature_key: str
	feature_id: Optional[UUID] = None
	source_feature_set_id: Optional[UUID] = None
	status: str = "APPLIED"


__all__ = [
	"DatasetArtifactFeatureLink",
	"Feature",
	"FeatureSet",
	"FeatureSetItem",
]
