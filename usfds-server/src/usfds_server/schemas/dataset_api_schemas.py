from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ImportDatasetRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    file_path: str = Field(..., description="Local filesystem path to raw transaction dataset file (.csv, .parquet, .json)")
    dataset_name: Optional[str] = Field(None, max_length=100, description="Optional unique dataset name. Defaults to filename stem.")
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    project_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    contains_pii: bool = False
    data_classification: Optional[str] = "INTERNAL"



class DatasetResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    dataset_id: UUID
    project_id: UUID
    user_id: UUID
    dataset_name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    contains_pii: bool = False
    data_classification: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    latest_stage: Optional[str] = None
    latest_validation_status: Optional[str] = None
    quality_score: Optional[float] = None
    artifacts_count: int = 0


class DatasetArtifactResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    artifact_id: UUID
    dataset_id: UUID
    parent_artifact_id: Optional[UUID] = None
    pipeline_stage: str
    change_type: Optional[str] = None
    storage_path: str
    output_paths: Dict[str, str] = Field(default_factory=dict)
    checksum_sha256: Optional[str] = None
    schema_snapshot: Optional[Dict[str, Any]] = None
    row_count: Optional[int] = None
    column_count: Optional[int] = None
    validation_status: Optional[str] = None
    quality_score: Optional[float] = None
    validation_report: Optional[Dict[str, Any]] = None
    created_by: Optional[str] = None
    created_at: datetime


class LineageNodeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    stage: str
    created_at: str
    parent_id: Optional[str] = None


class LineageEdgeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source: str
    target: str


class LineageGraphResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    dataset_id: str
    nodes: List[LineageNodeResponse] = Field(default_factory=list)
    edges: List[LineageEdgeResponse] = Field(default_factory=list)


class DatasetDetailResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    dataset: DatasetResponse
    artifacts: List[DatasetArtifactResponse] = Field(default_factory=list)
    lineage: LineageGraphResponse


class ForkBranchRequest(BaseModel):
    parent_artifact_id: UUID


class ExportDatasetRequest(BaseModel):
    include_train: bool = True
    include_test: bool = True
    include_pipeline: bool = True
    include_schema: bool = True
    file_format: str = "parquet"  # "parquet" or "csv"


class DatasetPreviewResponse(BaseModel):
    artifact_id: UUID
    split: str
    row_count: int
    columns: List[str]
    rows: List[Dict[str, Any]]


__all__ = [
    "ImportDatasetRequest",
    "DatasetCreateRequest",
    "DatasetResponse",
    "DatasetArtifactResponse",
    "DatasetDetailResponse",
    "ForkBranchRequest",
    "ExportDatasetRequest",
    "DatasetPreviewResponse",
]
