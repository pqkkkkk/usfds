"""System Runner Wrapper template (_usfds_runner.py) injected into the execution workspace.

Provides CLI argument parsing, format adaptation (Parquet/CSV), target column alias resolution,
standardized metric evaluation, and execution of user-defined `run_training` and `run_inference`
functions in `main.py`.
"""

from pathlib import Path

RUNNER_SCRIPT_FILENAME = "_usfds_runner.py"

RUNNER_SCRIPT_TEMPLATE = '''"""Auto-generated USFDS Plugin Runner Wrapper."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Dict, List
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)


def _resolve_target_column(file_path: Path, requested_target: str) -> str:
    """Resolve the actual target column name present in the dataset."""
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        cols = list(pd.read_csv(file_path, nrows=1).columns)
    else:
        cols = list(pd.read_parquet(file_path).columns)

    if requested_target in cols:
        return requested_target

    for c in cols:
        if c.lower() == requested_target.lower():
            return c

    for candidate in ["label", "is_fraud", "target", "fraud", "Class", "class"]:
        if candidate in cols:
            return candidate

    return requested_target


def _compute_standard_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> Dict[str, Any]:
    """Compute standardized USFDS evaluation metrics from y_true and y_prob."""
    y_true_arr = np.asarray(y_true, dtype=int).ravel()
    y_prob_arr = np.clip(np.asarray(y_prob, dtype=float).ravel(), 0.0, 1.0)
    y_pred_arr = (y_prob_arr >= 0.5).astype(int)

    metrics: Dict[str, Any] = {
        "accuracy": round(float(accuracy_score(y_true_arr, y_pred_arr)), 4),
        "precision": round(float(precision_score(y_true_arr, y_pred_arr, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true_arr, y_pred_arr, zero_division=0)), 4),
        "f1_score": round(float(f1_score(y_true_arr, y_pred_arr, zero_division=0)), 4),
    }

    try:
        if len(np.unique(y_true_arr)) > 1:
            metrics["loss"] = round(float(log_loss(y_true_arr, y_prob_arr, labels=[0, 1])), 4)
            metrics["roc_auc"] = round(float(roc_auc_score(y_true_arr, y_prob_arr)), 4)
            metrics["pr_auc"] = round(float(average_precision_score(y_true_arr, y_prob_arr)), 4)
        else:
            metrics["loss"] = 0.0
            metrics["roc_auc"] = 0.0
            metrics["pr_auc"] = 0.0
    except Exception:
        metrics.setdefault("loss", 0.0)

    # Best F1 threshold search
    best_th = 0.5
    best_f1 = metrics["f1_score"]
    for th in np.linspace(0.1, 0.9, 17):
        preds_th = (y_prob_arr >= th).astype(int)
        f1_th = float(f1_score(y_true_arr, preds_th, zero_division=0))
        if f1_th > best_f1:
            best_f1 = f1_th
            best_th = float(round(th, 2))

    metrics["recommended_thresholds"] = {
        "best_f1": {"threshold": best_th, "f1_score": round(best_f1, 4)}
    }
    return metrics


def _load_entrypoint_module(entrypoint_path: Path):
    """Dynamically import the user entrypoint module with its parent directory on sys.path."""
    plugin_dir = str(entrypoint_path.parent.resolve())
    if plugin_dir not in sys.path:
        sys.path.insert(0, plugin_dir)

    spec = importlib.util.spec_from_file_location("usfds_user_plugin_main", str(entrypoint_path.resolve()))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module specification from {entrypoint_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["usfds_user_plugin_main"] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser(description="USFDS System Runner Wrapper")
    parser.add_argument("--mode", choices=["train", "inference"], required=True)
    parser.add_argument("--entrypoint", required=True, help="Path to user main.py")
    parser.add_argument("--train-file", help="Path to training dataset file")
    parser.add_argument("--test-file", help="Path to testing dataset file")
    parser.add_argument("--config-file", help="Path to config.json")
    parser.add_argument("--output-dir", help="Path to output directory (for train mode)")
    parser.add_argument("--input-file", help="Path to unlabeled input file (for inference mode)")
    parser.add_argument("--artifact-dir", help="Path to model artifact directory (for inference mode)")
    parser.add_argument("--output-file", help="Path to output predictions parquet file (for inference mode)")
    args = parser.parse_args()

    entrypoint_path = Path(args.entrypoint).resolve()
    user_module = _load_entrypoint_module(entrypoint_path)

    if args.mode == "train":
        if not hasattr(user_module, "run_training"):
            raise AttributeError(f"Entrypoint '{entrypoint_path.name}' must define 'run_training(...)'")

        train_file = Path(args.train_file).resolve()
        test_file = Path(args.test_file).resolve() if args.test_file else train_file
        output_dir = Path(args.output_dir).resolve()
        artifact_dir = output_dir / "model"
        artifact_dir.mkdir(parents=True, exist_ok=True)

        cfg: Dict[str, Any] = {}
        if args.config_file and Path(args.config_file).exists():
            with open(args.config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)

        requested_target = cfg.get("target_column", "label")
        resolved_target = _resolve_target_column(train_file, requested_target)
        hyperparameters = cfg.get("hyperparameters", {}) or {}

        raw_result = user_module.run_training(
            train_file=str(train_file),
            test_file=str(test_file),
            artifact_dir=str(artifact_dir),
            target_column=resolved_target,
            hyperparameters=hyperparameters,
        )

        if not isinstance(raw_result, dict):
            raise TypeError(f"run_training() must return a dict, got {type(raw_result).__name__}")

        y_true = raw_result.get("y_true")
        y_prob = raw_result.get("y_prob")
        user_metrics = raw_result.get("metrics")

        if isinstance(user_metrics, dict):
            final_metrics = dict(user_metrics)
        else:
            final_metrics = {
                k: v for k, v in raw_result.items() if k not in ("y_true", "y_prob", "metrics")
            }

        if y_true is not None and y_prob is not None:
            y_true_arr = np.asarray(y_true, dtype=int).ravel()
            y_prob_arr = np.asarray(y_prob, dtype=float).ravel()
            computed = _compute_standard_metrics(y_true_arr, y_prob_arr)
            for k, v in computed.items():
                final_metrics.setdefault(k, v)

            eval_df = pd.DataFrame({
                "y_true": y_true_arr,
                "y_prob": np.clip(y_prob_arr, 0.0, 1.0),
            })
            eval_df.to_parquet(output_dir / "eval_predictions.parquet", index=False)

        with open(output_dir / "metrics.json", "w", encoding="utf-8") as f:
            json.dump(final_metrics, f, indent=2)

    elif args.mode == "inference":
        if not hasattr(user_module, "run_inference"):
            raise AttributeError(f"Entrypoint '{entrypoint_path.name}' must define 'run_inference(...)'")

        input_file = Path(args.input_file).resolve()
        artifact_dir = Path(args.artifact_dir).resolve()
        output_file = Path(args.output_file).resolve()

        y_prob = user_module.run_inference(
            input_file=str(input_file),
            artifact_dir=str(artifact_dir),
        )

        y_prob_arr = np.asarray(y_prob, dtype=float).ravel()
        if np.isnan(y_prob_arr).any() or np.isinf(y_prob_arr).any():
            raise ValueError("run_inference() returned NaN or Inf values in probability output.")

        y_prob_arr = np.clip(y_prob_arr, 0.0, 1.0)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"y_prob": y_prob_arr}).to_parquet(output_file, index=False)


if __name__ == "__main__":
    main()
'''


def write_runner_script(target_dir: Path) -> Path:
    """Write the `_usfds_runner.py` script into `target_dir` and return its path."""
    target_dir.mkdir(parents=True, exist_ok=True)
    runner_path = target_dir / RUNNER_SCRIPT_FILENAME
    runner_path.write_text(RUNNER_SCRIPT_TEMPLATE, encoding="utf-8")
    return runner_path
