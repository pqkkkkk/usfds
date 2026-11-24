"""Pydantic DSL schemas and DTOs for Feature Management & Compatibility (ISS-040)."""
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


VelocityAggFn = Literal[
	"COUNT",
	"SUM",
	"AVG",
	"STD",
	"MIN",
	"MAX",
	"NUNIQUE",
	"LAG_SECONDS",
	"IS_FIRST",
	"SEQ_NUM",
]
VelocityWindow = Literal["5m", "1h", "6h", "24h", "7d", "30d", "90d", "same_day", "lifetime"]


class VelocitySpec(BaseModel):
	"""Tier 1 declarative rolling/behavioral aggregation compiled to DuckDB SQL."""

	model_config = ConfigDict(extra="allow")

	entity_key: str = "user_id"
	secondary_group_by: Optional[str] = None
	metric_col: Optional[str] = None
	agg_fn: VelocityAggFn = "COUNT"
	window: VelocityWindow = "1h"
	include_current: bool = True
	time_col: str = "timestamp"


class ExpressionSpec(BaseModel):
	"""Tier 1 safe expression compiled via AST whitelist to DuckDB SQL."""

	model_config = ConfigDict(extra="allow")

	expr: str


class TargetRateSpec(BaseModel):
	"""Tier 1 Laplace-smoothed historical target encoding fitted strictly on train."""

	model_config = ConfigDict(extra="allow")

	group_col: str
	smoothing_m: float = Field(default=10.0, ge=0.0)


class PythonCodeSpec(BaseModel):
	"""Optional metadata config companion for PYTHON_CODE features."""

	model_config = ConfigDict(extra="allow")

	required_packages: List[str] = Field(default_factory=list)
	params: Dict[str, Any] = Field(default_factory=dict)


class FeatureCompatibilityItem(BaseModel):
	"""Per-feature compatibility evaluation result for a given dataset/project schema."""

	feature_id: UUID
	feature_key: str
	display_name: str
	megafamily: str
	compute_kind: str
	output_type: str
	is_builtin: bool
	requires_label: bool = False
	status: Literal["AVAILABLE", "MISSING_INPUTS", "MISSING_DEPENDENCY"]
	missing_inputs: List[str] = Field(default_factory=list)
	missing_dependencies: List[str] = Field(default_factory=list)
	missing_packages: List[str] = Field(default_factory=list)


class FeatureCompatibilityReport(BaseModel):
	"""Aggregated compatibility report across candidate features."""

	available_columns: List[str] = Field(default_factory=list)
	items: List[FeatureCompatibilityItem] = Field(default_factory=list)
	available_count: int = 0
	unavailable_count: int = 0


class FeaturePreviewResult(BaseModel):
	"""Preview execution output for a feature over a sample of a MAPPED artifact."""

	feature_key: str
	output_type: str
	sample_rows: List[Dict[str, Any]] = Field(default_factory=list)
	stats: Dict[str, Any] = Field(default_factory=dict)
	warnings: List[str] = Field(default_factory=list)
	execution_time_ms: float = 0.0


__all__ = [
	"ExpressionSpec",
	"FeatureCompatibilityItem",
	"FeatureCompatibilityReport",
	"FeaturePreviewResult",
	"PythonCodeSpec",
	"TargetRateSpec",
	"VelocityAggFn",
	"VelocitySpec",
	"VelocityWindow",
]
