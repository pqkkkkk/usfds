import hashlib
import io
from typing import Optional, Union
from uuid import UUID, uuid4
import pandas as pd

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.enums import PipelineStage
from usfds_core.domain.schemas.artifact_output import validate_stage_outputs
from usfds_core.domain.schemas.preprocessing_config import (
    DataMappingConfig,
    SupportedTimeFormat,
    SystemColumn,
)
from usfds_core.repositories.base_dataset_artifact_repo import IDatasetArtifactRepository
from usfds_core.services.data_management.validation import (
    DataQualityReport,
    DataQualityValidationService,
)
from usfds_core.storage.base_storage import IFileStorage


class DataMappingService:
    """Service implementing Mapping raw schema to standardized FDS 5-core schema,

    generating mapped.parquet, and automatically executing data quality validation.
    """

    def __init__(
        self,
        file_storage: IFileStorage,
        artifact_repo: Optional[IDatasetArtifactRepository] = None,
        validation_service: Optional[DataQualityValidationService] = None,
    ) -> None:
        self.file_storage = file_storage
        self.artifact_repo = artifact_repo
        self.validation_service = validation_service or DataQualityValidationService()

    def _load_dataframe_from_storage(self, storage_path: str) -> pd.DataFrame:
        """Loads DataFrame from file storage based on file extension."""
        if not self.file_storage.exists(storage_path):
            raise FileNotFoundError(f"File not found in storage at '{storage_path}'.")

        raw_bytes = self.file_storage.read_bytes(storage_path)
        buffer = io.BytesIO(raw_bytes)
        lower_path = storage_path.lower()

        try:
            if lower_path.endswith((".parquet", ".pq")):
                return pd.read_parquet(buffer)
            elif lower_path.endswith((".csv", ".txt")):
                return pd.read_csv(buffer)
            elif lower_path.endswith(".json"):
                return pd.read_json(buffer)
            else:
                try:
                    return pd.read_parquet(buffer)
                except Exception:
                    buffer.seek(0)
                    return pd.read_csv(buffer)
        except Exception as err:
            raise ValueError(f"Failed to parse source dataset from '{storage_path}': {err}") from err

    def _parse_timestamps(
        self,
        series: pd.Series,
        time_format: Union[SupportedTimeFormat, str],
        max_invalid_ratio: float,
    ) -> pd.Series:
        """Parses and standardizes timestamps to ISO-8601 UTC strings."""
        fmt_str = time_format.value if isinstance(time_format, SupportedTimeFormat) else str(time_format)

        try:
            if fmt_str == SupportedTimeFormat.EPOCH_SECONDS.value:
                # Handle numeric epoch seconds
                parsed = pd.to_datetime(pd.to_numeric(series, errors="coerce"), unit="s", utc=True)
            elif fmt_str == SupportedTimeFormat.EPOCH_MILLIS.value:
                # Handle numeric epoch milliseconds
                parsed = pd.to_datetime(pd.to_numeric(series, errors="coerce"), unit="ms", utc=True)
            elif fmt_str in (SupportedTimeFormat.AUTO.value, SupportedTimeFormat.ISO8601.value):
                # Try automatic date parsing
                parsed = pd.to_datetime(series, utc=True, errors="coerce")
            else:
                # Custom strftime format
                parsed = pd.to_datetime(series, format=fmt_str, utc=True, errors="coerce")
        except Exception as e:
            raise ValueError(f"Cột nguồn thời gian không tương thích với định dạng thời gian được chọn: {e}") from e

        # Check unparseable ratio
        original_not_null = series.notna() & (series.astype(str).str.strip() != "")
        if original_not_null.sum() > 0:
            invalid_ratio = (original_not_null & parsed.isna()).sum() / original_not_null.sum()
            if invalid_ratio > max_invalid_ratio:
                raise ValueError(
                    f"Cột nguồn thời gian không tương thích: tỷ lệ không thể chuyển đổi ({invalid_ratio * 100:.1f}%) "
                    f"vượt ngưỡng cho phép ({max_invalid_ratio * 100:.1f}%)."
                )

        return parsed.dt.strftime("%Y-%m-%d %H:%M:%S")

    def _parse_amounts(self, series: pd.Series, max_invalid_ratio: float) -> pd.Series:
        """Parses and standardizes amounts to numeric float64."""
        parsed = pd.to_numeric(series, errors="coerce")
        original_not_null = series.notna() & (series.astype(str).str.strip() != "")
        if original_not_null.sum() > 0:
            invalid_ratio = (original_not_null & parsed.isna()).sum() / original_not_null.sum()
            if invalid_ratio > max_invalid_ratio:
                raise ValueError(
                    f"Cột nguồn số tiền không tương thích với kiểu số: {invalid_ratio * 100:.1f}% giá trị không phải số "
                    f"(vượt ngưỡng {max_invalid_ratio * 100:.1f}%)."
                )
        return parsed.astype("float64")

    def map_dataset(
        self,
        dataset_id: UUID,
        parent_artifact: DatasetArtifact,
        mapping_config: DataMappingConfig,
        user_name: str = "system",
    ) -> DatasetArtifact:
        """Executes data mapping, saves mapped.parquet, and executes data quality validation."""
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

        # 4. Load source raw DataFrame
        source_path = (
            parent_artifact.output_paths.get("raw")
            or parent_artifact.storage_path
        )
        raw_df = self._load_dataframe_from_storage(source_path)

        # 5. Verify mapped columns exist in source data
        for std_name, raw_name in mandatory_fields.items():
            if raw_name not in raw_df.columns:
                raise ValueError(
                    f"Cột nguồn '{raw_name}' ánh xạ cho '{std_name}' không tồn tại trong tập dữ liệu thô."
                )

        for raw_col in mapping_config.optional_columns.keys():
            if raw_col not in raw_df.columns:
                raise ValueError(
                    f"Cột nguồn tùy chọn '{raw_col}' không tồn tại trong tập dữ liệu thô."
                )

        # 6. Transform and rename columns to standardized schema
        mapped_df = pd.DataFrame(index=raw_df.index)

        # 6.1 Event ID
        mapped_df[SystemColumn.EVENT_ID.value] = raw_df[mapping_config.event_id_column].astype(str)

        # 6.2 Timestamp (standardized)
        mapped_df[SystemColumn.TIMESTAMP.value] = self._parse_timestamps(
            raw_df[mapping_config.time_column],
            mapping_config.time_format,
            mapping_config.max_invalid_ratio_allowed,
        )

        # 6.3 Amount (numeric)
        mapped_df[SystemColumn.AMOUNT.value] = self._parse_amounts(
            raw_df[mapping_config.amount_column],
            mapping_config.max_invalid_ratio_allowed,
        )

        # 6.4 User ID
        mapped_df[SystemColumn.USER_ID.value] = raw_df[mapping_config.user_id_column].astype(str)

        # 6.5 Label
        mapped_df[SystemColumn.LABEL.value] = pd.to_numeric(
            raw_df[mapping_config.target_column], errors="coerce"
        ).fillna(0).astype(int)

        # 6.6 Optional columns (all unmapped columns dropped)
        for raw_col, target_col in mapping_config.optional_columns.items():
            mapped_df[str(target_col)] = raw_df[raw_col]

        # 7. Serialize mapped DataFrame to Parquet
        storage_path = f"datasets/{dataset_id}/mapped/mapped.parquet"
        parquet_buffer = io.BytesIO()
        mapped_df.to_parquet(parquet_buffer, index=False)
        parquet_bytes = parquet_buffer.getvalue()

        self.file_storage.save_bytes(storage_path, parquet_bytes)
        checksum = hashlib.sha256(parquet_bytes).hexdigest()

        # 8. Validate output contract for MAPPED stage
        output_paths = {"mapped": storage_path}
        validate_stage_outputs(PipelineStage.MAPPED, output_paths)

        # 9. Data validation
        quality_report: DataQualityReport = self.validation_service.validate(mapped_df)

        # 10. Construct schema snapshot
        schema_snapshot = {str(col): str(mapped_df[col].dtype) for col in mapped_df.columns}

        # 11. Create immutable DatasetArtifact
        artifact = DatasetArtifact(
            artifact_id=uuid4(),
            dataset_id=dataset_id,
            parent_artifact_id=parent_artifact.artifact_id,
            pipeline_stage=PipelineStage.MAPPED,
            change_type="DATA_MAPPING",
            storage_path=storage_path,
            output_paths=output_paths,
            checksum_sha256=checksum,
            schema_snapshot=schema_snapshot,
            row_count=len(mapped_df),
            column_count=len(mapped_df.columns),
            validation_status=quality_report.validation_status,
            validation_report=quality_report.to_dict(),
            created_by=user_name,
        )

        # 12. Persist artifact if repository is provided
        if self.artifact_repo is not None:
            self.artifact_repo.save(artifact)

        return artifact


__all__ = ["DataMappingService"]
