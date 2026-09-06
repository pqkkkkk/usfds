import json
import logging
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict

from usfds_core.services.training.models.base_trainer import BaseTrainer
from usfds_core.services.training.workspace import TrainingRunWorkspace

logger = logging.getLogger(__name__)


class ScriptPluginTrainer(BaseTrainer):
    """Trainer for running external Python scripts via CLI contract:
    `python <entrypoint> --input <workspace.input_dir> --output <workspace.output_dir>`.
    """

    def __init__(self, entrypoint_uri: str):
        self.entrypoint_uri = entrypoint_uri

    def train(
        self,
        workspace: TrainingRunWorkspace,
        target_column: str,
        hyperparameters: Dict[str, Any],
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute user script in a subprocess conforming to the workspace contract."""
        script_path = Path(self.entrypoint_uri)
        if not script_path.exists():
            raise FileNotFoundError(f"Script entrypoint not found: {self.entrypoint_uri}")

        workspace.model_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            sys.executable,
            str(script_path.resolve()),
            "--input",
            str(workspace.input_dir.resolve()),
            "--output",
            str(workspace.output_dir.resolve()),
        ]

        logger.info(f"Executing script trainer: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            error_msg = f"Script execution failed with exit code {result.returncode}.\nSTDERR: {result.stderr}\nSTDOUT: {result.stdout}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Validate that model weights were produced
        model_files = list(workspace.model_dir.glob("*"))
        if not model_files:
            raise FileNotFoundError(
                f"Script completed successfully but no model artifact was found in {workspace.model_dir}"
            )

        # Validate that metrics.json was produced
        if not workspace.metrics_path.exists():
            raise FileNotFoundError(
                f"Script completed successfully but metrics file was not found in {workspace.metrics_path}"
            )

        with open(workspace.metrics_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)

        return metrics
