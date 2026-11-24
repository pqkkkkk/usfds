"""Pydantic REST API DTOs for Feature Management and Feature Sets (ISS-040)."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from usfds_core.domain.entities.enums import (
	FeatureComputeKind,
	FeatureMegafamily,
	FeatureStatus,
	LogicalDataType,
)
from usfds_server.schemas.base_response import ResourceOwnerDto


class CreateFeatureRequest(BaseModel):
	project_id: UUID
	feature_key: str = Field(..., min_length=2, max_length=96)
	display_name: str = Field(..., min_length=1, max_length=200)
	description: Optional[str] = Field(default=None, max_length=2000)
	megafamily: FeatureMegafamily = FeatureMegafamily.MONETARY
	compute_kind: FeatureComputeKind = FeatureComputeKind.EXPRESSION
	output_type: LogicalDataType = LogicalDataType.NUMERIC
	is_stateful: bool = False
	requires_label: bool = False
	config_json: Dict[str, Any] = Field(default_factory=dict)
	source_code: Optional[str] = None
	required_inputs: List[str] = Field(default_factory=list)
	depends_on_feature_ids: List[UUID] = Field(default_factory=list)
	status: FeatureStatus = FeatureStatus.ACTIVE


class UpdateFeatureRequest(BaseModel):
	display_name: Optional[str] = None
	description: Optional[str] = None
	megafamily: Optional[FeatureMegafamily] = None
	output_type: Optional[LogicalDataType] = None
	is_stateful: Optional[bool] = None
	requires_label: Optional[bool] = None
	config_json: Optional[Dict[str, Any]] = None
	source_code: Optional[str] = None
	required_inputs: Optional[List[str]] = None
	depends_on_feature_ids: Optional[List[UUID]] = None
	status: Optional[FeatureStatus] = None


class CloneFeatureRequest(BaseModel):
	new_feature_key: Optional[str] = None
	new_display_name: Optional[str] = None


class PreviewFeatureRequest(BaseModel):
	project_id: UUID
	artifact_id: UUID
	feature_id: Optional[UUID] = None
	feature_spec: Optional[Dict[str, Any]] = None


class FeatureResponse(BaseModel):
	feature_id: UUID
	project_id: Optional[UUID] = None
	user_id: Optional[UUID] = None
	owner: Optional[ResourceOwnerDto] = None
	is_builtin: bool
	feature_key: str
	display_name: str
	description: Optional[str] = None
	megafamily: str
	compute_kind: str
	output_type: str
	is_stateful: bool
	requires_label: bool
	config_json: Dict[str, Any] = Field(default_factory=dict)
	source_code: Optional[str] = None
	compiled_sql_preview: Optional[str] = None
	required_inputs: List[str] = Field(default_factory=list)
	depends_on_feature_ids: List[UUID] = Field(default_factory=list)
	status: str
	created_by: Optional[str] = None
	created_at: datetime
	updated_at: datetime


class FeatureCompatibilityItemResponse(BaseModel):
	feature_id: UUID
	feature_key: str
	display_name: str
	megafamily: str
	compute_kind: str
	output_type: str
	is_builtin: bool
	requires_label: bool
	status: str
	missing_inputs: List[str] = Field(default_factory=list)
	missing_dependencies: List[str] = Field(default_factory=list)
	missing_packages: List[str] = Field(default_factory=list)


class FeatureCompatibilityReportResponse(BaseModel):
	available_columns: List[str] = Field(default_factory=list)
	items: List[FeatureCompatibilityItemResponse] = Field(default_factory=list)
	available_count: int
	unavailable_count: int


class FeaturePreviewResponse(BaseModel):
	feature_key: str
	output_type: str
	sample_rows: List[Dict[str, Any]] = Field(default_factory=list)
	stats: Dict[str, Any] = Field(default_factory=dict)
	warnings: List[str] = Field(default_factory=list)
	execution_time_ms: float


class CreateFeatureSetRequest(BaseModel):
	project_id: UUID
	set_key: str = Field(..., min_length=2, max_length=96)
	name: str = Field(..., min_length=1, max_length=200)
	description: Optional[str] = Field(default=None, max_length=2000)
	domain_tag: str = "CUSTOM"
	default_config: Dict[str, Any] = Field(default_factory=dict)
	feature_ids: List[UUID] = Field(default_factory=list)


class UpdateFeatureSetRequest(BaseModel):
	name: Optional[str] = None
	description: Optional[str] = None
	domain_tag: Optional[str] = None
	default_config: Optional[Dict[str, Any]] = None
	feature_ids: Optional[List[UUID]] = None


class FeatureSetResponse(BaseModel):
	feature_set_id: UUID
	project_id: Optional[UUID] = None
	user_id: Optional[UUID] = None
	owner: Optional[ResourceOwnerDto] = None
	is_builtin: bool
	set_key: str
	name: str
	description: Optional[str] = None
	domain_tag: str
	default_config: Dict[str, Any] = Field(default_factory=dict)
	feature_ids: List[UUID] = Field(default_factory=list)
	created_by: Optional[str] = None
	created_at: datetime
	updated_at: datetime
