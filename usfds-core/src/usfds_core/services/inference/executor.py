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
	ActiveRuleSnapshot,
	BatchInferencePayload,
	BatchInferenceResult,
)
from usfds_core.domain.schemas.preprocessing_config import NON_ML_COLUMNS
from usfds_core.services.inference.scoring_service import ModelScorer
from usfds_core.services.inference.workspace import InferenceWorkspace
from usfds_core.services.rule_engine.executor import JsonLogicEvaluator, RuleExecutor
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
    else:
        # Fallback canonical column alias resolution when legacy MAPPED artifacts omitted column_mapping
        canonical_aliases: Dict[str, list[str]] = {
            "event_id": ["transaction_id", "TransactionID", "tx_id", "id", "trans_num"],
            "timestamp": ["transaction_time", "TransactionDT", "tx_time", "time", "Time", "datetime", "date_time", "trans_date_trans_time"],
            "amount": ["transaction_amount", "TransactionAmt", "tx_amount", "amt", "Amount"],
            "user_id": ["customer_id", "client_id", "account_id", "card1", "CLIENTNUM"],
            "label": ["is_fraud", "isFraud", "target", "fraud", "Class", "class"],
        }
        fallback_rename: Dict[str, str] = {}
        for canonical_col, aliases in canonical_aliases.items():
            if canonical_col not in df.columns:
                for alias in aliases:
                    if alias in df.columns and alias not in fallback_rename:
                        fallback_rename[alias] = canonical_col
                        break
        if fallback_rename:
            df = df.rename(columns=fallback_rename)

    # 2. Validate presence of required canonical columns
    ignored_labels = {"label", "class", "target", "is_fraud", "isfraud"}
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

    def _try_load_companion_feature_engineers(self, model_uri: str, workspace: InferenceWorkspace) -> Optional[Any]:
        """Attempt to load `fitted_feature_engineers.joblib` saved alongside `model.joblib` in the model run directory."""
        parent_uri = str(Path(model_uri).parent / "fitted_feature_engineers.joblib").replace("\\", "/")
        try:
            fe_bytes = self._read_bytes(parent_uri)
            with open(workspace.fitted_engineers_path, "wb") as f:
                f.write(fe_bytes)
            return joblib.load(workspace.fitted_engineers_path)
        except Exception:
            return None

    def _try_load_companion_column_mapping(self, model_uri: str) -> Dict[str, str]:
        """Attempt to load `column_mapping.json` saved alongside `model.joblib` in the model run directory."""
        parent_uri = str(Path(model_uri).parent / "column_mapping.json").replace("\\", "/")
        try:
            cm_bytes = self._read_bytes(parent_uri)
            parsed = json.loads(cm_bytes.decode("utf-8"))
            if isinstance(parsed, dict):
                return {str(k): str(v) for k, v in parsed.items() if v}
        except Exception:
            pass
        return {}

    def _evaluate_hybrid_decisions(
        self,
        raw_df: pd.DataFrame,
        enriched_df: pd.DataFrame,
        model_scores: np.ndarray,
        has_model: bool,
        threshold: float,
        use_rules: bool,
        active_rules: list[ActiveRuleSnapshot],
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Evaluates active rules and combines with model_scores according to BR-DT-07:
        REJECT (Rule REJECT) > REVIEW (Rule REVIEW or model_score >= threshold) > ALLOW.
        """
        total_records = len(enriched_df)
        raw_records = raw_df.to_dict(orient="records")
        enriched_records = enriched_df.to_dict(orient="records")

        # Resolve amount column for Amount at Risk calculation
        amount_col: Optional[str] = None
        for cand in ("amount", "tx_amount", "transaction_amount", "amt", "Amount"):
            if cand in enriched_df.columns:
                amount_col = cand
                break
            if cand in raw_df.columns:
                amount_col = cand
                break

        id_col: Optional[str] = None
        for cand in ("event_id", "transaction_id", "tx_id", "id"):
            if cand in enriched_df.columns:
                id_col = cand
                break
            if cand in raw_df.columns:
                id_col = cand
                break

        rule_hit_counts: Dict[str, int] = {r.rule_code: 0 for r in active_rules}
        triggered_rules_col: list[str] = []
        triggered_details_col: list[str] = []
        rule_action_col: list[str] = []
        final_action_col: list[str] = []
        is_flagged_col: list[int] = []

        reject_count = 0
        review_count = 0
        allow_count = 0
        amount_at_risk = 0.0

        for idx in range(total_records):
            raw_row = raw_records[idx] if idx < len(raw_records) else {}
            enr_row = enriched_records[idx]

            clean_raw: Dict[str, Any] = {}
            for k, v in raw_row.items():
                if isinstance(v, float) and np.isnan(v):
                    clean_raw[str(k)] = None
                elif hasattr(v, "item"):
                    clean_raw[str(k)] = v.item()
                else:
                    clean_raw[str(k)] = v

            clean_enr: Dict[str, Any] = {}
            for k, v in enr_row.items():
                if isinstance(v, float) and np.isnan(v):
                    clean_enr[str(k)] = None
                elif hasattr(v, "item"):
                    clean_enr[str(k)] = v.item()
                else:
                    clean_enr[str(k)] = v

            merged_features = {**clean_raw, **clean_enr}
            tx_id = str(
                merged_features.get(id_col)
                if id_col and merged_features.get(id_col) is not None
                else idx + 1
            )
            m_score = float(model_scores[idx]) if idx < len(model_scores) else 0.0

            eval_payload: Dict[str, Any] = {
                **merged_features,
                "transaction_id": tx_id,
                "model_score": m_score,
                "raw": clean_raw,
                "raw_features": clean_raw,
                "mapped": clean_enr,
                "mapped_features": clean_enr,
                "enriched": clean_enr,
                "enriched_features": clean_enr,
                "model": {"score": m_score, "fraud_probability": m_score},
            }

            row_triggered_codes: list[str] = []
            row_triggered_details: list[Dict[str, Any]] = []
            highest_rule_action = "ALLOW"

            if use_rules and active_rules:
                for r in active_rules:
                    try:
                        matched = bool(JsonLogicEvaluator.evaluate(r.condition, eval_payload))
                    except Exception:
                        matched = False
                    if matched:
                        row_triggered_codes.append(r.rule_code)
                        rule_hit_counts[r.rule_code] = rule_hit_counts.get(r.rule_code, 0) + 1
                        clauses = RuleExecutor._extract_matched_clauses(r.condition, eval_payload)
                        if not clauses:
                            clauses = [f"{r.rule_code} condition matched"]
                        r_act = str(r.action).upper()
                        row_triggered_details.append(
                            {
                                "rule_id": r.rule_id,
                                "rule_version_id": r.rule_version_id,
                                "version_number": r.version_number,
                                "rule_code": r.rule_code,
                                "rule_name": r.rule_name,
                                "action": r_act,
                                "matched_clauses": clauses,
                            }
                        )
                        if r_act == "REJECT":
                            highest_rule_action = "REJECT"
                        elif r_act == "REVIEW" and highest_rule_action != "REJECT":
                            highest_rule_action = "REVIEW"

            # Decision aggregation (BR-DT-07):
            # REJECT (from Rule REJECT) > REVIEW (from Rule REVIEW or model_score >= threshold) > ALLOW
            if highest_rule_action == "REJECT":
                final_action = "REJECT"
                reject_count += 1
            elif highest_rule_action == "REVIEW" or (has_model and m_score >= threshold):
                final_action = "REVIEW"
                review_count += 1
            else:
                final_action = "ALLOW"
                allow_count += 1

            flagged = 1 if final_action in ("REJECT", "REVIEW") else 0
            if flagged and amount_col and merged_features.get(amount_col) is not None:
                try:
                    amount_at_risk += float(merged_features[amount_col])
                except (ValueError, TypeError):
                    pass

            triggered_rules_col.append(json.dumps(row_triggered_codes))
            triggered_details_col.append(json.dumps(row_triggered_details))
            rule_action_col.append(highest_rule_action)
            final_action_col.append(final_action)
            is_flagged_col.append(flagged)

        result_df = enriched_df.copy()
        # Preserve any raw columns that were renamed so users can inspect both raw and canonical columns
        for col in raw_df.columns:
            if col not in result_df.columns:
                result_df[col] = raw_df[col].values

        result_df["model_score"] = np.round(model_scores, 6)
        result_df["fraud_probability"] = np.round(model_scores, 6)
        result_df["triggered_rules"] = triggered_rules_col
        result_df["triggered_rule_details"] = triggered_details_col
        result_df["rule_action"] = rule_action_col
        result_df["final_action"] = final_action_col
        result_df["is_flagged"] = is_flagged_col
        result_df["prediction"] = is_flagged_col

        # Build score distribution histogram (10 bins: 0.0-0.1, ..., 0.9-1.0)
        bins = np.linspace(0.0, 1.0, 11)
        clipped_scores = np.clip(model_scores, 0.0, 1.0)
        counts, _ = np.histogram(clipped_scores, bins=bins)
        flagged_arr = np.asarray(is_flagged_col, dtype=int) if len(is_flagged_col) > 0 else np.zeros(len(clipped_scores), dtype=int)

        score_distribution = []
        for i in range(len(counts)):
            low = round(float(bins[i]), 2)
            high = round(float(bins[i + 1]), 2)
            if i == len(counts) - 1:
                bin_mask = (clipped_scores >= bins[i]) & (clipped_scores <= bins[i + 1])
            else:
                bin_mask = (clipped_scores >= bins[i]) & (clipped_scores < bins[i + 1])
            flagged_in_bin = int(np.sum(flagged_arr[bin_mask])) if len(flagged_arr) > 0 else 0

            score_distribution.append({
                "bin": f"{low:.1f}-{high:.1f}",
                "lower": low,
                "upper": high,
                "count": int(counts[i]),
                "flagged_count": flagged_in_bin,
            })

        rule_breakdown = [
            {
                "rule_id": r.rule_id,
                "rule_code": r.rule_code,
                "rule_name": r.rule_name,
                "action": str(r.action).upper(),
                "version_number": r.version_number,
                "hit_count": rule_hit_counts.get(r.rule_code, 0),
                "hit_rate": round(rule_hit_counts.get(r.rule_code, 0) / max(1, total_records), 4),
            }
            for r in active_rules
        ]

        summary_metrics: Dict[str, Any] = {
            "total_records": total_records,
            "flagged_count": reject_count + review_count,
            "reject_count": reject_count,
            "review_count": review_count,
            "allow_count": allow_count,
            "amount_at_risk": round(amount_at_risk, 2),
            "has_model": has_model,
            "use_rules": use_rules,
            "active_rules_count": len(active_rules) if use_rules else 0,
            "score_threshold": threshold,
            "rule_trigger_breakdown": rule_breakdown,
            "score_distribution": score_distribution,
        }

        return result_df, summary_metrics

    def run(self, payload: BatchInferencePayload) -> BatchInferenceResult:
        """Executes the hybrid batch scoring workflow: download artifacts -> transform -> predict + evaluate rules -> upload -> notify."""
        start_time = time.time()
        workspace = InferenceWorkspace(
            inference_id=payload.job_id,
            deployment_id=payload.deployment_id or payload.model_version_id or "rule_only",
        )

        try:
            workspace.initialize()

            # 1. Optional Feature Engineering transformers
            fitted_engineers = None
            if payload.fe_artifact_path:
                logger.info(f"Downloading feature engineers from {payload.fe_artifact_path}...")
                try:
                    fe_bytes = self._read_bytes(payload.fe_artifact_path)
                    with open(workspace.fitted_engineers_path, "wb") as f:
                        f.write(fe_bytes)
                    fitted_engineers = joblib.load(workspace.fitted_engineers_path)
                except FileNotFoundError:
                    logger.warning(
                        f"Feature engineers file not found at {payload.fe_artifact_path}; trying companion artifact..."
                    )
                    if payload.model_artifact_uri:
                        fitted_engineers = self._try_load_companion_feature_engineers(
                            payload.model_artifact_uri, workspace
                        )
            elif payload.model_artifact_uri:
                fitted_engineers = self._try_load_companion_feature_engineers(
                    payload.model_artifact_uri, workspace
                )

            effective_column_mapping: Dict[str, str] = dict(payload.column_mapping or {})
            if not effective_column_mapping and payload.model_artifact_uri:
                effective_column_mapping = self._try_load_companion_column_mapping(payload.model_artifact_uri)

            # 2. Download and read input batch dataset
            logger.info(f"Downloading input batch dataset from {payload.input_path}...")
            input_bytes = self._read_bytes(payload.input_path)
            buffer = io.BytesIO(input_bytes)
            lower_input = payload.input_path.lower()
            if lower_input.endswith(".parquet") or lower_input.endswith(".pq"):
                raw_df = pd.read_parquet(buffer)
            elif lower_input.endswith(".json"):
                raw_df = pd.read_json(buffer)
            else:
                raw_df = pd.read_csv(buffer)

            if raw_df.empty:
                raise ValueError("Input batch dataset is empty.")

            threshold = getattr(payload, "decision_threshold", 0.5) or 0.5
            has_model = bool(payload.model_artifact_uri)

            # 3. Input preparation & schema validation (Dual-Schema)
            if has_model or effective_column_mapping:
                prepared_df = prepare_and_validate_input(raw_df, effective_column_mapping)
            else:
                prepared_df = raw_df.copy()

            # Apply domain feature engineers if available so rules can reference enriched features too
            fe_df = apply_domain_feature_engineers(prepared_df, fitted_engineers)

            # 4. Branch between AI Model Scoring (.zip plugin / .joblib builtin) and Rule-Only Mode
            if has_model and payload.model_artifact_uri:
                logger.info(f"Downloading model artifact from {payload.model_artifact_uri}...")
                model_bytes = self._read_bytes(payload.model_artifact_uri)

                if payload.model_artifact_uri.lower().endswith(".zip"):
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
            else:
                fraud_probs = np.zeros(len(fe_df), dtype=float)
                preds = np.zeros(len(fe_df), dtype=int)

            # 5. Evaluate Active Rules & Aggregate Final Decision (REJECT / REVIEW / ALLOW)
            result_df, summary_metrics = self._evaluate_hybrid_decisions(
                raw_df=raw_df,
                enriched_df=fe_df,
                model_scores=fraud_probs,
                has_model=has_model,
                threshold=threshold,
                use_rules=payload.use_rules,
                active_rules=payload.active_rules or [],
            )

            # 6. Write predictions to workspace
            result_df.to_parquet(workspace.output_predictions_path, index=False)

            # 7. Persist results to storage
            with open(workspace.output_predictions_path, "rb") as pf:
                output_bytes = pf.read()
            self.file_storage.save_bytes(payload.output_storage_path, output_bytes)

            total_records = len(result_df)
            fraud_records = int(summary_metrics["flagged_count"])
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
                summary_metrics=summary_metrics,
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
