"""Batch Inference Executor for running worker-side model inference jobs.
Operates with zero direct database access. Supports both Built-in models and self-contained Plugin Model Bundles.
"""

import io
import json
import logging
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Callable, Dict, Optional, Tuple, Union
import zipfile
import joblib
import numpy as np
import pandas as pd

from usfds_core.domain.schemas.inference_payload import (
    BatchInferencePayload,
    BatchInferenceResult,
)
from usfds_core.domain.schemas.preprocessing_config import NON_ML_COLUMNS
from usfds_core.services.inference.scoring_service import ModelScorer
from usfds_core.services.inference.workspace import InferenceWorkspace
from usfds_core.services.training.plugins.runner_template import write_runner_script
from usfds_core.storage.base_storage import IFileStorage

logger = logging.getLogger(__name__)


def prepare_and_validate_input(
    input_df: pd.DataFrame,
    column_mapping: Dict[str, str],
) -> pd.DataFrame:
    """Validates input schema and performs automatic raw-to-canonical renaming (Dual-Schema)."""
    df = input_df.copy()

    # 1. Dual-Schema: Rename raw columns to canonical if present
    if column_mapping:
        raw_rename_dict = {
            raw_col: canonical
            for raw_col, canonical in column_mapping.items()
            if raw_col in df.columns and canonical not in df.columns
        }
        if raw_rename_dict:
            df = df.rename(columns=raw_rename_dict)

    # 2. Validate presence of required canonical columns
    ignored_labels = {"label", "class", "target", "is_fraud"}
    required_canonical = [
        canonical
        for _, canonical in column_mapping.items()
        if canonical.lower() not in ignored_labels
    ]

    if required_canonical:
        missing_cols = [c for c in required_canonical if c not in df.columns]
        if missing_cols:
            reverse_mapping = {v: k for k, v in column_mapping.items()}
            hint_list = [
                f"'{c}' (or raw field '{reverse_mapping[c]}')" if c in reverse_mapping else f"'{c}'"
                for c in missing_cols
            ]
            raise ValueError(
                f"Input data is missing required feature columns: {', '.join(hint_list)}"
            )

    return df


def apply_domain_feature_engineers(
    df: pd.DataFrame,
    fitted_engineers: Optional[Any],
) -> pd.DataFrame:
    """Applies stateful cleansing and domain feature engineering to produce a FEATURE_ENGINEERED DataFrame."""
    curr_df = df.copy()
    if not fitted_engineers or not isinstance(fitted_engineers, dict):
        return curr_df

    # Step 1: Stateful Cleansing
    if "cleanser" in fitted_engineers:
        cleanser = fitted_engineers["cleanser"]
        curr_df = cleanser.clean(curr_df, time_col="timestamp", amount_col="amount")

    # Step 2: Domain Feature Engineering
    if "credit_card_engineer" in fitted_engineers:
        cc_eng = fitted_engineers["credit_card_engineer"]
        curr_df = cc_eng.transform(curr_df)
    if "velocity_engineer" in fitted_engineers:
        vel_eng = fitted_engineers["velocity_engineer"]
        curr_df = vel_eng.transform(curr_df)

    for key, transformer in fitted_engineers.items():
        if key not in ("cleanser", "credit_card_engineer", "velocity_engineer"):
            if hasattr(transformer, "transform"):
                curr_df = transformer.transform(curr_df)

    return curr_df


def run_feature_transformations(
    df: pd.DataFrame,
    fitted_engineers: Any,
    preprocessing_pipeline: Any,
    model: Any,
) -> Union[pd.DataFrame, np.ndarray]:
    """Sequentially applies stateful cleansing, domain feature engineering,
    column filtering, and fitted ML preprocessing transformations.
    """
    curr_df = apply_domain_feature_engineers(df, fitted_engineers)

    # Step 3: Filter non-predictive metadata/identifier columns
    cols_to_drop = [
        c for c in curr_df.columns
        if str(c).lower() in NON_ML_COLUMNS
        or pd.api.types.is_datetime64_any_dtype(curr_df[c])
    ]
    X = curr_df.drop(columns=cols_to_drop, errors="ignore")

    # Step 4: Apply fitted preprocessing pipeline (Scaling, One-Hot Encoding, PCA)
    if hasattr(preprocessing_pipeline, "steps"):
        X_curr = X
        for name, step in preprocessing_pipeline.steps:
            if hasattr(step, "transform"):
                X_curr = step.transform(X_curr)
    elif hasattr(preprocessing_pipeline, "transform"):
        X_curr = preprocessing_pipeline.transform(X)
    else:
        X_curr = X

    # Step 5: Align feature names with model expectations if needed
    if hasattr(model, "feature_names_in_") and not isinstance(X_curr, pd.DataFrame):
        X_curr = pd.DataFrame(X_curr, columns=model.feature_names_in_)

    return X_curr


