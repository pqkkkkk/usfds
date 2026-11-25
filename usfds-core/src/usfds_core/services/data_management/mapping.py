from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.enums import (
    ColumnCategory,
    LogicalDataType,
    PipelineStage,
)
from usfds_core.domain.entities.system_metadata import SystemColumnMetadata
from usfds_core.domain.schemas.artifact_output import validate_stage_outputs
from usfds_core.domain.schemas.preprocessing_config import (
    DataMappingConfig,
    SupportedTimeFormat,
    SystemColumn,
)
from usfds_core.domain.schemas.system_metadata import build_non_ml_columns
from usfds_core.repositories.base_dataset_artifact_repo import IDatasetArtifactRepository
from usfds_core.repositories.base_system_metadata_repo import ISystemColumnMetadataRepository
from usfds_core.services.data_management.duckdb_io import (
    copy_query_to_file,
    create_utc_bounded_duckdb_connection,
    duckdb_type_to_physical_dtype,
    is_duckdb_datetime_type,
    quote_ident,
    quote_literal,
    register_file_view,
    sha256_file,
)
from usfds_core.services.data_management.validation import (
    DataQualityReport,
    DataQualityValidationService,
)
from usfds_core.storage.base_storage import IFileStorage

_FLOAT_TYPES = {"FLOAT", "FLOAT4", "FLOAT8", "DOUBLE", "REAL"}

_AUTO_TIME_FORMATS = (
    "['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', "
    "'%Y-%m-%d', '%Y/%m/%d %H:%M:%S', '%Y/%m/%d', "
    "'%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M', '%d/%m/%Y', "
    "'%m/%d/%Y %H:%M:%S', '%m/%d/%Y %H:%M', '%m/%d/%Y']"
)


