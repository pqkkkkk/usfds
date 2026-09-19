"""Batch Inference Executor for running worker-side model inference jobs.
Operates with zero direct database access.
"""

import io
import logging
from pathlib import Path
import time
from typing import Any, Callable, Dict, Optional, Union
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
from usfds_core.storage.base_storage import IFileStorage

logger = logging.getLogger(__name__)


def prepare_and_validate_input(
    input_df: pd.DataFrame,
    column_mapping: Dict[str, str],
) -> pd.DataFrame:
    """Validates input schema and performs automatic raw-to-canonical renaming (Dual-Schema).

    Args:
        input_df: Input dataframe to prepare.
        column_mapping: Mapping of raw column name -> canonical column name.

    Returns:
        Prepared dataframe with canonical column names.
    """
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


def run_feature_transformations(
    df: pd.DataFrame,
    fitted_engineers: Any,
    preprocessing_pipeline: Any,
    model: Any,
) -> Union[pd.DataFrame, np.ndarray]:
    """Sequentially applies stateful cleansing, domain feature engineering,
    column filtering, and fitted ML preprocessing transformations.
    """
    curr_df = df.copy()

    # Step 1: Stateful Cleansing
    if isinstance(fitted_engineers, dict) and "cleanser" in fitted_engineers:
        cleanser = fitted_engineers["cleanser"]
        curr_df = cleanser.clean(curr_df, time_col="timestamp", amount_col="amount")

    # Step 2: Domain Feature Engineering
    if isinstance(fitted_engineers, dict):
        if "credit_card_engineer" in fitted_engineers:
            cc_eng = fitted_engineers["credit_card_engineer"]
            curr_df = cc_eng.transform(curr_df)
        if "velocity_engineer" in fitted_engineers:
            vel_eng = fitted_engineers["velocity_engineer"]
            curr_df = vel_eng.transform(curr_df)

        # Apply any other custom fitted transformers
        for key, transformer in fitted_engineers.items():
            if key not in ("cleanser", "credit_card_engineer", "velocity_engineer"):
                if hasattr(transformer, "transform"):
                    curr_df = transformer.transform(curr_df)

    # Step 3: Filter non-predictive metadata/identifier columns
    cols_to_drop = [c for c in curr_df.columns if str(c).lower() in NON_ML_COLUMNS]
    X = curr_df.drop(columns=cols_to_drop)

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

    def run(self, payload: BatchInferencePayload) -> BatchInferenceResult:
        """Executes the batch scoring workflow: download artifacts -> transform -> predict -> upload -> notify."""
        start_time = time.time()
        workspace = InferenceWorkspace(
            inference_id=payload.job_id,
            deployment_id=payload.deployment_id,
        )

        try:
            workspace.initialize()

            # 1. Download & deserialize pipeline artifacts
            logger.info(f"Downloading feature engineers from {payload.fe_artifact_path}...")
            fe_bytes = self._read_bytes(payload.fe_artifact_path)
            with open(workspace.fitted_engineers_path, "wb") as f:
                f.write(fe_bytes)
            fitted_engineers = joblib.load(workspace.fitted_engineers_path)

            logger.info(f"Downloading preprocessing pipeline from {payload.prep_artifact_path}...")
            prep_bytes = self._read_bytes(payload.prep_artifact_path)
            with open(workspace.fitted_pipeline_path, "wb") as f:
                f.write(prep_bytes)
            preprocessing_pipeline = joblib.load(workspace.fitted_pipeline_path)

            logger.info(f"Downloading model artifact from {payload.model_artifact_uri}...")
            model_bytes = self._read_bytes(payload.model_artifact_uri)
            with open(workspace.model_path, "wb") as f:
                f.write(model_bytes)
            model = joblib.load(workspace.model_path)

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

            # 4. Feature transformations
            X = run_feature_transformations(
                prepared_df, fitted_engineers, preprocessing_pipeline, model
            )

            # 5. Model predictions using configurable decision threshold
            threshold = getattr(payload, "decision_threshold", 0.5) or 0.5
            preds, fraud_probs = ModelScorer.predict_with_probabilities(model, X, threshold=threshold)

            # 6. Preserve identifiers and append prediction columns
            result_df = prepared_df.copy()
            result_df["prediction"] = preds
            result_df["fraud_probability"] = np.round(fraud_probs, 6)

            # 7. Write predictions to workspace
            result_df.to_parquet(workspace.output_predictions_path, index=False)

            # 8. Persist results to storage
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