def execute_plugin_bundle_inference(
    feature_engineered_df: pd.DataFrame,
    bundle_bytes: bytes,
    workspace: InferenceWorkspace,
    threshold: float = 0.5,
) -> Tuple[np.ndarray, np.ndarray]:
    """Unpack a self-contained `model_bundle.zip` and execute `run_inference` via `_usfds_runner.py`."""
    bundle_dir = workspace.artifacts_dir / "plugin_bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(bundle_bytes), "r") as zf:
        zf.extractall(bundle_dir)

    src_dir = bundle_dir / "src"
    artifact_dir = bundle_dir / "artifacts"
    if not src_dir.exists():
        src_dir = bundle_dir
    if not artifact_dir.exists():
        artifact_dir = bundle_dir

    manifest_path = src_dir / "plugin_manifest.json"
    entrypoint_name = "main.py"
    data_format = "parquet"
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as mf:
                manifest_data = json.load(mf)
                entrypoint_name = manifest_data.get("entrypoint", "main.py")
                data_format = manifest_data.get("data_format", "parquet")
        except Exception:
            pass

    entrypoint_path = src_dir / entrypoint_name
    if not entrypoint_path.exists():
        raise FileNotFoundError(f"Plugin entrypoint '{entrypoint_name}' not found inside model bundle.")

    runner_path = write_runner_script(src_dir)

    # Drop any ground-truth label columns before passing to run_inference
    unlabeled_df = feature_engineered_df.drop(
        columns=[c for c in feature_engineered_df.columns if str(c).lower() in ("label", "is_fraud", "target", "class")],
        errors="ignore",
    )

    ext = ".csv" if data_format.lower() == "csv" else ".parquet"
    input_file = workspace.input_dir / f"plugin_inference_input{ext}"
    if ext == ".csv":
        unlabeled_df.to_csv(input_file, index=False)
    else:
        unlabeled_df.to_parquet(input_file, index=False)

    output_probs_file = workspace.output_dir / "plugin_probs.parquet"

    cmd = [
        sys.executable,
        str(runner_path.resolve()),
        "--mode",
        "inference",
        "--entrypoint",
        str(entrypoint_path.resolve()),
        "--input-file",
        str(input_file.resolve()),
        "--artifact-dir",
        str(artifact_dir.resolve()),
        "--output-file",
        str(output_probs_file.resolve()),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Plugin inference failed with exit code {proc.returncode}.\n"
            f"STDERR: {proc.stderr}\nSTDOUT: {proc.stdout}"
        )

    if not output_probs_file.exists():
        raise FileNotFoundError("Plugin inference completed without writing output probability file.")

    probs_df = pd.read_parquet(output_probs_file)
    fraud_probs = np.asarray(probs_df["y_prob"], dtype=float).ravel()
    preds = (fraud_probs >= threshold).astype(int)
    return preds, fraud_probs