class DataMappingService:
    """Service implementing Mapping raw schema to standardized FDS 5-core schema,

    generating mapped.parquet, and automatically executing data quality validation.
    """

    def __init__(
        self,
        file_storage: IFileStorage,
        artifact_repo: Optional[IDatasetArtifactRepository] = None,
        validation_service: Optional[DataQualityValidationService] = None,
        metadata_repo: Optional[ISystemColumnMetadataRepository] = None,
    ) -> None:
        self.file_storage = file_storage
        self.artifact_repo = artifact_repo
        self.validation_service = validation_service or DataQualityValidationService()
        self.metadata_repo = metadata_repo

    @staticmethod
    def _not_blank_sql(col_ident: str, col_type: str) -> str:
        t_up = col_type.strip().upper()
        if t_up in _FLOAT_TYPES:
            return f"{col_ident} IS NOT NULL AND NOT isnan({col_ident}) AND trim(CAST({col_ident} AS VARCHAR)) != ''"
        return f"{col_ident} IS NOT NULL AND trim(CAST({col_ident} AS VARCHAR)) != ''"

    @staticmethod
    def _timestamp_parse_sql(
        col_ident: str,
        col_type: str,
        time_format: Union[SupportedTimeFormat, str],
    ) -> str:
        fmt_str = time_format.value if isinstance(time_format, SupportedTimeFormat) else str(time_format)
        if fmt_str == SupportedTimeFormat.EPOCH_SECONDS.value:
            num_expr = f"TRY_CAST({col_ident} AS DOUBLE)"
            return (
                f"CASE WHEN {num_expr} IS NOT NULL AND isfinite({num_expr}) "
                f"THEN CAST(to_timestamp({num_expr}) AS TIMESTAMP) ELSE NULL END"
            )
        if fmt_str == SupportedTimeFormat.EPOCH_MILLIS.value:
            num_expr = f"TRY_CAST({col_ident} AS DOUBLE)"
            return (
                f"CASE WHEN {num_expr} IS NOT NULL AND isfinite({num_expr}) "
                f"THEN CAST(to_timestamp({num_expr} / 1000.0) AS TIMESTAMP) ELSE NULL END"
            )
        if fmt_str in (SupportedTimeFormat.AUTO.value, SupportedTimeFormat.ISO8601.value):
            if is_duckdb_datetime_type(col_type):
                return f"CAST(TRY_CAST({col_ident} AS TIMESTAMPTZ) AS TIMESTAMP)"
            trimmed = f"trim(CAST({col_ident} AS VARCHAR))"
            return (
                f"CAST(COALESCE("
                f"TRY_CAST({trimmed} AS TIMESTAMPTZ), "
                f"CAST(TRY_CAST({trimmed} AS TIMESTAMP) AS TIMESTAMPTZ), "
                f"CAST(try_strptime({trimmed}, {_AUTO_TIME_FORMATS}) AS TIMESTAMPTZ)"
                f") AS TIMESTAMP)"
            )
        trimmed = f"trim(CAST({col_ident} AS VARCHAR))"
        return f"try_strptime({trimmed}, {quote_literal(fmt_str)})"

    @staticmethod
    def _numeric_parse_sql(col_ident: str) -> str:
        num_expr = f"TRY_CAST({col_ident} AS DOUBLE)"
        return f"CASE WHEN {num_expr} IS NOT NULL AND isfinite({num_expr}) THEN {num_expr} ELSE NULL END"

    @staticmethod
    def _boolean_parse_sql(col_ident: str) -> str:
        norm = f"lower(trim(CAST({col_ident} AS VARCHAR)))"
        return (
            f"CASE "
            f"WHEN {col_ident} IS NULL OR trim(CAST({col_ident} AS VARCHAR)) = '' THEN NULL "
            f"WHEN {norm} IN ('true', '1', '1.0', 'yes', 'y', 't') THEN TRUE "
            f"WHEN {norm} IN ('false', '0', '0.0', 'no', 'n', 'f') THEN FALSE "
            f"ELSE NULL END"
        )

    @staticmethod
    def _serialize_metadata_snapshot(active_metadata: List[SystemColumnMetadata]) -> List[Dict[str, Any]]:
        snapshot: List[Dict[str, Any]] = []
        for meta in active_metadata:
            cat_val = meta.category.value if hasattr(meta.category, "value") else str(meta.category)
            type_val = meta.logical_type.value if hasattr(meta.logical_type, "value") else str(meta.logical_type)
            role_val = meta.ml_role.value if hasattr(meta.ml_role, "value") else str(meta.ml_role)
            snapshot.append(
                {
                    "column_key": meta.column_key,
                    "display_name": meta.display_name,
                    "category": cat_val,
                    "logical_type": type_val,
                    "is_required": bool(meta.is_required),
                    "ml_role": role_val,
                    "is_active": bool(meta.is_active),
                    "aliases": list(meta.aliases or []),
                }
            )
        return snapshot

    def map_dataset(
        self,
        dataset_id: UUID,
        parent_artifact: DatasetArtifact,
        mapping_config: DataMappingConfig,
        user_name: str = "system",
    ) -> DatasetArtifact:
        """Executes data mapping via bounded DuckDB, saves mapped.parquet, and runs DuckDB quality validation."""
        # 1. Validate Parent Artifact Stage
        if parent_artifact.pipeline_stage != PipelineStage.RAW:
            raise ValueError(
                f"DataMappingService requires parent artifact at stage RAW, got '{parent_artifact.pipeline_stage}'."
            )

        # 2. Validate mandatory 5 fields
        mandatory_fields = {
            "event_id": mapping_config.event_id_column,
            "timestamp": mapping_config.time_column,
            "amount": mapping_config.amount_column,
            "user_id": mapping_config.user_id_column,
            "label": mapping_config.target_column,
        }

        missing_fields = [k for k, v in mandatory_fields.items() if not v or not str(v).strip()]
        if missing_fields:
            raise ValueError(
                f"Chưa ánh xạ đầy đủ 5 trường dữ liệu bắt buộc ({', '.join(missing_fields)}). "
                "Vui lòng hoàn tất trước khi lưu."
            )

        # 3. Check for unique column mapping
        core_cols = [
            mapping_config.event_id_column,
            mapping_config.time_column,
            mapping_config.amount_column,
            mapping_config.user_id_column,
            mapping_config.target_column,
        ]
        if len(set(core_cols)) < len(core_cols):
            raise ValueError("Mỗi trường chuẩn chỉ được ánh xạ tối đa với 1 cột nguồn duy nhất.")

        # 3.1 Load active system metadata (if repository is configured) and enforce required DOMAIN columns
        active_metadata: List[SystemColumnMetadata] = (
            self.metadata_repo.list_all(include_inactive=False)
            if self.metadata_repo is not None
            else []
        )
        domain_meta_by_key: Dict[str, SystemColumnMetadata] = {
            m.column_key: m
            for m in active_metadata
            if (m.category.value if hasattr(m.category, "value") else str(m.category)) == ColumnCategory.DOMAIN.value
        }
        mapped_optional_targets = {
            str(target_col).strip()
            for target_col in mapping_config.optional_columns.values()
            if target_col and str(target_col).strip()
        }
        missing_required_domain = [
            key
            for key, meta in domain_meta_by_key.items()
            if meta.is_required and key not in mapped_optional_targets
        ]
        if missing_required_domain:
            raise ValueError(
                f"Chưa ánh xạ đầy đủ trường nghiệp vụ bắt buộc ({', '.join(missing_required_domain)}). "
                "Vui lòng hoàn tất trước khi lưu."
            )

        # 4. Verify source file exists
        source_path = (
            parent_artifact.output_paths.get("raw")
            or parent_artifact.storage_path
        )
        if not source_path or not self.file_storage.exists(source_path):
            raise FileNotFoundError(f"File not found in storage at '{source_path}'.")

        artifact_id = uuid4()
        storage_path = f"datasets/{dataset_id}/mapped/{artifact_id}/mapped.parquet"
        checksum = ""
        schema_snapshot: Dict[str, str] = {}
        retained_columns: List[str] = []
        quality_report: Optional[DataQualityReport] = None

        with self.file_storage.open_local_path(source_path) as local_path:
            conn = create_utc_bounded_duckdb_connection()
            try:
                _, raw_types = register_file_view(
                    conn,
                    local_path,
                    view_name="raw_src",
                    source_hint=source_path,
                )

                # 5. Verify mapped columns exist in source data
                for std_name, raw_name in mandatory_fields.items():
                    if raw_name not in raw_types:
                        raise ValueError(
                            f"Cột nguồn '{raw_name}' ánh xạ cho '{std_name}' không tồn tại trong tập dữ liệu thô."
                        )

                for raw_col in mapping_config.optional_columns.keys():
                    if raw_col not in raw_types:
                        raise ValueError(
                            f"Cột nguồn tùy chọn '{raw_col}' không tồn tại trong tập dữ liệu thô."
                        )

                # 6. Build SQL coercion expressions + invalid-ratio checks
                select_exprs: Dict[str, str] = {}
                # Each entry: (kind, target_key, not_blank_sql, parsed_sql)
                ratio_checks: List[Tuple[str, str, str, str]] = []

                ev_ident = quote_ident(mapping_config.event_id_column)
                select_exprs[SystemColumn.EVENT_ID.value] = f"CAST({ev_ident} AS VARCHAR)"

                ts_src = mapping_config.time_column
                ts_ident = quote_ident(ts_src)
                ts_parsed_sql = self._timestamp_parse_sql(ts_ident, raw_types[ts_src], mapping_config.time_format)
                select_exprs[SystemColumn.TIMESTAMP.value] = f"strftime({ts_parsed_sql}, '%Y-%m-%d %H:%M:%S')"
                ratio_checks.append(
                    ("TIMESTAMP", SystemColumn.TIMESTAMP.value, self._not_blank_sql(ts_ident, raw_types[ts_src]), ts_parsed_sql)
                )

                amt_src = mapping_config.amount_column
                amt_ident = quote_ident(amt_src)
                amt_parsed_sql = self._numeric_parse_sql(amt_ident)
                select_exprs[SystemColumn.AMOUNT.value] = amt_parsed_sql
                ratio_checks.append(
                    ("AMOUNT", SystemColumn.AMOUNT.value, self._not_blank_sql(amt_ident, raw_types[amt_src]), amt_parsed_sql)
                )

                uid_ident = quote_ident(mapping_config.user_id_column)
                select_exprs[SystemColumn.USER_ID.value] = f"CAST({uid_ident} AS VARCHAR)"

                lbl_src = mapping_config.target_column
                lbl_ident = quote_ident(lbl_src)
                if raw_types[lbl_src].strip().upper() in ("BOOLEAN", "BOOL"):
                    select_exprs[SystemColumn.LABEL.value] = f"CAST(COALESCE(CAST({lbl_ident} AS BIGINT), 0) AS BIGINT)"
                else:
                    lbl_num = self._numeric_parse_sql(lbl_ident)
                    select_exprs[SystemColumn.LABEL.value] = f"CAST(COALESCE(TRY_CAST({lbl_num} AS BIGINT), 0) AS BIGINT)"

                for raw_col, target_col in mapping_config.optional_columns.items():
                    target_key = str(target_col).strip()
                    col_ident = quote_ident(raw_col)
                    col_type = raw_types[raw_col]
                    domain_meta = domain_meta_by_key.get(target_key)
                    if domain_meta is not None:
                        ltype_val = (
                            domain_meta.logical_type.value
                            if hasattr(domain_meta.logical_type, "value")
                            else str(domain_meta.logical_type).upper()
                        )
                        if ltype_val == LogicalDataType.NUMERIC.value:
                            parsed_sql = self._numeric_parse_sql(col_ident)
                            select_exprs[target_key] = parsed_sql
                            ratio_checks.append(
                                ("DOMAIN_NUMERIC", target_key, self._not_blank_sql(col_ident, col_type), parsed_sql)
                            )
                        elif ltype_val == LogicalDataType.DATETIME.value:
                            parsed_sql = self._timestamp_parse_sql(col_ident, col_type, mapping_config.time_format)
                            select_exprs[target_key] = f"strftime({parsed_sql}, '%Y-%m-%d %H:%M:%S')"
                            ratio_checks.append(
                                ("DOMAIN_DATETIME", target_key, self._not_blank_sql(col_ident, col_type), parsed_sql)
                            )
                        elif ltype_val == LogicalDataType.BOOLEAN.value:
                            parsed_sql = self._boolean_parse_sql(col_ident)
                            select_exprs[target_key] = parsed_sql
                            ratio_checks.append(
                                ("DOMAIN_BOOLEAN", target_key, self._not_blank_sql(col_ident, col_type), parsed_sql)
                            )
                        else:
                            select_exprs[target_key] = (
                                f"CASE WHEN {col_ident} IS NULL THEN NULL ELSE CAST({col_ident} AS VARCHAR) END"
                            )
                    else:
                        select_exprs[target_key] = col_ident

                # 6.1 Execute invalid-ratio checks in a single aggregate SQL pass
                if ratio_checks:
                    agg_exprs: List[str] = []
                    for _, _, not_blank_sql, parsed_sql in ratio_checks:
                        agg_exprs.append(f"SUM(CASE WHEN {not_blank_sql} THEN 1 ELSE 0 END)")
                        agg_exprs.append(
                            f"SUM(CASE WHEN ({not_blank_sql}) AND ({parsed_sql}) IS NULL THEN 1 ELSE 0 END)"
                        )
                    try:
                        agg_row = conn.execute(f'SELECT {", ".join(agg_exprs)} FROM "raw_src"').fetchone()
                    except Exception as e:
                        raise ValueError(
                            f"Cột nguồn thời gian không tương thích với định dạng thời gian được chọn: {e}"
                        ) from e

                    max_invalid = mapping_config.max_invalid_ratio_allowed
                    for idx, (kind, target_key, _, _) in enumerate(ratio_checks):
                        non_blank_cnt = int(agg_row[idx * 2] or 0) if agg_row else 0
                        invalid_cnt = int(agg_row[idx * 2 + 1] or 0) if agg_row else 0
                        if non_blank_cnt > 0:
                            invalid_ratio = invalid_cnt / non_blank_cnt
                            if invalid_ratio > max_invalid:
                                if kind in ("TIMESTAMP", "DOMAIN_DATETIME"):
                                    raise ValueError(
                                        f"Cột nguồn thời gian không tương thích: tỷ lệ không thể chuyển đổi ({invalid_ratio * 100:.1f}%) "
                                        f"vượt ngưỡng cho phép ({max_invalid * 100:.1f}%)."
                                    )
                                if kind == "AMOUNT":
                                    raise ValueError(
                                        f"Cột nguồn số tiền không tương thích với kiểu số: {invalid_ratio * 100:.1f}% giá trị không phải số "
                                        f"(vượt ngưỡng {max_invalid * 100:.1f}%)."
                                    )
                                if kind == "DOMAIN_NUMERIC":
                                    raise ValueError(
                                        f"Cột nghiệp vụ '{target_key}' không tương thích kiểu NUMERIC: "
                                        f"{invalid_ratio * 100:.1f}% giá trị không hợp lệ (vượt ngưỡng {max_invalid * 100:.1f}%)."
                                    )
                                if kind == "DOMAIN_BOOLEAN":
                                    raise ValueError(
                                        f"Cột nghiệp vụ '{target_key}' không tương thích kiểu BOOLEAN: "
                                        f"{invalid_ratio * 100:.1f}% giá trị không hợp lệ (vượt ngưỡng {max_invalid * 100:.1f}%)."
                                    )

                retained_columns = list(select_exprs.keys())
                select_sql = "SELECT " + ", ".join(
                    f"{expr} AS {quote_ident(out_col)}" for out_col, expr in select_exprs.items()
                ) + ' FROM "raw_src"'

                # 7-9. Materialize mapped.parquet to temp disk, upload, and run DuckDB quality validation
                with tempfile.TemporaryDirectory() as tmp_dir:
                    tmp_mapped = Path(tmp_dir) / "mapped.parquet"
                    copy_query_to_file(conn, select_sql, tmp_mapped, ".parquet")
                    checksum = sha256_file(tmp_mapped)

                    output_paths = {"mapped": storage_path}
                    validate_stage_outputs(PipelineStage.MAPPED, output_paths)
                    self.file_storage.upload_file(tmp_mapped, storage_path)

                    out_cols, out_types = register_file_view(
                        conn,
                        tmp_mapped,
                        view_name="mapped_out",
                        source_hint=storage_path,
                    )
                    try:
                        quality_report = self.validation_service.validate_duckdb(conn, view_name="mapped_out")
                        schema_snapshot = {
                            col: duckdb_type_to_physical_dtype(out_types[col]) for col in out_cols
                        }
                    finally:
                        conn.execute('DROP VIEW IF EXISTS "mapped_out"')
            finally:
                conn.close()

        assert quality_report is not None

        # 10. Enrich validation report with column_mapping, retained_columns, and metadata snapshot
        report_dict = quality_report.to_dict()
        report_dict["column_mapping"] = mapping_config.get_full_column_mapping()
        if mapping_config.column_semantic_types:
            report_dict["column_semantic_types"] = dict(mapping_config.column_semantic_types)
        report_dict["retained_columns"] = retained_columns
        report_dict["non_ml_columns"] = sorted(build_non_ml_columns(active_metadata))
        if active_metadata:
            report_dict["metadata_snapshot"] = self._serialize_metadata_snapshot(active_metadata)
        if mapping_config.time_format:
            report_dict["time_format"] = str(mapping_config.time_format)

        # 11. Create immutable DatasetArtifact
        artifact = DatasetArtifact(
            artifact_id=artifact_id,
            dataset_id=dataset_id,
            parent_artifact_id=parent_artifact.artifact_id,
            pipeline_stage=PipelineStage.MAPPED,
            change_type="DATA_MAPPING",
            storage_path=storage_path,
            output_paths=output_paths,
            checksum_sha256=checksum,
            schema_snapshot=schema_snapshot,
            row_count=quality_report.total_rows,
            column_count=quality_report.total_columns,
            validation_status=quality_report.validation_status,
            validation_report=report_dict,
            created_by=user_name,
        )

        # 12. Persist artifact if repository is provided
        if self.artifact_repo is not None:
            self.artifact_repo.save(artifact)

        return artifact


__all__ = ["DataMappingService"]
