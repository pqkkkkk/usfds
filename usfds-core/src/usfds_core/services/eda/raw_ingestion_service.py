import hashlib
import io
from pathlib import Path
from typing import Optional, Union
from uuid import UUID, uuid4
import pandas as pd

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.enums import PipelineStage, ValidationStatus
from usfds_core.domain.schemas.artifact_output import validate_stage_outputs
from usfds_core.repositories.base_dataset_artifact_repo import IDatasetArtifactRepository
from usfds_core.services.eda.eda_service import DatasetEdaService
from usfds_core.storage.base_storage import IFileStorage


class RawDatasetIngestionService:
    """Service that coordinates raw dataset verification, exploratory data analysis (EDA),

    and immutable DatasetArtifact persistence at the initial RAW pipeline stage.
    """

    def __init__(
        self,
        file_storage: IFileStorage,
        artifact_repo: Optional[IDatasetArtifactRepository] = None,
        eda_service: Optional[DatasetEdaService] = None,
    ) -> None:
        self.file_storage = file_storage
        self.artifact_repo = artifact_repo
        self.eda_service = eda_service or DatasetEdaService()

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

    def ingest_raw_dataset(
        self,
        dataset_id: UUID,
        storage_path: str,
        user_name: str = "system",
    ) -> DatasetArtifact:
        """Verifies uploaded dataset file in storage, executes basic EDA, and creates a RAW stage DatasetArtifact.

        Flow:
        1. Verifies that `storage_path` exists in the provided `IFileStorage`.
        2. Reads file bytes and calculates SHA-256 integrity checksum.
        3. Parses raw bytes into a pandas DataFrame (CSV, Parquet, JSON).
        4. Validates that the DataFrame is not empty.
        5. Computes basic EDA metrics via `DatasetEdaService`.
        6. Constructs an immutable `DatasetArtifact` at `PipelineStage.RAW`.
        7. Persists the artifact via `IDatasetArtifactRepository` if provided.
        """
        # 1. Verification of file in storage
        if not self.file_storage.exists(storage_path):
            raise FileNotFoundError(f"Raw dataset file not found in storage at '{storage_path}'.")

        # 2. Read bytes and compute checksum
        raw_bytes = self.file_storage.read_bytes(storage_path)
        if len(raw_bytes) == 0:
            raise ValueError(f"Uploaded file at '{storage_path}' is empty (0 bytes).")

        checksum = hashlib.sha256(raw_bytes).hexdigest()

        # 3. Parse DataFrame
        df = self._load_dataframe_from_bytes(storage_path, raw_bytes)

        # 4. Validate non-empty data
        if df.empty or len(df.columns) == 0:
            raise ValueError(f"Uploaded dataset at '{storage_path}' contains no records or columns.")

        # 5. Execute basic EDA
        eda_summary = self.eda_service.analyze(df)

        # 6. Validate output paths contract for RAW stage
        output_paths = {"raw": storage_path}
        validate_stage_outputs(PipelineStage.RAW, output_paths)

        # 7. Construct schema snapshot
        schema_snapshot = {str(col): str(df[col].dtype) for col in df.columns}

        # 8. Create DatasetArtifact
        artifact = DatasetArtifact(
            artifact_id=uuid4(),
            dataset_id=dataset_id,
            parent_artifact_id=None,
            pipeline_stage=PipelineStage.RAW,
            change_type="RAW_INGESTION",
            storage_path=storage_path,
            output_paths=output_paths,
            checksum_sha256=checksum,
            schema_snapshot=schema_snapshot,
            row_count=len(df),
            column_count=len(df.columns),
            validation_status=ValidationStatus.PASSED,
            validation_report={"eda": eda_summary.to_dict()},
            created_by=user_name,
        )

        # 9. Persist artifact if repository is configured
        if self.artifact_repo is not None:
            self.artifact_repo.save(artifact)

        return artifact

    def upload_and_ingest_raw_dataset(
        self,
        dataset_id: UUID,
        file_name: str,
        file_bytes: bytes,
        user_name: str = "system",
    ) -> DatasetArtifact:
        """Helper for direct uploads and testing: saves bytes to storage, then ingests and generates EDA."""
        clean_file_name = Path(file_name).name
        storage_path = f"datasets/{dataset_id}/raw/{clean_file_name}"
        self.file_storage.save_bytes(storage_path, file_bytes)
        return self.ingest_raw_dataset(
            dataset_id=dataset_id,
            storage_path=storage_path,
            user_name=user_name,
        )


__all__ = ["RawDatasetIngestionService"]
