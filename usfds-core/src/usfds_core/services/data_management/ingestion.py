from datetime import datetime, timezone
from pathlib import Path
import tempfile
from typing import Dict, Optional, Tuple, Union
from uuid import UUID, uuid4

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
from usfds_core.services.data_management.duckdb_io import (
    copy_query_to_file,
    create_utc_bounded_duckdb_connection,
    duckdb_type_to_physical_dtype,
    quote_ident,
    register_file_view,
    sha256_file,
)
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

    def _cleanup_failed_ingestion(self, storage_dest: str, dataset_id: UUID) -> None:
        try:
            self.file_storage.delete(storage_dest)
            self.file_storage.delete(f"datasets/{dataset_id}")
        except Exception:
            pass

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
        """Entry point for Data Management: Imports a dataset file via bounded DuckDB,
        validates/locks the Project RAW schema, creates the Dataset entity, computes
        basic data profiling, and persists the RAW artifact without loading full frames into RAM.
        """
        path_str = str(file_path).strip()
        if not self.file_storage.exists(path_str):
            raise FileNotFoundError(f"Tệp nguồn không tồn tại trên hệ thống: '{file_path}'")

        src_path = Path(path_str)
        ext = src_path.suffix.lower()
        file_size = (
            self.file_storage.get_file_size(path_str)
            if hasattr(self.file_storage, "get_file_size")
            else len(self.file_storage.read_bytes(path_str))
        )
        src_name = src_path.name
        src_stem = src_path.stem

        if ext not in self.ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Định dạng tệp '{ext}' không được hỗ trợ. Vui lòng chọn tệp .csv, .parquet hoặc .json."
            )

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
        effective_name = dataset_name or src_stem
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
        storage_dest = f"datasets/{dataset_id}/raw/{src_name}"
        if hasattr(self.file_storage, "save_file"):
            self.file_storage.save_file(path_str, storage_dest)
        else:
            self.file_storage.save_bytes(storage_dest, self.file_storage.read_bytes(path_str))
        if path_str.replace("\\", "/").lstrip("/").startswith(("uploads/", "staging/")):
            try:
                self.file_storage.delete(path_str)
            except Exception:
                pass

        # 3-5. Inspect schema, strip extra columns if needed, hash, and profile via bounded DuckDB
        validation_status = ValidationStatus.PASSED
        schema_validation_dict = None
        columns: list[str] = []
        col_types: Dict[str, str] = {}
        row_count = 0
        checksum = ""
        profile_summary = None

        try:
            with self.file_storage.open_local_path(storage_dest) as local_path:
                expected_cols_to_strip: Optional[list[str]] = None
                conn = create_utc_bounded_duckdb_connection()
                try:
                    columns, col_types = register_file_view(
                        conn,
                        local_path,
                        view_name="raw_src",
                        source_hint=storage_dest,
                    )
                    row_count = int(conn.execute('SELECT COUNT(*) FROM "raw_src"').fetchone()[0])
                    if row_count == 0 or len(columns) == 0:
                        raise ValueError(f"Tập dữ liệu '{src_name}' không chứa bản ghi hoặc cột nào.")

                    if project is not None:
                        if not project.is_schema_locked:
                            locked_schema = self.schema_validator.extract_raw_schema_from_duckdb(
                                conn,
                                view_name="raw_src",
                                source_dataset_id=dataset_id,
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
                            val_res = self.schema_validator.validate_duckdb_view(
                                conn,
                                view_name="raw_src",
                                raw_schema=project.raw_schema,
                                allow_missing_target=True,
                            )
                            if not val_res.is_valid:
                                raise ValueError(" ".join(val_res.errors))

                            if val_res.extra_columns and project.raw_schema:
                                expected_cols_to_strip = [
                                    c for c in project.raw_schema.get("columns", {}).keys()
                                    if c in col_types
                                ]

                            if val_res.warnings:
                                validation_status = ValidationStatus.WARNING
                            schema_validation_dict = val_res.model_dump()

                    if expected_cols_to_strip is None:
                        checksum = sha256_file(local_path)
                        profile_summary = self.profiling_service.analyze_duckdb(conn, view_name="raw_src")
                finally:
                    conn.close()

                if expected_cols_to_strip is not None:
                    with tempfile.TemporaryDirectory() as tmp_dir:
                        filtered_path = Path(tmp_dir) / f"filtered{ext}"
                        filter_conn = create_utc_bounded_duckdb_connection()
                        try:
                            register_file_view(
                                filter_conn,
                                local_path,
                                view_name="raw_src",
                                source_hint=storage_dest,
                            )
                            proj_sql = ", ".join(quote_ident(c) for c in expected_cols_to_strip)
                            copy_query_to_file(
                                filter_conn,
                                f'SELECT {proj_sql} FROM "raw_src"',
                                filtered_path,
                                ext,
                            )
                        finally:
                            filter_conn.close()

                        # Upload filtered artifact after releasing any handle on local_path
                        self.file_storage.upload_file(filtered_path, storage_dest)
                        checksum = sha256_file(filtered_path)

                        profile_conn = create_utc_bounded_duckdb_connection()
                        try:
                            columns, col_types = register_file_view(
                                profile_conn,
                                filtered_path,
                                view_name="raw_filtered",
                                source_hint=storage_dest,
                            )
                            row_count = int(profile_conn.execute('SELECT COUNT(*) FROM "raw_filtered"').fetchone()[0])
                            profile_summary = self.profiling_service.analyze_duckdb(
                                profile_conn,
                                view_name="raw_filtered",
                            )
                        finally:
                            profile_conn.close()
        except Exception:
            self._cleanup_failed_ingestion(storage_dest, dataset_id)
            raise

        assert profile_summary is not None

        # 6. Build Stage outputs
        output_paths = {"raw": storage_dest}
        validate_stage_outputs(PipelineStage.RAW, output_paths)

        schema_snapshot = {col: duckdb_type_to_physical_dtype(col_types[col]) for col in columns}
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
            row_count=row_count,
            column_count=len(columns),
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
