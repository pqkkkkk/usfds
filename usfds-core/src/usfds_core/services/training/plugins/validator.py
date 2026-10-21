"""Two-stage validator for User Model Plugins:
1. Static AST Security & Contract Validation.
2. Dynamic Dry-Run Validation (Training + Unlabeled Inference on Synthetic FEATURE_ENGINEERED Data).
"""

import ast
import json
import logging
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import List, Optional, Set, Tuple
import numpy as np
import pandas as pd

from usfds_core.domain.schemas.model_plugin import ModelPluginManifest, PluginValidationResult
from usfds_core.services.training.plugins.runner_template import (
    RUNNER_SCRIPT_FILENAME,
    write_runner_script,
)

logger = logging.getLogger(__name__)

FORBIDDEN_MODULES: Set[str] = {
    "socket",
    "subprocess",
    "urllib",
    "requests",
    "http",
    "ftplib",
    "telnetlib",
    "pty",
    "ctypes",
    "webbrowser",
}

FORBIDDEN_BUILTINS: Set[str] = {
    "eval",
    "exec",
    "compile",
}


class ModelPluginValidator:
    """Validates user-imported model plugin packages before registration."""

    def __init__(self, dry_run_timeout_seconds: int = 60):
        self.dry_run_timeout_seconds = dry_run_timeout_seconds

    @staticmethod
    def load_or_create_manifest(
        plugin_dir: Path,
        override_manifest: Optional[ModelPluginManifest] = None,
    ) -> ModelPluginManifest:
        """Load `plugin_manifest.json` from `plugin_dir` if present, or fallback to override/default."""
        manifest_path = plugin_dir / "plugin_manifest.json"
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if override_manifest:
                merged = {**data, **override_manifest.model_dump(exclude_unset=True)}
                return ModelPluginManifest.model_validate(merged)
            return ModelPluginManifest.model_validate(data)

        if override_manifest:
            return override_manifest

        return ModelPluginManifest(model_name=plugin_dir.name)

    @staticmethod
    def validate_static_ast(
        plugin_dir: Path,
        entrypoint_name: str = "main.py",
    ) -> List[str]:
        """Perform static AST inspection across all Python files in the plugin directory."""
        errors: List[str] = []
        entrypoint_path = plugin_dir / entrypoint_name
        if not entrypoint_path.exists():
            errors.append(f"Required entrypoint file '{entrypoint_name}' not found in plugin root.")
            return errors

        py_files = [
            p for p in plugin_dir.rglob("*.py")
            if p.name != RUNNER_SCRIPT_FILENAME and "__pycache__" not in p.parts
        ]

        if not py_files:
            errors.append("No Python source files found in plugin directory.")
            return errors

        entrypoint_functions: Set[str] = set()

        for py_file in py_files:
            rel_name = str(py_file.relative_to(plugin_dir))
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=rel_name)
            except SyntaxError as se:
                errors.append(f"Syntax error in '{rel_name}' (line {se.lineno}): {se.msg}")
                continue
            except Exception as ex:
                errors.append(f"Failed to parse '{rel_name}': {ex}")
                continue

            if py_file.resolve() == entrypoint_path.resolve():
                for node in tree.body:
                    if isinstance(node, ast.FunctionDef):
                        entrypoint_functions.add(node.name)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root_mod = alias.name.split(".")[0]
                        if root_mod in FORBIDDEN_MODULES:
                            errors.append(
                                f"Forbidden module import '{alias.name}' in '{rel_name}' (line {node.lineno})."
                            )
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        root_mod = node.module.split(".")[0]
                        if root_mod in FORBIDDEN_MODULES:
                            errors.append(
                                f"Forbidden module import from '{node.module}' in '{rel_name}' (line {node.lineno})."
                            )
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_BUILTINS:
                        errors.append(
                            f"Forbidden builtin call '{node.func.id}()' in '{rel_name}' (line {node.lineno})."
                        )

        if "run_training" not in entrypoint_functions:
            errors.append(
                f"Entrypoint '{entrypoint_name}' must define function 'run_training(train_file, test_file, artifact_dir, target_column, hyperparameters)'."
            )
        if "run_inference" not in entrypoint_functions:
            errors.append(
                f"Entrypoint '{entrypoint_name}' must define function 'run_inference(input_file, artifact_dir)'."
            )

        return errors

    @staticmethod
    def generate_synthetic_feature_engineered_data(
        n_train: int = 120,
        n_test: int = 40,
        seed: int = 42,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Generate synthetic FEATURE_ENGINEERED datasets preserving business semantics,
        repeating user_ids, chronological timestamps, categorical & numerical features, and binary label.
        """
        rng = np.random.default_rng(seed)
        total = n_train + n_test

        base_ts = pd.Timestamp("2026-01-01T00:00:00Z")
        timestamps = [base_ts + pd.Timedelta(minutes=15 * i) for i in range(total)]

        # Repeat user_ids so sequence/graph/window models can form multi-event histories
        user_ids = rng.integers(1001, 1025, size=total)
        amounts = np.round(rng.uniform(5.0, 1500.0, size=total), 2)
        avg_amounts = np.round(rng.uniform(20.0, 500.0, size=total), 2)

        df = pd.DataFrame({
            "event_id": np.arange(1, total + 1, dtype=np.int64),
            "user_id": user_ids.astype(np.int64),
            "account_age_days": rng.integers(1, 1000, size=total, dtype=np.int64),
            "total_transactions_user": rng.integers(1, 200, size=total, dtype=np.int64),
            "avg_amount_user": avg_amounts,
            "amount": amounts,
            "country": rng.choice(["US", "GB", "FR", "DE"], size=total),
            "bin_country": rng.choice(["US", "GB", "FR", "DE"], size=total),
            "channel": rng.choice(["web", "mobile"], size=total),
            "merchant_category": rng.choice(["retail", "electronics", "travel", "food"], size=total),
            "promo_used": rng.integers(0, 2, size=total, dtype=np.int64),
            "avs_match": rng.integers(0, 2, size=total, dtype=np.int64),
            "cvv_result": rng.integers(0, 2, size=total, dtype=np.int64),
            "three_ds_flag": rng.integers(0, 2, size=total, dtype=np.int64),
            "timestamp": timestamps,
            "shipping_distance_km": np.round(rng.uniform(1.0, 500.0, size=total), 2),
        })

        # Ensure both classes (0 and 1) are well represented in both train and test
        labels = np.zeros(total, dtype=np.int64)
        labels[::4] = 1  # 25% positive class
        df["label"] = labels

        df_train = df.iloc[:n_train].reset_index(drop=True)
        df_test = df.iloc[n_train:].reset_index(drop=True)
        return df_train, df_test

    def validate(
        self,
        plugin_source_dir: Path,
        manifest: Optional[ModelPluginManifest] = None,
    ) -> PluginValidationResult:
        """Execute full 2-stage validation (Static AST + Dynamic Train & Inference Dry-Run)."""
        if not plugin_source_dir.exists() or not plugin_source_dir.is_dir():
            return PluginValidationResult(
                is_valid=False,
                errors=[f"Plugin directory does not exist: {plugin_source_dir}"],
            )

        try:
            resolved_manifest = self.load_or_create_manifest(plugin_source_dir, manifest)
        except Exception as ex:
            return PluginValidationResult(
                is_valid=False,
                errors=[f"Invalid plugin_manifest.json: {ex}"],
            )

        # Stage 1: Static AST check
        static_errors = self.validate_static_ast(
            plugin_source_dir,
            entrypoint_name=resolved_manifest.entrypoint,
        )
        if static_errors:
            return PluginValidationResult(
                is_valid=False,
                static_check_passed=False,
                manifest=resolved_manifest,
                errors=static_errors,
            )

        # Stage 2: Dynamic Dry-Run in isolated temp workspace
        temp_root = Path(tempfile.mkdtemp(prefix="usfds_plugin_dryrun_"))
        try:
            sandbox_src = temp_root / "src"
            shutil.copytree(plugin_source_dir, sandbox_src)
            runner_path = write_runner_script(sandbox_src)

            input_dir = temp_root / "input"
            output_dir = temp_root / "output"
            input_dir.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)

            df_train, df_test = self.generate_synthetic_feature_engineered_data()
            ext = ".csv" if resolved_manifest.data_format == "csv" else ".parquet"
            train_file = input_dir / f"train_enriched{ext}"
            test_file = input_dir / f"test_enriched{ext}"
            unlabeled_file = input_dir / f"inference_unlabeled{ext}"

            df_unlabeled = df_test.drop(columns=["label"])

            if ext == ".csv":
                df_train.to_csv(train_file, index=False)
                df_test.to_csv(test_file, index=False)
                df_unlabeled.to_csv(unlabeled_file, index=False)
            else:
                df_train.to_parquet(train_file, index=False)
                df_test.to_parquet(test_file, index=False)
                df_unlabeled.to_parquet(unlabeled_file, index=False)

            dry_run_params = {
                **resolved_manifest.default_hyperparameters,
                **resolved_manifest.dry_run_hyperparameters,
            }
            config_file = input_dir / "config.json"
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "target_column": "label",
                        "hyperparameters": dry_run_params,
                    },
                    f,
                    indent=2,
                )

            entrypoint_file = sandbox_src / resolved_manifest.entrypoint

            # 2A. Dry-Run Training
            train_cmd = [
                sys.executable,
                str(runner_path),
                "--mode",
                "train",
                "--entrypoint",
                str(entrypoint_file),
                "--train-file",
                str(train_file),
                "--test-file",
                str(test_file),
                "--config-file",
                str(config_file),
                "--output-dir",
                str(output_dir),
            ]

            train_proc = subprocess.run(
                train_cmd,
                capture_output=True,
                text=True,
                timeout=self.dry_run_timeout_seconds,
                check=False,
            )

            if train_proc.returncode != 0:
                return PluginValidationResult(
                    is_valid=False,
                    static_check_passed=True,
                    dry_run_train_passed=False,
                    manifest=resolved_manifest,
                    errors=[
                        f"Dry-run training failed (exit code {train_proc.returncode}): "
                        f"{train_proc.stderr.strip() or train_proc.stdout.strip()}"
                    ],
                )

            model_dir = output_dir / "model"
            artifact_files = [p.name for p in model_dir.glob("*") if p.is_file()]
            if not artifact_files:
                return PluginValidationResult(
                    is_valid=False,
                    static_check_passed=True,
                    dry_run_train_passed=False,
                    manifest=resolved_manifest,
                    errors=["Dry-run training completed but saved no files in artifact_dir."],
                )

            has_preprocessor = any("preprocess" in name.lower() or "pipeline" in name.lower() for name in artifact_files)
            has_model = any("model" in name.lower() or "pipeline" in name.lower() for name in artifact_files)
            if not (has_model and has_preprocessor):
                return PluginValidationResult(
                    is_valid=False,
                    static_check_passed=True,
                    dry_run_train_passed=False,
                    manifest=resolved_manifest,
                    detected_artifacts=artifact_files,
                    errors=[
                        f"Plugin must save both model weights (e.g. 'model.joblib'/'model.pt') and "
                        f"fitted preprocessor (e.g. 'preprocessor.joblib') in artifact_dir. Found: {artifact_files}"
                    ],
                )

            metrics_path = output_dir / "metrics.json"
            if not metrics_path.exists():
                return PluginValidationResult(
                    is_valid=False,
                    static_check_passed=True,
                    dry_run_train_passed=False,
                    manifest=resolved_manifest,
                    detected_artifacts=artifact_files,
                    errors=["Dry-run training did not produce metrics.json."],
                )

            with open(metrics_path, "r", encoding="utf-8") as f:
                metrics = json.load(f)

            # 2B. Dry-Run Inference on unlabeled data
            inference_out = output_dir / "dryrun_inference.parquet"
            inf_cmd = [
                sys.executable,
                str(runner_path),
                "--mode",
                "inference",
                "--entrypoint",
                str(entrypoint_file),
                "--input-file",
                str(unlabeled_file),
                "--artifact-dir",
                str(model_dir),
                "--output-file",
                str(inference_out),
            ]

            inf_proc = subprocess.run(
                inf_cmd,
                capture_output=True,
                text=True,
                timeout=self.dry_run_timeout_seconds,
                check=False,
            )

            if inf_proc.returncode != 0:
                return PluginValidationResult(
                    is_valid=False,
                    static_check_passed=True,
                    dry_run_train_passed=True,
                    dry_run_inference_passed=False,
                    manifest=resolved_manifest,
                    metrics=metrics,
                    detected_artifacts=artifact_files,
                    errors=[
                        f"Dry-run inference failed on unlabeled data (exit code {inf_proc.returncode}): "
                        f"{inf_proc.stderr.strip() or inf_proc.stdout.strip()}"
                    ],
                )

            if not inference_out.exists():
                return PluginValidationResult(
                    is_valid=False,
                    static_check_passed=True,
                    dry_run_train_passed=True,
                    dry_run_inference_passed=False,
                    manifest=resolved_manifest,
                    metrics=metrics,
                    detected_artifacts=artifact_files,
                    errors=["Dry-run inference did not produce output predictions file."],
                )

            pred_df = pd.read_parquet(inference_out)
            if len(pred_df) != len(df_unlabeled):
                return PluginValidationResult(
                    is_valid=False,
                    static_check_passed=True,
                    dry_run_train_passed=True,
                    dry_run_inference_passed=False,
                    manifest=resolved_manifest,
                    metrics=metrics,
                    detected_artifacts=artifact_files,
                    errors=[
                        f"Inference row alignment mismatch: expected {len(df_unlabeled)} predictions, got {len(pred_df)}."
                    ],
                )

            return PluginValidationResult(
                is_valid=True,
                static_check_passed=True,
                dry_run_train_passed=True,
                dry_run_inference_passed=True,
                manifest=resolved_manifest,
                metrics=metrics,
                detected_artifacts=artifact_files,
                errors=[],
            )
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)
