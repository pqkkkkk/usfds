from pathlib import Path
import shutil
from typing import Optional, Union
from uuid import UUID

from usfds_core.constants import DEFAULT_WORKSPACE_ROOT


class TrainingRunWorkspace:
    """Encapsulates the directory layout, path conventions, and lifecycle of a training run workspace."""

    def __init__(
        self,
        run_id: Union[UUID, str],
        base_dir: Optional[Union[Path, str]] = None,
    ):
        self.run_id = str(run_id)
        self.base_dir = (
            Path(base_dir)
            if base_dir is not None
            else DEFAULT_WORKSPACE_ROOT / "training" / "runs"
        )

    @property
    def run_dir(self) -> Path:
        """Isolated working directory for this run: {base_dir}/{run_id}"""
        return self.base_dir / self.run_id

    @property
    def input_dir(self) -> Path:
        """Root input directory containing training data and configurations."""
        return self.run_dir / "input"

    @property
    def output_dir(self) -> Path:
        """Root output directory containing produced model weights and evaluation metrics."""
        return self.run_dir / "output"

    @property
    def train_data_path(self) -> Path:
        """Path to the preprocessed training parquet dataset."""
        return self.input_dir / "data" / "train.parquet"

    @property
    def test_data_path(self) -> Path:
        """Path to the evaluation/test parquet dataset."""
        return self.input_dir / "data" / "test.parquet"

    @property
    def config_path(self) -> Path:
        """Path to the configuration JSON file."""
        return self.input_dir / "config.json"

    @property
    def model_dir(self) -> Path:
        """Directory where trained model weights and binaries are stored."""
        return self.output_dir / "model"

    @property
    def metrics_path(self) -> Path:
        """Path to the output metrics JSON file."""
        return self.output_dir / "metrics.json"

    def initialize(self) -> None:
        """Ensure all required input and output subdirectories exist."""
        (self.input_dir / "data").mkdir(parents=True, exist_ok=True)
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def cleanup(self) -> None:
        """Clean up the run workspace directory and all its contents."""
        shutil.rmtree(self.run_dir, ignore_errors=True)
