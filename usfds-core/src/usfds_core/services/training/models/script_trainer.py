import ast
import json
import logging
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, Optional
import pandas as pd

from usfds_core.services.training.models.base_trainer import BaseTrainer
from usfds_core.services.training.plugins.register import extract_zip_bytes_to_directory
from usfds_core.services.training.plugins.runner_template import write_runner_script
from usfds_core.services.training.workspace import TrainingRunWorkspace

logger = logging.getLogger(__name__)


class ScriptPluginTrainer(BaseTrainer):
    """Trainer for executing user-imported model plugins.

    Supports:
    1. Function Entrypoint via injected `_usfds_runner.py`:
       `main.py` defines `run_training(train_file, test_file, artifact_dir, target_column, hyperparameters)`
       and `run_inference(input_file, artifact_dir)`. Automatically converts Parquet to CSV if declared
       in `plugin_manifest.json`.
    """

    def __init__(self, entrypoint_uri: str):
        self.entrypoint_uri = entrypoint_uri

    @staticmethod
    def _has_run_training_function(script_path: Path) -> bool:
        """Check via AST whether `script_path` defines `def run_training(...)`."""
        try:
            tree = ast.parse(script_path.read_text(encoding="utf-8"))
            return any(
                isinstance(node, ast.FunctionDef) and node.name == "run_training"
                for node in tree.body
            )
        except Exception:
            return False

    def _prepare_plugin_directory(self, workspace: TrainingRunWorkspace) -> Path:
        """Resolve `entrypoint_uri` (directory, .zip archive, or .py file) into `workspace.plugin_src_dir`
        and return the resolved entrypoint `.py` file path.
        """
        raw_path = Path(self.entrypoint_uri)
        if not raw_path.exists():
            raise FileNotFoundError(f"Script entrypoint not found: {self.entrypoint_uri}")

        workspace.plugin_src_dir.mkdir(parents=True, exist_ok=True)

        if raw_path.is_dir():
            if raw_path.resolve() != workspace.plugin_src_dir.resolve():
                shutil.copytree(raw_path, workspace.plugin_src_dir, dirs_exist_ok=True)
            manifest_path = workspace.plugin_src_dir / "plugin_manifest.json"
            entrypoint_name = "main.py"
            if manifest_path.exists():
                with open(manifest_path, "r", encoding="utf-8") as f:
                    entrypoint_name = json.load(f).get("entrypoint", "main.py")
            script_path = workspace.plugin_src_dir / entrypoint_name
            if not script_path.exists():
                raise FileNotFoundError(f"Entrypoint '{entrypoint_name}' not found in plugin directory {raw_path}")
            return script_path

        if raw_path.suffix.lower() == ".zip":
            extract_zip_bytes_to_directory(raw_path.read_bytes(), workspace.plugin_src_dir)
            manifest_path = workspace.plugin_src_dir / "plugin_manifest.json"
            entrypoint_name = "main.py"
            if manifest_path.exists():
                with open(manifest_path, "r", encoding="utf-8") as f:
                    entrypoint_name = json.load(f).get("entrypoint", "main.py")
            script_path = workspace.plugin_src_dir / entrypoint_name
            if not script_path.exists():
                raise FileNotFoundError(f"Entrypoint '{entrypoint_name}' not found in plugin zip {raw_path}")
            return script_path

        # Single .py file
        target_py = workspace.plugin_src_dir / raw_path.name
        if raw_path.resolve() != target_py.resolve():
            shutil.copy2(raw_path, target_py)
        return target_py

    def _prepare_data_files(
        self,
        workspace: TrainingRunWorkspace,
        data_format: str,
    ) -> tuple[Path, Optional[Path]]:
        """Return paths to train and test files in the format requested by the plugin ('parquet' or 'csv')."""
        train_pq = workspace.train_data_path
        test_pq = workspace.test_data_path if workspace.test_data_path.exists() else None

        if data_format.lower() == "csv":
            train_csv = workspace.input_dir / "data" / "train.csv"
            if train_pq.exists() and not train_csv.exists():
                pd.read_parquet(train_pq).to_csv(train_csv, index=False)
            test_csv = None
            if test_pq and test_pq.exists():
                test_csv = workspace.input_dir / "data" / "test.csv"
                if not test_csv.exists():
                    pd.read_parquet(test_pq).to_csv(test_csv, index=False)
            return train_csv, test_csv

        return train_pq, test_pq

    def train(
        self,
        workspace: TrainingRunWorkspace,
        target_column: str,
        hyperparameters: Dict[str, Any],
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute user plugin in an isolated subprocess."""
        script_path = self._prepare_plugin_directory(workspace)
        workspace.model_dir.mkdir(parents=True, exist_ok=True)

        # Ensure config.json exists in workspace.input_dir
        if not workspace.config_path.exists():
            workspace.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(workspace.config_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "target_column": target_column,
                        "hyperparameters": hyperparameters or {},
                    },
                    f,
                    indent=2,
                )

        if self._has_run_training_function(script_path):
            # Runner Wrapper execution
            manifest_path = script_path.parent / "plugin_manifest.json"
            data_format = "parquet"
            if manifest_path.exists():
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data_format = json.load(f).get("data_format", "parquet")

            train_file, test_file = self._prepare_data_files(workspace, data_format=data_format)
            runner_path = write_runner_script(script_path.parent)

            cmd = [
                sys.executable,
                str(runner_path.resolve()),
                "--mode",
                "train",
                "--entrypoint",
                str(script_path.resolve()),
                "--train-file",
                str(train_file.resolve()),
                "--test-file",
                str((test_file or train_file).resolve()),
                "--config-file",
                str(workspace.config_path.resolve()),
                "--output-dir",
                str(workspace.output_dir.resolve()),
            ]
        else:
            raise RuntimeError(f"Script {script_path} does not define the 'run_training' function")

        logger.info(f"Executing script trainer: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            error_msg = (
                f"Script execution failed with exit code {result.returncode}.\n"
                f"STDERR: {result.stderr}\nSTDOUT: {result.stdout}"
            )
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
