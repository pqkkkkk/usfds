from typing import List
import pandas as pd

from usfds_core.domain.schemas.dataset_profiling import (
    DatasetProfilingSummary,
    FieldProfilingSummary,
)


class DataProfilingService:
    """Service providing core tabular data profiling statistics."""

    def analyze(self, df: pd.DataFrame) -> DatasetProfilingSummary:
        """Analyzes a pandas DataFrame and generates basic data profiling statistics.

        Metrics calculated:
        - field_count: Total number of fields/columns
        - field_names: Ordered list of field names
        - row_count: Total number of rows/records
        - Per-field metrics:
            - name: Column name
            - dtype: Data type string
            - unique_count: Number of distinct/unique values
            - null_count: Number of missing/null values
            - null_percentage: Percentage of null values (0.0 - 100.0)
        """
        row_count = len(df)
        field_names: List[str] = [str(col) for col in df.columns]
        field_count = len(field_names)

        fields: List[FieldProfilingSummary] = []
        for col in df.columns:
            series = df[col]
            null_count = int(series.isna().sum())
            null_percentage = (
                round((null_count / row_count) * 100.0, 2) if row_count > 0 else 0.0
            )

            try:
                unique_count = int(series.nunique(dropna=True))
            except TypeError:
                # Handle columns containing unhashable objects (e.g. lists/dicts)
                unique_count = int(series.astype(str).nunique(dropna=True))

            fields.append(
                FieldProfilingSummary(
                    name=str(col),
                    dtype=str(series.dtype),
                    unique_count=unique_count,
                    null_count=null_count,
                    null_percentage=null_percentage,
                )
            )

        return DatasetProfilingSummary(
            row_count=row_count,
            field_count=field_count,
            field_names=field_names,
            fields=fields,
        )

