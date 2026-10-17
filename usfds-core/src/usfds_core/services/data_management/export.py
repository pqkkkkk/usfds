import io
import json
from pathlib import Path
import zipfile
import pandas as pd

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.enums import PipelineStage
from usfds_core.storage.base_storage import IFileStorage


class DatasetExportService:
    """Service implementing Export normalized dataset (Train/Test/Pipelines) as ZIP or individual files."""

    def __init__(self, file_storage: IFileStorage) -> None:
        self.file_storage = file_storage

    def export_artifact_bundle(
        self,
        artifact: DatasetArtifact,
        include_train: bool = True,
        include_test: bool = True,
        include_pipeline: bool = True,
        include_schema: bool = True,
        file_format: str = "parquet",  # "parquet" or "csv"
    ) -> tuple[bytes, str]:
        """Bundles requested artifact outputs into an in-memory ZIP archive.

        Returns:
            Tuple[bytes, str]: The raw bytes of the zip archive, and the suggested filename.
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

        zip_buffer = io.BytesIO()
        stage_name = stage.value.lower()
        format_lower = file_format.lower()

        with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            # 1. Train dataset
            train_path = artifact.output_paths.get("train") or artifact.output_paths.get("mapped")
            if include_train and train_path and self.file_storage.exists(train_path):
                raw_bytes = self.file_storage.read_bytes(train_path)
                if format_lower == "csv" and train_path.endswith((".parquet", ".pq")):
                    df = pd.read_parquet(io.BytesIO(raw_bytes))
                    csv_buffer = io.StringIO()
                    df.to_csv(csv_buffer, index=False)
                    zf.writestr("train.csv", csv_buffer.getvalue().encode("utf-8"))
                else:
                    ext = Path(train_path).suffix or ".parquet"
                    zf.writestr(f"train{ext}", raw_bytes)

            # 2. Test dataset
            test_path = artifact.output_paths.get("test")
            if include_test and test_path and self.file_storage.exists(test_path):
                raw_bytes = self.file_storage.read_bytes(test_path)
                if format_lower == "csv" and test_path.endswith((".parquet", ".pq")):
                    df = pd.read_parquet(io.BytesIO(raw_bytes))
                    csv_buffer = io.StringIO()
                    df.to_csv(csv_buffer, index=False)
                    zf.writestr("test.csv", csv_buffer.getvalue().encode("utf-8"))
                else:
                    ext = Path(test_path).suffix or ".parquet"
                    zf.writestr(f"test{ext}", raw_bytes)

            # 3. Pipeline / Fitted Engineers artifact
            pipe_path = (
                artifact.output_paths.get("pipeline")
                or artifact.output_paths.get("fitted_engineers")
            )
            if include_pipeline and pipe_path and self.file_storage.exists(pipe_path):
                pipe_bytes = self.file_storage.read_bytes(pipe_path)
                ext = Path(pipe_path).suffix or ".joblib"
                zf.writestr(f"pipeline{ext}", pipe_bytes)

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

        zip_bytes = zip_buffer.getvalue()
        zip_filename = f"dataset_{artifact.dataset_id}_{stage_name}_export.zip"
        return zip_bytes, zip_filename


__all__ = ["DatasetExportService"]
