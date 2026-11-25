from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union
from uuid import UUID
import pandas as pd

from usfds_core.domain.entities.enums import LogicalDataType
from usfds_core.domain.schemas.project_schema import (
    ColumnSchemaSpec,
    ProjectRawSchema,
    SchemaValidationResult,
)
from usfds_core.services.data_management.duckdb_io import (
    duckdb_type_to_logical_type,
    duckdb_type_to_physical_dtype,
    quote_ident,
)


class ProjectSchemaValidator:
    """Service responsible for extracting, locking, and validating Project-level RAW schemas (BR-PM-01, BR-PM-02, BR-PM-05)."""

    NUMERIC_COMPARISON_OPERATORS = {">", ">=", "<", "<="}

    @classmethod
    def infer_logical_type(cls, series_or_dtype: Any) -> LogicalDataType:
        """Maps a Pandas Series or dtype to one of the 4 canonical LogicalDataTypes."""
        dtype = series_or_dtype.dtype if isinstance(series_or_dtype, pd.Series) else series_or_dtype
        dtype_str = str(dtype).lower()

        if pd.api.types.is_bool_dtype(dtype) or dtype_str in ("bool", "boolean"):
            return LogicalDataType.BOOLEAN

        if pd.api.types.is_datetime64_any_dtype(dtype) or "datetime" in dtype_str:
            return LogicalDataType.DATETIME

        if pd.api.types.is_numeric_dtype(dtype) or any(
            dtype_str.startswith(prefix) for prefix in ("int", "uint", "float", "decimal")
        ):
            return LogicalDataType.NUMERIC

        return LogicalDataType.STRING

    @classmethod
    def extract_raw_schema(
        cls,
        df: pd.DataFrame,
        source_dataset_id: Optional[Union[UUID, str]] = None,
    ) -> ProjectRawSchema:
        """Extracts a ProjectRawSchema from the first uploaded RAW DataFrame."""
        columns: Dict[str, ColumnSchemaSpec] = {}
        for col in df.columns:
            col_name = str(col)
            series = df[col]
            logical_type = cls.infer_logical_type(series)
            physical_dtype = str(series.dtype)
            # In RAW schema governance, columns are marked nullable by default unless strictly non-null
            nullable = bool(series.isna().any())
            columns[col_name] = ColumnSchemaSpec(
                logical_type=logical_type,
                physical_dtype=physical_dtype,
                nullable=nullable,
            )

        return ProjectRawSchema(
            version=1,
            source_dataset_id=str(source_dataset_id) if source_dataset_id else None,
            columns=columns,
        )

    @classmethod
    def _are_logical_types_compatible(
        cls,
        expected: LogicalDataType,
        actual: LogicalDataType,
        series: Optional[pd.Series] = None,
    ) -> bool:
        """Determines whether an actual column's logical type is compatible with the expected logical type."""
        if expected == actual:
            return True

        # If column is 100% null/NaN in the new dataset, Pandas may type it as float64 or object
        if series is not None and series.isna().all():
            return True

        # DATETIME columns in raw CSVs are often loaded as STRING (object)
        if expected == LogicalDataType.DATETIME and actual == LogicalDataType.STRING:
            return True
        if expected == LogicalDataType.STRING and actual == LogicalDataType.DATETIME:
            return True

        # BOOLEAN flags (True/False vs 0/1)
        if {expected, actual} == {LogicalDataType.BOOLEAN, LogicalDataType.NUMERIC}:
            if series is not None:
                non_null = series.dropna().unique()
                if set(non_null).issubset({0, 1, 0.0, 1.0, True, False}):
                    return True

        return False

    @classmethod
    def validate_dataframe(
        cls,
        df: pd.DataFrame,
        raw_schema: Union[ProjectRawSchema, Dict[str, Any]],
        allow_missing_target: bool = True,
    ) -> SchemaValidationResult:
        """Validates an incoming DataFrame against the locked ProjectRawSchema (BR-PM-02).

        Rules:
        1. Column Coverage:
           - Must contain all columns in `raw_schema`, OR at most 1 missing column when `allow_missing_target=True`
             (to support unlabeled INFERENCE datasets).
           - Extra columns are tolerated with a WARNING (Superset Tolerance).
        2. Logical Type Compatibility:
           - Every shared column must match the expected `LogicalDataType` (e.g. int64 and float64 both match NUMERIC).
        """
        schema = (
            raw_schema
            if isinstance(raw_schema, ProjectRawSchema)
            else ProjectRawSchema.from_dict(raw_schema)
        )

        result = SchemaValidationResult(is_valid=True)
        expected_cols = list(schema.columns.keys())
        expected_set = set(expected_cols)
        actual_cols = [str(c) for c in df.columns]
        actual_set = set(actual_cols)

        missing_cols = [c for c in expected_cols if c not in actual_set]
        extra_cols = [c for c in actual_cols if c not in expected_set]

        result.missing_columns = missing_cols
        result.extra_columns = extra_cols

        if len(missing_cols) == 1 and allow_missing_target:
            result.inferred_unlabeled_inference = True
            result.warnings.append(
                f"Khuyết 1 cột '{missing_cols[0]}' so với RAW schema của dự án (được chấp nhận như tập dữ liệu Inference không nhãn)."
            )
        elif len(missing_cols) > 0:
            result.is_valid = False
            result.errors.append(
                f"Tập dữ liệu thiếu {len(missing_cols)} cột bắt buộc theo RAW schema của dự án: {', '.join(missing_cols)}."
            )

        if extra_cols:
            result.warnings.append(
                f"Tập dữ liệu có {len(extra_cols)} cột dư ngoài RAW schema của dự án ({', '.join(extra_cols)})."
            )

        # Validate Logical DataTypes on shared columns
        for col_name in expected_cols:
            if col_name not in df.columns:
                continue
            spec = schema.columns[col_name]
            series = df[col_name]
            actual_logical = cls.infer_logical_type(series)

            if not cls._are_logical_types_compatible(spec.logical_type, actual_logical, series):
                result.is_valid = False
                mismatch = {
                    "column": col_name,
                    "expected_logical_type": str(spec.logical_type.value),
                    "actual_logical_type": str(actual_logical.value),
                    "actual_physical_dtype": str(series.dtype),
                }
                result.type_mismatches.append(mismatch)
                result.errors.append(
                    f"Cột '{col_name}' có kiểu dữ liệu '{actual_logical.value}' ({series.dtype}) "
                    f"không tương thích với kiểu '{spec.logical_type.value}' trong RAW schema của dự án."
                )

        return result

    @classmethod
    def extract_raw_schema_from_duckdb(
        cls,
        conn: Any,
        view_name: str,
        source_dataset_id: Optional[Union[UUID, str]] = None,
    ) -> ProjectRawSchema:
        """Extracts a ProjectRawSchema from a registered DuckDB view without loading into pandas."""
        v = quote_ident(view_name)
        described = conn.execute(f"DESCRIBE SELECT * FROM {v}").fetchall()
        col_types = [(str(row[0]), str(row[1])) for row in described]

        nullable_map: Dict[str, bool] = {}
        batch_size = 50
        for idx in range(0, len(col_types), batch_size):
            batch = col_types[idx : idx + batch_size]
            exprs = [f"(COUNT(*) - COUNT({quote_ident(col_name)})) > 0" for col_name, _ in batch]
            row = conn.execute(f"SELECT {', '.join(exprs)} FROM {v}").fetchone()
            for col_idx, (col_name, _) in enumerate(batch):
                nullable_map[col_name] = bool(row[col_idx]) if row is not None else True

        columns: Dict[str, ColumnSchemaSpec] = {}
        for col_name, dtype_str in col_types:
            columns[col_name] = ColumnSchemaSpec(
                logical_type=duckdb_type_to_logical_type(dtype_str),
                physical_dtype=duckdb_type_to_physical_dtype(dtype_str),
                nullable=nullable_map.get(col_name, True),
            )

        return ProjectRawSchema(
            version=1,
            source_dataset_id=str(source_dataset_id) if source_dataset_id else None,
            columns=columns,
        )

    @classmethod
    def validate_duckdb_view(
        cls,
        conn: Any,
        view_name: str,
        raw_schema: Union[ProjectRawSchema, Dict[str, Any]],
        allow_missing_target: bool = True,
    ) -> SchemaValidationResult:
        """Validates a DuckDB view against the locked ProjectRawSchema (BR-PM-02) without pandas."""
        schema = (
            raw_schema
            if isinstance(raw_schema, ProjectRawSchema)
            else ProjectRawSchema.from_dict(raw_schema)
        )

        v = quote_ident(view_name)
        described = conn.execute(f"DESCRIBE SELECT * FROM {v}").fetchall()
        actual_cols = [str(row[0]) for row in described]
        actual_types = {str(row[0]): str(row[1]) for row in described}

        result = SchemaValidationResult(is_valid=True)
        expected_cols = list(schema.columns.keys())
        expected_set = set(expected_cols)
        actual_set = set(actual_cols)

        missing_cols = [c for c in expected_cols if c not in actual_set]
        extra_cols = [c for c in actual_cols if c not in expected_set]

        result.missing_columns = missing_cols
        result.extra_columns = extra_cols

        if len(missing_cols) == 1 and allow_missing_target:
            result.inferred_unlabeled_inference = True
            result.warnings.append(
                f"Khuyết 1 cột '{missing_cols[0]}' so với RAW schema của dự án (được chấp nhận như tập dữ liệu Inference không nhãn)."
            )
        elif len(missing_cols) > 0:
            result.is_valid = False
            result.errors.append(
                f"Tập dữ liệu thiếu {len(missing_cols)} cột bắt buộc theo RAW schema của dự án: {', '.join(missing_cols)}."
            )

        if extra_cols:
            result.warnings.append(
                f"Tập dữ liệu có {len(extra_cols)} cột dư ngoài RAW schema của dự án ({', '.join(extra_cols)})."
            )

        candidate_cols: List[Tuple[str, LogicalDataType, LogicalDataType, str]] = []
        for col_name in expected_cols:
            if col_name not in actual_types:
                continue
            spec = schema.columns[col_name]
            dtype_str = actual_types[col_name]
            actual_logical = duckdb_type_to_logical_type(dtype_str)

            if spec.logical_type == actual_logical:
                continue
            if {spec.logical_type, actual_logical} == {LogicalDataType.DATETIME, LogicalDataType.STRING}:
                continue
            if spec.logical_type == LogicalDataType.NUMERIC and actual_logical == LogicalDataType.BOOLEAN:
                continue
            candidate_cols.append((col_name, spec.logical_type, actual_logical, dtype_str))

        if candidate_cols:
            batch_size = 25
            for idx in range(0, len(candidate_cols), batch_size):
                batch = candidate_cols[idx : idx + batch_size]
                exprs: List[str] = []
                for col_name, expected_ltype, actual_ltype, _ in batch:
                    col_ident = quote_ident(col_name)
                    exprs.append(f"COUNT({col_ident})")
                    if expected_ltype == LogicalDataType.BOOLEAN and actual_ltype == LogicalDataType.NUMERIC:
                        exprs.append(
                            f"SUM(CASE WHEN {col_ident} IS NOT NULL "
                            f"AND (TRY_CAST({col_ident} AS DOUBLE) IS NULL "
                            f"OR TRY_CAST({col_ident} AS DOUBLE) NOT IN (0.0, 1.0)) THEN 1 ELSE 0 END)"
                        )
                    else:
                        exprs.append("NULL")
                row = conn.execute(f"SELECT {', '.join(exprs)} FROM {v}").fetchone()
                for c_idx, (col_name, expected_ltype, actual_ltype, dtype_str) in enumerate(batch):
                    non_null_count = int(row[c_idx * 2] or 0) if row else 0
                    if non_null_count == 0:
                        continue
                    if expected_ltype == LogicalDataType.BOOLEAN and actual_ltype == LogicalDataType.NUMERIC:
                        bad_binary = int(row[c_idx * 2 + 1] or 0) if row else 0
                        if bad_binary == 0:
                            continue
                    phys_dtype = duckdb_type_to_physical_dtype(dtype_str)
                    result.is_valid = False
                    mismatch = {
                        "column": col_name,
                        "expected_logical_type": str(expected_ltype.value),
                        "actual_logical_type": str(actual_ltype.value),
                        "actual_physical_dtype": phys_dtype,
                    }
                    result.type_mismatches.append(mismatch)
                    result.errors.append(
                        f"Cột '{col_name}' có kiểu dữ liệu '{actual_ltype.value}' ({phys_dtype}) "
                        f"không tương thích với kiểu '{expected_ltype.value}' trong RAW schema của dự án."
                    )

        return result

    @classmethod
    def extract_jsonlogic_vars(cls, condition: Any) -> List[Tuple[str, Optional[str], List[Any]]]:
        """Traverses a JsonLogic condition tree and returns a list of tuples:
        (var_path, parent_operator, sibling_args)
        """
        found: List[Tuple[str, Optional[str], List[Any]]] = []

        def _walk(node: Any, parent_op: Optional[str] = None, siblings: Optional[List[Any]] = None) -> None:
            if not isinstance(node, dict) or not node:
                return
            for op, args in node.items():
                if op == "var":
                    var_path = args[0] if isinstance(args, list) and args else args
                    if isinstance(var_path, str) and var_path.strip():
                        found.append((var_path.strip(), parent_op, siblings or []))
                else:
                    arg_list = args if isinstance(args, list) else [args]
                    for item in arg_list:
                        if isinstance(item, dict):
                            _walk(item, parent_op=op, siblings=arg_list)

        _walk(condition)
        return found

    @classmethod
    def extract_enriched_feature_keys(cls, condition: Any) -> Set[str]:
        """Extracts referenced `enriched.<key>` / `enriched_features.<key>` names from JsonLogic."""
        keys: Set[str] = set()
        for var_path, _, _ in cls.extract_jsonlogic_vars(condition):
            if var_path.startswith("enriched."):
                k = var_path[len("enriched."):].strip()
                if k:
                    keys.add(k)
            elif var_path.startswith("enriched_features."):
                k = var_path[len("enriched_features."):].strip()
                if k:
                    keys.add(k)
        return keys

    @classmethod
    def validate_rule_condition(
        cls,
        condition: Dict[str, Any],
        raw_schema: Union[ProjectRawSchema, Dict[str, Any]],
        active_features: Optional[Sequence[Any]] = None,
    ) -> List[str]:
        """Validates a Rule's JsonLogic condition against the Project's RAW schema and active Features.

        Returns a list of human-readable validation error messages (empty list if valid).
        """
        if not condition or not isinstance(condition, dict):
            return ["Biểu thức điều kiện (condition) của Rule không được để trống."]

        schema = (
            raw_schema
            if isinstance(raw_schema, ProjectRawSchema)
            else ProjectRawSchema.from_dict(raw_schema)
        )
        if not schema.columns:
            return []

        active_by_key: Optional[Dict[str, Any]] = None
        if active_features is not None:
            active_by_key = {str(getattr(f, "feature_key")): f for f in active_features if getattr(f, "feature_key", None)}

        errors: List[str] = []
        var_usages = cls.extract_jsonlogic_vars(condition)

        for var_path, parent_op, siblings in var_usages:
            if var_path.startswith(("enriched.", "enriched_features.")):
                if active_by_key is None:
                    continue
                prefix = "enriched." if var_path.startswith("enriched.") else "enriched_features."
                feat_key = var_path[len(prefix):].strip()
                feat = active_by_key.get(feat_key)
                if feat is None:
                    errors.append(
                        f"Đặc trưng làm giàu '{var_path}' ('{feat_key}') không tồn tại trong Kho đặc trưng hoạt động của dự án."
                    )
                    continue
                if parent_op in cls.NUMERIC_COMPARISON_OPERATORS:
                    out_type = feat.output_type.value if hasattr(feat.output_type, "value") else str(feat.output_type)
                    has_numeric_literal = any(
                        isinstance(sib, (int, float)) and not isinstance(sib, bool)
                        for sib in siblings
                    )
                    if has_numeric_literal and out_type in (
                        LogicalDataType.STRING.value,
                        LogicalDataType.BOOLEAN.value,
                    ):
                        errors.append(
                            f"Không thể áp dụng toán tử so sánh số học '{parent_op}' cho đặc trưng '{feat_key}' có kiểu '{out_type}'."
                        )
                continue

            if var_path.startswith("raw."):
                col_name = var_path[len("raw."):]
            elif var_path.startswith("raw_features."):
                col_name = var_path[len("raw_features."):]
            elif var_path.startswith("mapped."):
                col_name = var_path[len("mapped."):]
            elif var_path.startswith("mapped_features."):
                col_name = var_path[len("mapped_features."):]
            else:
                col_name = var_path

            if col_name == "transaction_id":
                continue

            if col_name not in schema.columns:
                errors.append(
                    f"Trường '{var_path}' (cột '{col_name}') không tồn tại trong RAW schema của dự án. "
                    f"Các cột hợp lệ: {', '.join(schema.columns.keys())}."
                )
                continue

            # Check numeric comparison operator against non-numeric/non-datetime column
            col_spec = schema.columns[col_name]
            if parent_op in cls.NUMERIC_COMPARISON_OPERATORS:
                has_numeric_literal = any(
                    isinstance(sib, (int, float)) and not isinstance(sib, bool)
                    for sib in siblings
                )
                if has_numeric_literal and col_spec.logical_type in (
                    LogicalDataType.STRING,
                    LogicalDataType.BOOLEAN,
                ):
                    errors.append(
                        f"Không thể áp dụng toán tử so sánh số học '{parent_op}' cho cột '{col_name}' "
                        f"có kiểu dữ liệu '{col_spec.logical_type.value}'."
                    )

        return errors


__all__ = ["ProjectSchemaValidator"]
