from pathlib import Path
from typing import Any, Dict, List, Union
import pandas as pd

from usfds_core.domain.schemas.dataset_profiling import (
    DatasetProfilingSummary,
    FieldProfilingSummary,
)
from usfds_core.services.data_management.duckdb_io import (
    create_utc_bounded_duckdb_connection,
    duckdb_type_to_physical_dtype,
    quote_ident,
    register_file_view,
)

_FLOAT_TYPES = {"FLOAT", "FLOAT4", "FLOAT8", "DOUBLE", "REAL"}
_MAX_DISTINCT_VALUES = 20


class DataProfilingService:
    """Service providing core tabular data profiling statistics."""

    @staticmethod
    def _format_distinct_scalar(val: Any) -> str:
        if hasattr(val, "item") and not isinstance(val, (bytes, str)):
            val = val.item()
        if isinstance(val, bool):
            return "true" if val else "false"
        return str(val).strip()

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

            distinct_values: List[str] = []
            if 1 <= unique_count <= _MAX_DISTINCT_VALUES:
                try:
                    raw_uniques = series.dropna().unique().tolist()
                    distinct_values = sorted(
                        {
                            formatted
                            for item in raw_uniques
                            if (formatted := self._format_distinct_scalar(item)) != ""
                        }
                    )[:_MAX_DISTINCT_VALUES]
                except Exception:
                    distinct_values = []

            fields.append(
                FieldProfilingSummary(
                    name=str(col),
                    dtype=str(series.dtype),
                    unique_count=unique_count,
                    null_count=null_count,
                    null_percentage=null_percentage,
                    distinct_values=distinct_values,
                )
            )

        return DatasetProfilingSummary(
            row_count=row_count,
            field_count=field_count,
            field_names=field_names,
            fields=fields,
        )

    def analyze_duckdb(self, conn: Any, view_name: str = "src") -> DatasetProfilingSummary:
        """Analyzes a registered DuckDB view without materializing a pandas DataFrame."""
        v = quote_ident(view_name)
        described = conn.execute(f"DESCRIBE SELECT * FROM {v}").fetchall()
        field_names: List[str] = [str(row[0]) for row in described]
        col_types: Dict[str, str] = {str(row[0]): str(row[1]) for row in described}
        field_count = len(field_names)

        row_count = int(conn.execute(f"SELECT COUNT(*) FROM {v}").fetchone()[0])

        non_null_counts: Dict[str, int] = {}
        unique_counts: Dict[str, int] = {}
        batch_size = 50
        for idx in range(0, field_count, batch_size):
            batch = field_names[idx : idx + batch_size]
            exprs: List[str] = []
            for col in batch:
                c = quote_ident(col)
                exprs.append(f"COUNT({c})")
                exprs.append(f"COUNT(DISTINCT {c})")
            try:
                row = conn.execute(f"SELECT {', '.join(exprs)} FROM {v}").fetchone()
                for c_idx, col in enumerate(batch):
                    non_null_counts[col] = int(row[c_idx * 2] or 0) if row else 0
                    unique_counts[col] = int(row[c_idx * 2 + 1] or 0) if row else 0
            except Exception:
                # Fallback per column (e.g. unhashable/complex nested types)
                for col in batch:
                    c = quote_ident(col)
                    try:
                        r_single = conn.execute(f"SELECT COUNT({c}), COUNT(DISTINCT {c}) FROM {v}").fetchone()
                    except Exception:
                        r_single = conn.execute(
                            f"SELECT COUNT({c}), COUNT(DISTINCT CAST({c} AS VARCHAR)) FROM {v}"
                        ).fetchone()
                    non_null_counts[col] = int(r_single[0] or 0) if r_single else 0
                    unique_counts[col] = int(r_single[1] or 0) if r_single else 0

        fields: List[FieldProfilingSummary] = []
        for col in field_names:
            null_count = max(0, row_count - non_null_counts.get(col, 0))
            null_percentage = (
                round((null_count / row_count) * 100.0, 2) if row_count > 0 else 0.0
            )
            uniq_cnt = unique_counts.get(col, 0)
            distinct_values: List[str] = []
            if 1 <= uniq_cnt <= _MAX_DISTINCT_VALUES:
                c = quote_ident(col)
                t_up = col_types[col].strip().upper()
                if t_up in _FLOAT_TYPES:
                    where_cond = f"{c} IS NOT NULL AND NOT isnan({c}) AND trim(CAST({c} AS VARCHAR)) != ''"
                else:
                    where_cond = f"{c} IS NOT NULL AND trim(CAST({c} AS VARCHAR)) != ''"
                try:
                    rows = conn.execute(
                        f"SELECT DISTINCT trim(CAST({c} AS VARCHAR)) AS val "
                        f"FROM {v} WHERE {where_cond} ORDER BY 1 LIMIT {_MAX_DISTINCT_VALUES}"
                    ).fetchall()
                    distinct_values = [str(r[0]) for r in rows if r and r[0] is not None]
                except Exception:
                    distinct_values = []

            fields.append(
                FieldProfilingSummary(
                    name=col,
                    dtype=duckdb_type_to_physical_dtype(col_types[col]),
                    unique_count=uniq_cnt,
                    null_count=null_count,
                    null_percentage=null_percentage,
                    distinct_values=distinct_values,
                )
            )

        return DatasetProfilingSummary(
            row_count=row_count,
            field_count=field_count,
            field_names=field_names,
            fields=fields,
        )

    def analyze_file(self, file_path: Union[str, Path]) -> DatasetProfilingSummary:
        """Analyzes a tabular file on disk using a bounded DuckDB connection."""
        conn = create_utc_bounded_duckdb_connection()
        try:
            register_file_view(conn, file_path, view_name="src", source_hint=str(file_path))
            return self.analyze_duckdb(conn, view_name="src")
        finally:
            conn.close()
