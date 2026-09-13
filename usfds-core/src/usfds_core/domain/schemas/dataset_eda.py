from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FieldEdaSummary(BaseModel):
    """Statistical and profiling summary for an individual dataset field/feature."""
    name: str = Field(..., description="Name of the field/column.")
    dtype: str = Field(..., description="Pandas/Numpy data type of the field.")
    unique_count: int = Field(..., description="Count of distinct/unique values in this field.")
    null_count: int = Field(..., description="Count of missing/null values in this field.")
    null_percentage: float = Field(..., description="Percentage of missing values relative to total rows (0.0 - 100.0).")


class DatasetEdaSummary(BaseModel):
    """Exploratory Data Analysis (EDA) summary for an entire dataset."""
    row_count: int = Field(..., description="Total number of records/rows in the dataset.")
    field_count: int = Field(..., description="Total number of fields/columns in the dataset.")
    field_names: List[str] = Field(..., description="Ordered list of field names.")
    fields: List[FieldEdaSummary] = Field(..., description="Detailed profile metrics for each field.")

    def get_field(self, name: str) -> Optional[FieldEdaSummary]:
        """Lookup a field summary by its column name."""
        for field in self.fields:
            if field.name == name:
                return field
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize EDA summary into dictionary representation."""
        return self.model_dump()


__all__ = ["FieldEdaSummary", "DatasetEdaSummary"]
