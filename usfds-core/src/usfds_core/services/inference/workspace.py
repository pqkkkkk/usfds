"""Inference Workspace for managing isolated directories and execution lifecycle."""

from pathlib import Path
import shutil
from typing import Optional, Union
from uuid import UUID, uuid4

from usfds_core.constants import DEFAULT_WORKSPACE_ROOT


class InferenceWorkspace:
    """Encapsulates local working directory, input/output paths, and lifecycle
    for Inference (online and batch) execution.
    """

    def __init__(
        self,
        inference_id: Optional[Union[UUID, str]] = None,
        deployment_id: Optional[Union[UUID, str]] = None,
        base_dir: Optional[Union[Path, str]] = None,
    ):
        self.inference_id = str(inference_id or uuid4())
        self.deployment_id = str(deployment_id or "default")
        self.base_dir = (
            Path(base_dir)
            if base_dir is not None
            else DEFAULT_WORKSPACE_ROOT / "inference" / "runs"
        )

    @property
    def run_dir(self) -> Path:
        """Isolated working directory for this inference task."""
        return self.base_dir / f"{self.deployment_id}_{self.inference_id}"

    @property
    def artifacts_dir(self) -> Path:
        """Directory holding downloaded pipeline artifacts (.joblib)."""
        return self.run_dir / "artifacts"

    @property
    def input_dir(self) -> Path:
        """Directory containing input dataset for batch inference."""
        return self.run_dir / "input"

    @property
    def output_dir(self) -> Path:
        """Directory containing scored output files."""
        return self.run_dir / "output"

    @property
    def fitted_engineers_path(self) -> Path:
        """Local path to downloaded fitted feature engineers artifact."""
        return self.artifacts_dir / "fitted_feature_engineers.joblib"

    @property
    def fitted_pipeline_path(self) -> Path:
        """Local path to downloaded fitted preprocessing pipeline artifact."""
        return self.artifacts_dir / "fitted_pipeline.joblib"

    @property
    def model_path(self) -> Path:
        """Local path to downloaded model artifact."""
        return self.artifacts_dir / "model.joblib"

    @property
    def input_data_path(self) -> Path:
        """Default local path for input batch dataset."""
        return self.input_dir / "batch_input.parquet"

    def get_input_data_path(self, source_filename: str = "") -> Path:
        """Returns input path preserving source file extension."""
        ext = Path(source_filename).suffix or ".parquet"
        return self.input_dir / f"batch_input{ext}"

    @property
    def output_predictions_path(self) -> Path:
        """Path where batch prediction results are generated before upload."""
        return self.output_dir / "predictions.parquet"

    def initialize(self) -> None:
        """Ensure all required input, output, and artifact subdirectories exist."""
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def cleanup(self) -> None:
        """Clean up the run workspace directory and all its temporary contents."""
        shutil.rmtree(self.run_dir, ignore_errors=True)
