from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from usfds_core.domain.entities.enums import LogicalDataType


class ColumnSchemaSpec(BaseModel):
    """Specification of a single column in the Project's RAW schema."""
    model_config = ConfigDict(extra="ignore")

    logical_type: LogicalDataType
    physical_dtype: str
    nullable: bool = True


class ProjectRawSchema(BaseModel):
    """Project-level RAW data schema contract locked on first dataset upload."""
    model_config = ConfigDict(extra="ignore")

    version: int = 1
    locked_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    source_dataset_id: Optional[str] = None
    columns: Dict[str, ColumnSchemaSpec] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "locked_at": self.locked_at,
            "source_dataset_id": self.source_dataset_id,
            "columns": {
                col: {
                    "logical_type": str(spec.logical_type.value if hasattr(spec.logical_type, "value") else spec.logical_type),
                    "physical_dtype": spec.physical_dtype,
                    "nullable": spec.nullable,
                }
                for col, spec in self.columns.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectRawSchema":
        cols_raw = data.get("columns", {}) or {}
        columns: Dict[str, ColumnSchemaSpec] = {}
        for col_name, spec_dict in cols_raw.items():
            if isinstance(spec_dict, ColumnSchemaSpec):
                columns[col_name] = spec_dict
            elif isinstance(spec_dict, dict):
                ltype_val = spec_dict.get("logical_type", LogicalDataType.STRING.value)
                try:
                    ltype = LogicalDataType(ltype_val)
                except ValueError:
                    ltype = LogicalDataType.STRING
                columns[col_name] = ColumnSchemaSpec(
                    logical_type=ltype,
                    physical_dtype=str(spec_dict.get("physical_dtype", "object")),
                    nullable=bool(spec_dict.get("nullable", True)),
                )
        return cls(
            version=int(data.get("version", 1)),
            locked_at=str(data.get("locked_at", datetime.now(timezone.utc).isoformat())),
            source_dataset_id=data.get("source_dataset_id"),
            columns=columns,
        )


class SchemaValidationResult(BaseModel):
    """Result of validating a new DataFrame against a locked ProjectRawSchema."""
    is_valid: bool = True
    missing_columns: List[str] = Field(default_factory=list)
    extra_columns: List[str] = Field(default_factory=list)
    type_mismatches: List[Dict[str, str]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    inferred_unlabeled_inference: bool = False


__all__ = [
    "ColumnSchemaSpec",
    "ProjectRawSchema",
    "SchemaValidationResult",
]
