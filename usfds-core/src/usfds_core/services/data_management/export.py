import json
from pathlib import Path
import tempfile
from typing import Union
import zipfile

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.enums import PipelineStage
from usfds_core.services.data_management.duckdb_io import (
    copy_query_to_file,
    create_utc_bounded_duckdb_connection,
    quote_literal,
)
from usfds_core.storage.base_storage import IFileStorage


class DatasetExportService:
    """Service implementing Export normalized dataset (Train/Test/Pipelines) as ZIP or individual files."""

    def __init__(self, file_storage: IFileStorage) -> None:
        self.file_storage = file_storage

    def _add_tabular_entry_to_zip(
        self,
        zf: zipfile.ZipFile,
        storage_path: str,
        base_name: str,
        format_lower: str,
    ) -> None:
        with self.file_storage.open_local_path(storage_path) as local_src:
            if format_lower == "csv" and storage_path.lower().endswith((".parquet", ".pq")):
                with tempfile.TemporaryDirectory() as csv_tmp_dir:
                    tmp_csv = Path(csv_tmp_dir) / f"{base_name}.csv"
                    conn = create_utc_bounded_duckdb_connection()
                    try:
                        src_lit = quote_literal(local_src.as_posix())
                        copy_query_to_file(
                            conn,
                            f"SELECT * FROM read_parquet({src_lit})",
                            tmp_csv,
                            ".csv",
                        )
                    finally:
                        conn.close()
                    zf.write(tmp_csv, arcname=f"{base_name}.csv")
            else:
                ext = Path(storage_path).suffix or ".parquet"
                zf.write(local_src, arcname=f"{base_name}{ext}")

    def export_artifact_bundle_to_file(
        self,
        artifact: DatasetArtifact,
        dest_path: Union[str, Path],
        include_train: bool = True,
        include_test: bool = True,
        include_pipeline: bool = True,
        include_schema: bool = True,
        file_format: str = "parquet",  # "parquet" or "csv"
    ) -> str:
        """Bundles requested artifact outputs into a ZIP archive written directly on disk.

        Returns:
            str: The suggested filename for the ZIP archive.
        """
        valid_stages = {
            PipelineStage.FEATURE_ENGINEERED,
            PipelineStage.PRE_PROCESSED,
            PipelineStage.MAPPED,
        }
        stage = (
            artifact.pipeline_stage
            if isinstance(artifact.pipeline_stage, PipelineStage)
            else PipelineStage(str(artifact.pipeline_stage))
        )

        if stage not in valid_stages:
            raise ValueError(
                f"Export is only supported for stages {', '.join(s.value for s in valid_stages)}, "
                f"got '{stage}'."
            )

        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        stage_name = stage.value.lower()
        format_lower = file_format.lower()

        with zipfile.ZipFile(dest, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            # 1. Train dataset
            train_path = artifact.output_paths.get("train") or artifact.output_paths.get("mapped")
            if include_train and train_path and self.file_storage.exists(train_path):
                self._add_tabular_entry_to_zip(zf, train_path, "train", format_lower)

            # 2. Test dataset
            test_path = artifact.output_paths.get("test")
            if include_test and test_path and self.file_storage.exists(test_path):
                self._add_tabular_entry_to_zip(zf, test_path, "test", format_lower)

            # 3. Pipeline / Fitted Engineers artifact
            pipe_path = (
                artifact.output_paths.get("pipeline")
                or artifact.output_paths.get("fitted_engineers")
            )
            if include_pipeline and pipe_path and self.file_storage.exists(pipe_path):
                with self.file_storage.open_local_path(pipe_path) as local_pipe:
                    ext = Path(pipe_path).suffix or ".joblib"
                    zf.write(local_pipe, arcname=f"pipeline{ext}")

            # 4. Schema metadata JSON
            if include_schema:
                metadata = {
                    "artifact_id": str(artifact.artifact_id),
                    "dataset_id": str(artifact.dataset_id),
                    "pipeline_stage": stage_name.upper(),
                    "row_count": artifact.row_count,
                    "column_count": artifact.column_count,
                    "checksum_sha256": artifact.checksum_sha256,
                    "schema_snapshot": artifact.schema_snapshot,
                    "validation_status": (
                        artifact.validation_status.value
                        if hasattr(artifact.validation_status, "value")
                        else str(artifact.validation_status)
                    ),
                    "validation_report": artifact.validation_report,
                }
                zf.writestr("schema_metadata.json", json.dumps(metadata, indent=2))

        return f"dataset_{artifact.dataset_id}_{stage_name}_export.zip"

    def export_artifact_bundle(
        self,
        artifact: DatasetArtifact,
        include_train: bool = True,
        include_test: bool = True,
        include_pipeline: bool = True,
        include_schema: bool = True,
        file_format: str = "parquet",  # "parquet" or "csv"
    ) -> tuple[bytes, str]:
        """Bundles requested artifact outputs into a ZIP archive (bytes wrapper)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "bundle.zip"
            zip_filename = self.export_artifact_bundle_to_file(
                artifact=artifact,
                dest_path=zip_path,
                include_train=include_train,
                include_test=include_test,
                include_pipeline=include_pipeline,
                include_schema=include_schema,
                file_format=file_format,
            )
            return zip_path.read_bytes(), zip_filename


__all__ = ["DatasetExportService"]