class BatchInferenceExecutor:
    """Worker-side batch inference execution engine.
    Executes the batch scoring pipeline without direct database access.
    """

    def __init__(
        self,
        file_storage: IFileStorage,
        notifier: Optional[Callable[[BatchInferenceResult], None]] = None,
    ):
        self.file_storage = file_storage
        self.notifier = notifier

    def _read_bytes(self, file_path_or_storage: Union[str, Path]) -> bytes:
        """Reads file bytes directly from local filesystem or through IFileStorage."""
        path_str = str(file_path_or_storage)
        p = Path(path_str)
        if p.is_file():
            return p.read_bytes()
        return self.file_storage.read_bytes(path_str)

    def _try_load_companion_preprocessor(self, model_uri: str, workspace: InferenceWorkspace) -> Optional[Any]:
        """Attempt to load `preprocessor.joblib` saved alongside `model.joblib` for FEATURE_ENGINEERED models."""
        parent_uri = str(Path(model_uri).parent / "preprocessor.joblib").replace("\\", "/")
        try:
            prep_bytes = self._read_bytes(parent_uri)
            with open(workspace.fitted_pipeline_path, "wb") as f:
                f.write(prep_bytes)
            return joblib.load(workspace.fitted_pipeline_path)
        except Exception:
            return None

    def run(self, payload: BatchInferencePayload) -> BatchInferenceResult:
        """Executes the batch scoring workflow: download artifacts -> transform -> predict -> upload -> notify."""
        start_time = time.time()
        workspace = InferenceWorkspace(
            inference_id=payload.job_id,
            deployment_id=payload.deployment_id,
        )

        try:
            workspace.initialize()

            # 1. Optional Feature Engineering transformers
            fitted_engineers = None
            if payload.fe_artifact_path:
                logger.info(f"Downloading feature engineers from {payload.fe_artifact_path}...")
                fe_bytes = self._read_bytes(payload.fe_artifact_path)
                with open(workspace.fitted_engineers_path, "wb") as f:
                    f.write(fe_bytes)
                fitted_engineers = joblib.load(workspace.fitted_engineers_path)

            # 2. Download and read input batch dataset
            logger.info(f"Downloading input batch dataset from {payload.input_path}...")
            input_bytes = self._read_bytes(payload.input_path)
            buffer = io.BytesIO(input_bytes)
            if payload.input_path.endswith(".parquet") or payload.input_path.endswith(".pq"):
                raw_df = pd.read_parquet(buffer)
            else:
                raw_df = pd.read_csv(buffer)

            if raw_df.empty:
                raise ValueError("Input batch dataset is empty.")

            # 3. Input preparation & schema validation (Dual-Schema)
            prepared_df = prepare_and_validate_input(raw_df, payload.column_mapping)
            threshold = getattr(payload, "decision_threshold", 0.5) or 0.5

            # 4. Branch between Plugin Model Bundle (.zip) and Built-in Model (.joblib)
            logger.info(f"Downloading model artifact from {payload.model_artifact_uri}...")
            model_bytes = self._read_bytes(payload.model_artifact_uri)

            if payload.model_artifact_uri.lower().endswith(".zip"):
                fe_df = apply_domain_feature_engineers(prepared_df, fitted_engineers)
                preds, fraud_probs = execute_plugin_bundle_inference(
                    feature_engineered_df=fe_df,
                    bundle_bytes=model_bytes,
                    workspace=workspace,
                    threshold=threshold,
                )
            else:
                with open(workspace.model_path, "wb") as f:
                    f.write(model_bytes)
                model = joblib.load(workspace.model_path)

                preprocessing_pipeline = None
                if payload.prep_artifact_path:
                    logger.info(f"Downloading preprocessing pipeline from {payload.prep_artifact_path}...")
                    prep_bytes = self._read_bytes(payload.prep_artifact_path)
                    with open(workspace.fitted_pipeline_path, "wb") as f:
                        f.write(prep_bytes)
                    preprocessing_pipeline = joblib.load(workspace.fitted_pipeline_path)
                else:
                    preprocessing_pipeline = self._try_load_companion_preprocessor(
                        payload.model_artifact_uri, workspace
                    )

                X = run_feature_transformations(
                    prepared_df, fitted_engineers, preprocessing_pipeline, model
                )
                preds, fraud_probs = ModelScorer.predict_with_probabilities(model, X, threshold=threshold)

            # 5. Preserve identifiers and append prediction columns
            result_df = prepared_df.copy()
            result_df["prediction"] = preds
            result_df["fraud_probability"] = np.round(fraud_probs, 6)

            # 6. Write predictions to workspace
            result_df.to_parquet(workspace.output_predictions_path, index=False)

            # 7. Persist results to storage
            with open(workspace.output_predictions_path, "rb") as pf:
                output_bytes = pf.read()
            self.file_storage.save_bytes(payload.output_storage_path, output_bytes)

            total_records = len(result_df)
            fraud_records = int((preds == 1).sum())
            fraud_rate = float(fraud_records / total_records) if total_records > 0 else 0.0
            duration = round(time.time() - start_time, 3)

            result = BatchInferenceResult(
                job_id=payload.job_id,
                is_success=True,
                output_path=payload.output_storage_path,
                total_records=total_records,
                fraud_records=fraud_records,
                fraud_rate=round(fraud_rate, 4),
                duration_seconds=duration,
            )

        except Exception as ex:
            logger.error(f"Batch inference job {payload.job_id} failed: {ex}", exc_info=True)
            result = BatchInferenceResult(
                job_id=payload.job_id,
                is_success=False,
                error_message=str(ex),
                duration_seconds=round(time.time() - start_time, 3),
            )
        finally:
            workspace.cleanup()

        if self.notifier:
            try:
                self.notifier(result)
            except Exception as ne:
                logger.warning(f"Notifier failed for job {payload.job_id}: {ne}")

        return result
