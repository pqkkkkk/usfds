"""Workspaces for Preprocessing and Feature Engineering execution pipelines."""

from pathlib import Path
import shutil
from typing import Optional, Union
from uuid import UUID

from usfds_core.constants import DEFAULT_WORKSPACE_ROOT


class FeatureEngineeringWorkspace:
    """Encapsulates local working directory, input/output paths, and lifecycle
    for a Feature Engineering pipeline stage execution.
    """

    def __init__(
        self,
        dataset_artifact_id: Union[UUID, str],
        base_dir: Optional[Union[Path, str]] = None,
    ):
        self.dataset_artifact_id = str(dataset_artifact_id)
        self.base_dir = (
            Path(base_dir)
            if base_dir is not None
            else DEFAULT_WORKSPACE_ROOT / "preprocessing" / "feature_engineering"
        )

    @property
    def run_dir(self) -> Path:
        """Isolated working directory for this artifact task: {base_dir}/{dataset_artifact_id}"""
        return self.base_dir / self.dataset_artifact_id

    @property
    def input_dir(self) -> Path:
        """Directory containing input dataset and configs."""
        return self.run_dir / "input"

    @property
    def output_dir(self) -> Path:
        """Directory containing engineered datasets and fitted feature engineering transformers."""
        return self.run_dir / "output"

    # Input paths
    @property
    def mapped_data_path(self) -> Path:
        """Default path to downloaded mapped input parquet file."""
        return self.input_dir / "mapped.parquet"

    def get_mapped_data_path(self, source_filename: str = "") -> Path:
        """Returns input path preserving source file extension."""
        ext = Path(source_filename).suffix or ".parquet"
        return self.input_dir / f"mapped{ext}"

    # Output paths
    @property
    def train_enriched_path(self) -> Path:
        """Path to split, cleansed, and feature-engineered train dataset."""
        return self.output_dir / "train_enriched.parquet"

    @property
    def test_enriched_path(self) -> Path:
        """Path to split, cleansed, and feature-engineered test dataset."""
        return self.output_dir / "test_enriched.parquet"

    @property
    def fitted_engineers_path(self) -> Path:
        """Path to serialized fitted feature engineering transformers (.joblib)."""
        return self.output_dir / "fitted_feature_engineers.joblib"

    def initialize(self) -> None:
        """Ensure all required input and output subdirectories exist."""
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def cleanup(self) -> None:
        """Clean up the working directory and all its contents."""
        shutil.rmtree(self.run_dir, ignore_errors=True)


class PreprocessingWorkspace:
    """Encapsulates local working directory, input/output paths, and lifecycle
    for an ML Feature Transformation & Preprocessing pipeline stage execution.
    """

    def __init__(
        self,
        dataset_artifact_id: Union[UUID, str],
        base_dir: Optional[Union[Path, str]] = None,
    ):
        self.dataset_artifact_id = str(dataset_artifact_id)
        self.base_dir = (
            Path(base_dir)
            if base_dir is not None
            else DEFAULT_WORKSPACE_ROOT / "preprocessing" / "transformations"
        )

    @property
    def run_dir(self) -> Path:
        """Isolated working directory for this artifact task: {base_dir}/{dataset_artifact_id}"""
        return self.base_dir / self.dataset_artifact_id

    @property
    def input_dir(self) -> Path:
        """Directory containing input enriched datasets and configs."""
        return self.run_dir / "input"

    @property
    def output_dir(self) -> Path:
        """Directory containing model-ready datasets and fitted preprocessing pipeline."""
        return self.run_dir / "output"

    # Input paths
    @property
    def train_input_path(self) -> Path:
        """Path to downloaded train_enriched input dataset."""
        return self.input_dir / "train_enriched.parquet"

    @property
    def test_input_path(self) -> Path:
        """Path to downloaded test_enriched input dataset."""
        return self.input_dir / "test_enriched.parquet"

    def get_train_input_path(self, source_filename: str = "") -> Path:
        """Returns train input path preserving source file extension."""
        ext = Path(source_filename).suffix or ".parquet"
        return self.input_dir / f"train_enriched{ext}"

    def get_test_input_path(self, source_filename: str = "") -> Path:
        """Returns test input path preserving source file extension."""
        ext = Path(source_filename).suffix or ".parquet"
        return self.input_dir / f"test_enriched{ext}"

    # Output paths
    @property
    def train_processed_path(self) -> Path:
        """Path to scaled, encoded, dimension-reduced, resampled train dataset."""
        return self.output_dir / "train_processed.parquet"

    @property
    def test_processed_path(self) -> Path:
        """Path to transformed test dataset (without resampling)."""
        return self.output_dir / "test_processed.parquet"

    @property
    def fitted_pipeline_path(self) -> Path:
        """Path to serialized fitted preprocessing pipeline (.joblib)."""
        return self.output_dir / "fitted_pipeline.joblib"

    def initialize(self) -> None:
        """Ensure all required input and output subdirectories exist."""
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def cleanup(self) -> None:
        """Clean up the working directory and all its contents."""
        shutil.rmtree(self.run_dir, ignore_errors=True)
