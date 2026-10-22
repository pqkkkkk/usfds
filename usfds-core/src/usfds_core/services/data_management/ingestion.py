from datetime import datetime, timezone
import hashlib
import io
from pathlib import Path
from typing import Optional, Tuple, Union
from uuid import UUID, uuid4
import pandas as pd

from usfds_core.domain.entities.dataset import Dataset, DatasetArtifact
from usfds_core.domain.entities.enums import (
    DataClassification,
    PipelineStage,
    ProjectStatus,
    ValidationStatus,
)
from usfds_core.domain.schemas.artifact_output import validate_stage_outputs
from usfds_core.repositories.base_dataset_artifact_repo import IDatasetArtifactRepository
from usfds_core.repositories.base_dataset_repo import IDatasetRepository
from usfds_core.repositories.base_project_repo import IProjectRepository
from usfds_core.services.data_management.profiling import DataProfilingService
from usfds_core.services.project_management.schema_validator import ProjectSchemaValidator
from usfds_core.storage.base_storage import IFileStorage


class DatasetIngestionService:
    """Service that coordinates raw dataset ingestion, data profiling,
    project-level RAW schema locking/validation, and immutable Dataset & DatasetArtifact
    persistence at the RAW pipeline stage.
    """

    ALLOWED_EXTENSIONS = {".csv", ".parquet", ".pq", ".json", ".txt"}
    DEFAULT_MAX_FILE_SIZE = 1024 * 1024 * 1024  # 1 GB

    def __init__(
        self,
        file_storage: IFileStorage,
        artifact_repo: Optional[IDatasetArtifactRepository] = None,
        dataset_repo: Optional[IDatasetRepository] = None,
        project_repo: Optional[IProjectRepository] = None,
        profiling_service: Optional[DataProfilingService] = None,
        schema_validator: Optional[ProjectSchemaValidator] = None,
    ) -> None:
        self.file_storage = file_storage
        self.artifact_repo = artifact_repo
        self.dataset_repo = dataset_repo
        self.project_repo = project_repo
        self.profiling_service = profiling_service or DataProfilingService()
        self.schema_validator = schema_validator or ProjectSchemaValidator()

    def _load_dataframe_from_bytes(self, path_str: str, raw_bytes: bytes) -> pd.DataFrame:
        """Parses a DataFrame from raw bytes based on file format extension."""
        buffer = io.BytesIO(raw_bytes)
        lower_path = path_str.lower()

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
            raise ValueError(f"Failed to parse tabular data from '{path_str}': {err}") from err

    def import_dataset(
        self,
        file_path: Union[str, Path],
        dataset_name: Optional[str] = None,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        project_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        contains_pii: bool = False,
        data_classification: Optional[DataClassification] = None,
        user_name: str = "system",
        max_file_size: int = DEFAULT_MAX_FILE_SIZE,
    ) -> Tuple[Dataset, DatasetArtifact]:
        """Entry point for Data Management: Imports a local dataset file, validates/locks the
        Project RAW schema, creates the Dataset entity, stores the raw
        data file, computes basic data profiling, and persists the RAW artifact.
        """
        src_path = Path(file_path).resolve()
        if not src_path.is_file():
            raise FileNotFoundError(f"Tệp nguồn không tồn tại trên hệ thống: '{file_path}'")

        ext = src_path.suffix.lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Định dạng tệp '{ext}' không được hỗ trợ. Vui lòng chọn tệp .csv, .parquet hoặc .json."
            )

        file_size = src_path.stat().st_size
        if file_size == 0:
            raise ValueError("Tệp dữ liệu rỗng (0 bytes). Vui lòng kiểm tra lại nội dung tệp.")
        if file_size > max_file_size:
            raise ValueError(
                f"Kích thước tệp ({file_size} bytes) vượt quá dung lượng tối đa cho phép ({max_file_size} bytes)."
            )

        # 1. Initialize Dataset Entity & Check Project Status
        dataset_id = uuid4()
        effective_project_id = project_id or uuid4()
        effective_user_id = user_id or uuid4()
        effective_name = dataset_name or src_path.stem
        effective_display = display_name or effective_name.replace("_", " ").title()

        project = None
        if self.project_repo is not None:
            project = self.project_repo.get_by_id(effective_project_id)
            if project is not None:
                proj_status = (
                    project.status.value
                    if hasattr(project.status, "value")
                    else str(project.status)
                )
                if proj_status == ProjectStatus.ARCHIVED.value:
                    raise ValueError(
                        f"Không thể tải dữ liệu vào dự án '{project.project_name}' vì dự án đang ở trạng thái ARCHIVED."
                    )

        if self.dataset_repo is not None:
            existing = self.dataset_repo.get_by_name(effective_project_id, effective_name)
            if existing is not None:
                raise ValueError(
                    f"Tên tập dữ liệu '{effective_name}' đã tồn tại trong dự án. Vui lòng chọn tên khác."
                )

        dataset = Dataset(
            dataset_id=dataset_id,
            project_id=effective_project_id,
            user_id=effective_user_id,
            dataset_name=effective_name,
            display_name=effective_display,
            description=description,
            contains_pii=contains_pii,
            data_classification=data_classification or DataClassification.INTERNAL,
        )

        # 2. Copy/save file to storage
        storage_dest = f"datasets/{dataset_id}/raw/{src_path.name}"
        if hasattr(self.file_storage, "save_file"):
            self.file_storage.save_file(src_path, storage_dest)
        else:
            self.file_storage.save_bytes(storage_dest, src_path.read_bytes())

        # 3. Read bytes & Parse DataFrame
        try:
            raw_bytes = self.file_storage.read_bytes(storage_dest)
            df = self._load_dataframe_from_bytes(storage_dest, raw_bytes)
            if df.empty or len(df.columns) == 0:
                raise ValueError(f"Tập dữ liệu '{src_path.name}' không chứa bản ghi hoặc cột nào.")
        except Exception:
            try:
                self.file_storage.delete(storage_dest)
                self.file_storage.delete(f"datasets/{dataset_id}")
            except Exception:
                pass
            raise

        # 4. Project-level RAW Schema Lock / Compatibility Validation
        validation_status = ValidationStatus.PASSED
        schema_validation_dict = None

        if project is not None:
            if not project.is_schema_locked:
                # First dataset locks the Project's RAW schema
                locked_schema = self.schema_validator.extract_raw_schema(
                    df, source_dataset_id=dataset_id
                )
                project.raw_schema = locked_schema.to_dict()
                project.base_dataset_id = dataset_id
                project.updated_at = datetime.now(timezone.utc)
                if self.project_repo is not None:
                    self.project_repo.save(project)
                schema_validation_dict = {
                    "action": "SCHEMA_LOCKED",
                    "is_valid": True,
                    "warnings": [],
                }
            else:
                # Validate against existing locked Project RAW schema
                val_res = self.schema_validator.validate_dataframe(
                    df, project.raw_schema, allow_missing_target=True
                )
                if not val_res.is_valid:
                    try:
                        self.file_storage.delete(storage_dest)
                        self.file_storage.delete(f"datasets/{dataset_id}")
                    except Exception:
                        pass
                    raise ValueError(" ".join(val_res.errors))

                # Superset tolerance: strip extra columns not in project.raw_schema
                if val_res.extra_columns and project.raw_schema:
                    expected_cols = [
                        c for c in project.raw_schema.get("columns", {}).keys()
                        if c in df.columns
                    ]
                    df = df[expected_cols]
                    # Re-persist filtered raw file so downstream stages see consistent columns
                    out_buf = io.BytesIO()
                    if ext in (".parquet", ".pq"):
                        df.to_parquet(out_buf, index=False)
                    elif ext == ".json":
                        df.to_json(out_buf, orient="records")
                    else:
                        df.to_csv(out_buf, index=False)
                    raw_bytes = out_buf.getvalue()
                    self.file_storage.save_bytes(storage_dest, raw_bytes)

                if val_res.warnings:
                    validation_status = ValidationStatus.WARNING

                schema_validation_dict = val_res.model_dump()

        checksum = hashlib.sha256(raw_bytes).hexdigest()

        # 5. Basic Data Profiling
        profile_summary = self.profiling_service.analyze(df)

        # 6. Build Stage outputs
        output_paths = {"raw": storage_dest}
        validate_stage_outputs(PipelineStage.RAW, output_paths)

        schema_snapshot = {str(col): str(df[col].dtype) for col in df.columns}
        val_report = {
            "profiling": profile_summary.to_dict(),
        }
        if schema_validation_dict is not None:
            val_report["schema_validation"] = schema_validation_dict

        # 7. Construct RAW DatasetArtifact
        artifact = DatasetArtifact(
            artifact_id=uuid4(),
            dataset_id=dataset_id,
            parent_artifact_id=None,
            pipeline_stage=PipelineStage.RAW,
            change_type="RAW_INGESTION",
            storage_path=storage_dest,
            output_paths=output_paths,
            checksum_sha256=checksum,
            schema_snapshot=schema_snapshot,
            row_count=len(df),
            column_count=len(df.columns),
            validation_status=validation_status,
            validation_report=val_report,
            created_by=user_name,
        )

        # 8. Persist Dataset and Artifact in repositories
        if self.dataset_repo is not None:
            self.dataset_repo.save(dataset)
        if self.artifact_repo is not None:
            self.artifact_repo.save(artifact)

        return dataset, artifact


__all__ = ["DatasetIngestionService"]
