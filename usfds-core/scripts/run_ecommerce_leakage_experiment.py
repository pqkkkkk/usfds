#!/usr/bin/env python3
"""End-to-End Experiment Script to Evaluate Data Leakage in Missing Value Imputation.

This script quantitatively investigates whether applying statistical imputation
(mean / median) BEFORE chronological train/test splitting introduces data leakage,
inflating test evaluation metrics (lookahead bias / overoptimism), compared to the
proper machine learning standard (splitting BEFORE fitting imputer).

Features:
1. Artificial Missingness Injection (MCAR):
   - Injects controllable missing rates (e.g. 20%) into continuous numerical features
     (amount, shipping_distance_km, avg_amount_user, account_age_days).
2. Side-by-Side Comparative Execution (--mode compare):
   - Pipeline A (Proper - Standard USFDS): Split train/test FIRST -> Fit imputer strictly on train -> Transform test.
   - Pipeline B (Leaked - Bad Practice): Impute missing values across ENTIRE dataset FIRST -> Split train/test afterwards.
   - Optional Baseline (--include-clean-baseline): Run on clean dataset with 0% missing values for ground truth reference.
3. Automatic Metric Comparison & Leakage Analysis:
   - Compares imputed statistical parameters (mu_train vs mu_global).
   - Generates comprehensive side-by-side performance table (Accuracy, Precision, Recall, F1, F2, ROC-AUC, PR-AUC).
   - Computes empirical Data Leakage Delta (Score_leaked - Score_proper).
"""

import argparse
import io
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import uuid4
import joblib
import numpy as np
import pandas as pd

# Ensure usfds_core package is accessible from python path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.enums import PipelineStage, ValidationStatus
from usfds_core.domain.schemas.preprocessing_config import (
    CategoricalEncoderType,
    CleansingConfig,
    DimReductionConfig,
    DimReductionType,
    FeatureEngineeringConfig,
    PreprocessingConfig,
    ResamplingConfig,
    ResamplingStrategy,
    ScalerType,
    SplitConfig,
    TransformationConfig,
)
from usfds_core.domain.schemas.training_payload import TrainingRunPayload
from usfds_core.services.preprocessing.feature_engineering_service import FeatureEngineeringExecutionService
from usfds_core.services.preprocessing.leaked_feature_engineering_service import (
    LeakedFeatureEngineeringExecutionService,
)
from usfds_core.services.preprocessing.preprocessing_service import PreprocessingExecutionService
from usfds_core.services.training.executor import TrainingRunExecutor
from usfds_core.storage.base_storage import IFileStorage


class LocalFileStorage(IFileStorage):
    """Local filesystem implementation of IFileStorage for artifact persistence."""

    def __init__(self, base_dir: Union[str, Path] = "."):
        self.base_dir = Path(base_dir).resolve()

    def _resolve_path(self, file_path: str) -> Path:
        p = Path(file_path)
        if p.is_absolute():
            return p
        return (self.base_dir / p).resolve()

    def save_bytes(self, file_path: str, data: bytes) -> str:
        target = self._resolve_path(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return str(target)

    def read_bytes(self, file_path: str) -> bytes:
        target = self._resolve_path(file_path)
        if not target.is_file():
            raise FileNotFoundError(f"File not found in local storage: {target}")
        return target.read_bytes()

    def exists(self, file_path: str) -> bool:
        target = self._resolve_path(file_path)
        return target.is_file()


def inject_missing_values(
    df: pd.DataFrame,
    columns: List[str],
    missing_rate: float = 0.2,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """Artificially injects Missing Completely At Random (MCAR) null values into specified columns."""
    df_corrupted = df.copy()
    rng = np.random.RandomState(random_state)
    injection_summary = {}

    n_rows = len(df_corrupted)
    n_missing = int(n_rows * missing_rate)

    for col in columns:
        if col not in df_corrupted.columns:
            continue
        missing_indices = rng.choice(n_rows, size=n_missing, replace=False)
        df_corrupted.loc[df_corrupted.index[missing_indices], col] = np.nan
        injection_summary[col] = n_missing

    return df_corrupted, injection_summary


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run End-to-End Imputation Data Leakage Experiment on E-Commerce Dataset"
    )
    workspace_root = PROJECT_ROOT.parent
    default_csv = workspace_root / "datasets" / "e-commerce-fraud-detection-dataset" / "mapped.csv"

    parser.add_argument(
        "--data-path",
        type=str,
        default=str(default_csv),
        help="Path to mapped.csv dataset file",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(PROJECT_ROOT / "storage_output" / "leakage_experiments"),
        help="Base storage directory for experiment artifacts",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["compare", "proper", "leaky"],
        default="compare",
        help="Experiment execution mode: compare (both side-by-side), proper (only proper split), leaky (only leaked imputer)",
    )
    parser.add_argument(
        "--missing-rate",
        type=float,
        default=0.2,
        help="Ratio of values to artificially mask as missing in specified columns (default: 0.2 = 20%%)",
    )
    parser.add_argument(
        "--missing-cols",
        type=str,
        default="amount,shipping_distance_km,avg_amount_user,account_age_days",
        help="Comma-separated numerical columns to inject missingness (default: amount,shipping_distance_km,avg_amount_user,account_age_days)",
    )
    parser.add_argument(
        "--missing-strategy",
        type=str,
        choices=["mean", "median"],
        default="mean",
        help="Statistical imputation strategy to test for data leakage (default: mean; options: mean, median)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for missingness injection and model reproducibility (default: 42)",
    )
    parser.add_argument(
        "--include-clean-baseline",
        action="store_true",
        help="Include clean uncorrupted baseline (0%% missing) in comparison",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Fraction of latest chronological transactions for test evaluation (default: 0.2)",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional row limit for fast testing (default: None, runs on full dataset)",
    )
    # Model arguments
    parser.add_argument(
        "--model",
        type=str,
        choices=["random_forest", "xgboost"],
        default="random_forest",
        help="Model algorithm to train (default: random_forest)",
    )
    parser.add_argument(
        "--class-weight",
        type=str,
        choices=["none", "balanced", "balanced_subsample"],
        default="balanced",
        help="Class weight strategy for imbalance (default: balanced)",
    )
    parser.add_argument(
        "--n-estimators",
        type=int,
        default=100,
        help="Number of trees (default: 100)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help="Maximum depth of trees (default: None)",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=0.1,
        help="Learning rate for XGBoost (default: 0.1)",
    )
    parser.add_argument(
        "--scaler",
        type=str,
        choices=["standard", "minmax", "robust", "none"],
        default="robust",
        help="Feature scaler type (default: standard)",
    )
    parser.add_argument(
        "--encoder",
        type=str,
        choices=["one_hot", "ordinal", "binary"],
        default="one_hot",
        help="Categorical encoder type (default: one_hot)",
    )
    parser.add_argument(
        "--dim-reduction",
        type=str,
        choices=["none", "pca", "rfe", "select_k_best_f2", "select_k_best_mi"],
        default="none",
        help="Dimensionality reduction technique (default: none)",
    )
    parser.add_argument(
        "--resampling",
        type=str,
        choices=["none", "smote", "adasyn", "random_under"],
        default="none",
        help="Resampling strategy (default: none)",
    )
    return parser.parse_args()


def run_pipeline_flow(
    pipeline_name: str,
    fe_service_class: Any,
    input_storage_key: str,
    storage: LocalFileStorage,
    args: argparse.Namespace,
    is_clean_baseline: bool = False,
) -> Dict[str, Any]:
    """Executes Stages 1, 2, and 3 for a given pipeline configuration and returns metrics."""
    print("\n" + "=" * 80)
    print(f"RUNNING PIPELINE: [{pipeline_name.upper()}]")
    print("=" * 80)

    dataset_id = uuid4()
    mapped_artifact = DatasetArtifact(
        dataset_id=dataset_id,
        storage_path=str(Path(input_storage_key).parent),
        output_paths={"mapped": input_storage_key},
        pipeline_stage=PipelineStage.MAPPED,
        validation_status=ValidationStatus.PASSED,
    )

    # --------------------------------------------------------------------------
    # STAGE 1: Feature Engineering & Cleansing
    # --------------------------------------------------------------------------
    effective_missing_strat = "none" if is_clean_baseline else args.missing_strategy
    fe_config = FeatureEngineeringConfig(
        split=SplitConfig(
            time_column="timestamp",
            target_column="label",
            test_size=args.test_size,
        ),
        cleansing=CleansingConfig(
            drop_duplicates=True,
            missing_value_strategy=effective_missing_strat,
            num_impute_strategy=effective_missing_strat,
            num_fill_value=-999.0,
            cat_impute_strategy="mode",
            cat_fill_value="missing",
        ),
        time_col="timestamp",
        amount_col="amount",
        user_id_col=None,
        enable_amount_ratios=False,
        enable_hour_of_day=False,
        enable_velocity_features=False,
    )

    fe_start = time.time()
    fe_service = fe_service_class(file_storage=storage)
    print(f"[{pipeline_name}] Executing {fe_service_class.__name__}...")
    fe_artifact = fe_service.execute(
        parent_artifact=mapped_artifact,
        config=fe_config,
        user_name="experiment_runner",
    )
    fe_duration = time.time() - fe_start

    # Extract imputer stats if available
    imputer_values = {}
    try:
        fitted_engineers_path = fe_artifact.output_paths.get("fitted_engineers")
        if fitted_engineers_path and storage.exists(fitted_engineers_path):
            engineers_bytes = storage.read_bytes(fitted_engineers_path)
            engineers_dict = joblib.load(io.BytesIO(engineers_bytes))
            cleanser = engineers_dict.get("cleanser")
            if cleanser and hasattr(cleanser, "imputation_values_"):
                imputer_values = cleanser.imputation_values_
    except Exception as exc:
        print(f"[{pipeline_name}] Note: Could not extract imputer parameters: {exc}")

    print(f"[{pipeline_name}] Stage 1 done ({fe_duration:.2f}s). Train rows: {fe_artifact.row_count:,}")
    if imputer_values:
        print(f"[{pipeline_name}] Imputation stats learned: {imputer_values}")

    # --------------------------------------------------------------------------
    # STAGE 2: Preprocessing (Scaling, Encoding)
    # --------------------------------------------------------------------------
    prep_config = PreprocessingConfig(
        split=SplitConfig(
            time_column="timestamp",
            target_column="label",
        ),
        transformation=TransformationConfig(
            numeric_columns=[],
            categorical_columns=[],
            scaler=ScalerType(args.scaler),
            categorical_encoder=CategoricalEncoderType(args.encoder),
        ),
        dim_reduction=DimReductionConfig(
            method=DimReductionType(args.dim_reduction),
            n_components=50,
        ),
        resampling=ResamplingConfig(
            method=ResamplingStrategy(
                "random_undersampling" if args.resampling == "random_under" else args.resampling
            ),
        ),
    )

    prep_start = time.time()
    prep_service = PreprocessingExecutionService(file_storage=storage)
    print(f"[{pipeline_name}] Executing PreprocessingExecutionService...")
    prep_artifact = prep_service.execute(
        parent_artifact=fe_artifact,
        config=prep_config,
        user_name="experiment_runner",
    )
    prep_duration = time.time() - prep_start
    print(f"[{pipeline_name}] Stage 2 done ({prep_duration:.2f}s). Features: {prep_artifact.column_count}")

    # --------------------------------------------------------------------------
    # STAGE 3: Model Training & Evaluation
    # --------------------------------------------------------------------------
    train_bytes = storage.read_bytes(prep_artifact.output_paths["train"])
    train_df = pd.read_parquet(io.BytesIO(train_bytes))

    hyperparameters = {}
    if args.n_estimators is not None:
        hyperparameters["n_estimators"] = args.n_estimators
    if args.max_depth is not None:
        hyperparameters["max_depth"] = args.max_depth
    if args.model in ["xgboost", "xgb"] and args.learning_rate is not None:
        hyperparameters["learning_rate"] = args.learning_rate
    if args.model in ["random_forest", "rf"] and args.class_weight and args.class_weight != "none":
        hyperparameters["class_weight"] = args.class_weight
    elif args.model in ["xgboost", "xgb"] and args.class_weight and args.class_weight != "none":
        if "label" in train_df.columns:
            counts = train_df["label"].value_counts()
            pos_count = counts.get(1, 0)
            neg_count = counts.get(0, 0)
            if pos_count > 0:
                hyperparameters["scale_pos_weight"] = round(float(neg_count / pos_count), 2)

    train_start = time.time()
    run_id = uuid4()
    payload = TrainingRunPayload(
        run_id=run_id,
        model_id=uuid4(),
        model_name=args.model,
        execution_type="BUILTIN",
        train_storage_path=prep_artifact.output_paths["train"],
        test_storage_path=prep_artifact.output_paths["test"],
        target_column="label",
        hyperparameters=hyperparameters,
    )

    training_executor = TrainingRunExecutor(file_storage=storage)
    print(f"[{pipeline_name}] Training {args.model.upper()}...")
    training_result = training_executor.run(payload)
    train_duration = time.time() - train_start

    if not training_result.is_success:
        raise RuntimeError(f"Pipeline {pipeline_name} training failed: {training_result.error_message}")

    metrics = training_result.metrics
    print(f"[{pipeline_name}] Stage 3 done ({train_duration:.2f}s).")
    print(f"[{pipeline_name}] PR-AUC: {metrics.get('pr_auc', 0.0):.6f} | ROC-AUC: {metrics.get('roc_auc', 0.0):.6f} | F1: {metrics.get('f1_score', 0.0):.6f}")

    return {
        "name": pipeline_name,
        "metrics": metrics,
        "imputer_values": imputer_values,
        "fe_duration": fe_duration,
        "train_duration": train_duration,
    }


def main():
    args = parse_arguments()
    data_path = Path(args.data_path).resolve()
    output_dir = Path(args.output_dir).resolve()

    print("=" * 80)
    print("DATA LEAKAGE EXPERIMENT IN MISSING VALUE IMPUTATION")
    print("=" * 80)
    print(f"Dataset Path           : {data_path}")
    print(f"Output Storage Dir     : {output_dir}")
    print(f"Execution Mode         : {args.mode}")
    print(f"Artificial Missing Rate: {args.missing_rate * 100:.1f}%")
    print(f"Injected Missing Cols  : {args.missing_cols}")
    print(f"Imputation Strategy    : {args.missing_strategy.upper()}")
    print(f"Model Algorithm        : {args.model.upper()} (class_weight={args.class_weight})")
    print(f"Temporal Test Ratio    : {args.test_size}")
    if args.max_rows:
        print(f"Max Rows Limit         : {args.max_rows:,}")
    print("=" * 80)

    if not data_path.is_file():
        print(f"[ERROR] Input data file does not exist: {data_path}")
        sys.exit(1)

    storage = LocalFileStorage(base_dir=output_dir)

    # 1. Load data (optionally limited by max_rows)
    print("\n[Step 1] Loading raw dataset...")
    if args.max_rows:
        df_raw = pd.read_csv(data_path, nrows=args.max_rows)
    else:
        df_raw = pd.read_csv(data_path)

    print(f"Loaded {len(df_raw):,} rows, {len(df_raw.columns)} columns.")

    # 2. Prepare Clean Baseline Storage File (if needed)
    clean_storage_key = "datasets/experiments/mapped_clean_baseline.csv"
    buf_clean = io.StringIO()
    df_raw.to_csv(buf_clean, index=False)
    storage.save_bytes(clean_storage_key, buf_clean.getvalue().encode("utf-8"))

    # 3. Inject Artificial Missingness (MCAR)
    missing_cols_list = [c.strip() for c in args.missing_cols.split(",") if c.strip()]
    print(f"\n[Step 2] Injecting {args.missing_rate * 100:.1f}% MCAR missing values into: {missing_cols_list}...")
    df_corrupted, injection_stats = inject_missing_values(
        df=df_raw,
        columns=missing_cols_list,
        missing_rate=args.missing_rate,
        random_state=args.seed,
    )

    for col, count in injection_stats.items():
        print(f"  - Column '{col}': {count:,} nulls injected ({count / len(df_raw) * 100:.1f}%)")

    corrupted_storage_key = "datasets/experiments/mapped_corrupted_mcar.csv"
    buf_corr = io.StringIO()
    df_corrupted.to_csv(buf_corr, index=False)
    storage.save_bytes(corrupted_storage_key, buf_corr.getvalue().encode("utf-8"))

    results = {}

    # 4. Execute Pipelines based on mode
    if args.mode in ["proper", "compare"]:
        # PIPELINE PROPER: Split FIRST, then fit imputer only on Train
        proper_result = run_pipeline_flow(
            pipeline_name="Proper (Split THEN Impute)",
            fe_service_class=FeatureEngineeringExecutionService,
            input_storage_key=corrupted_storage_key,
            storage=storage,
            args=args,
            is_clean_baseline=False,
        )
        results["proper"] = proper_result

    if args.mode in ["leaky", "compare"]:
        # PIPELINE LEAKED: Impute on ENTIRE dataset FIRST, then split (Data Leakage)
        leaked_result = run_pipeline_flow(
            pipeline_name="Leaked (Impute THEN Split)",
            fe_service_class=LeakedFeatureEngineeringExecutionService,
            input_storage_key=corrupted_storage_key,
            storage=storage,
            args=args,
            is_clean_baseline=False,
        )
        results["leaky"] = leaked_result

    if args.include_clean_baseline and args.mode == "compare":
        # PIPELINE BASELINE: Clean data without missing values
        clean_result = run_pipeline_flow(
            pipeline_name="Clean Baseline (0% Missing)",
            fe_service_class=FeatureEngineeringExecutionService,
            input_storage_key=clean_storage_key,
            storage=storage,
            args=args,
            is_clean_baseline=True,
        )
        results["clean"] = clean_result

    # --------------------------------------------------------------------------
    # 5. Comparative Reporting & Leakage Quantifications
    # --------------------------------------------------------------------------
    if args.mode == "compare" and "proper" in results and "leaky" in results:
        print("\n" + "#" * 80)
        print("EXPERIMENTAL RESULTS & DATA LEAKAGE COMPARISON")
        print("#" * 80)

        # A. Imputation Statistics Comparison
        proper_imp = results["proper"].get("imputer_values", {})
        leaked_imp = results["leaky"].get("imputer_values", {})

        print("\n### 1. Learned Imputation Values (Parameter Divergence):")
        print("| Column Name | Train-Only Value (Proper) | Global Value (Leaked) | Absolute Difference | Relative Bias (%) |")
        print("|:---|:---:|:---:|:---:|:---:|")
        for col in missing_cols_list:
            v_prop = proper_imp.get(col, np.nan)
            v_leak = leaked_imp.get(col, np.nan)
            if pd.notnull(v_prop) and pd.notnull(v_leak):
                diff = abs(v_leak - v_prop)
                rel_bias = (diff / abs(v_prop) * 100) if v_prop != 0 else 0.0
                print(f"| `{col}` | {v_prop:.4f} | {v_leak:.4f} | {diff:.4f} | {rel_bias:.2f}% |")
            else:
                print(f"| `{col}` | {v_prop} | {v_leak} | - | - |")

        # B. Model Performance Metrics Comparison
        p_met = results["proper"]["metrics"]
        l_met = results["leaky"]["metrics"]
        c_met = results.get("clean", {}).get("metrics", {})

        metrics_keys = [
            ("ROC-AUC", "roc_auc"),
            ("PR-AUC (Average Precision)", "pr_auc"),
            ("F1-Score", "f1_score"),
            ("F2-Score (Fraud-weighted)", "f2_score"),
            ("Precision", "precision"),
            ("Recall", "recall"),
            ("Accuracy", "accuracy"),
        ]

        print("\n### 2. Fraud Detection Performance Comparison:")
        if c_met:
            print("| Evaluation Metric | Clean Baseline | Proper (No Leakage) | Leaked (Pre-imputation) | Delta (Leaked - Proper) | Status |")
            print("|:---|:---:|:---:|:---:|:---:|:---:|")
            for label, key in metrics_keys:
                c_val = c_met.get(key, 0.0)
                p_val = p_met.get(key, 0.0)
                l_val = l_met.get(key, 0.0)
                delta = l_val - p_val
                status = "[+] INFLATED" if delta > 0.0005 else ("[-] DEGRADED" if delta < -0.0005 else "EQUIVALENT")
                print(f"| **{label}** | {c_val:.6f} | {p_val:.6f} | {l_val:.6f} | {delta:+.6f} | {status} |")
        else:
            print("| Evaluation Metric | Proper (No Leakage) | Leaked (Pre-imputation) | Delta (Leaked - Proper) | Status |")
            print("|:---|:---:|:---:|:---:|:---:|")
            for label, key in metrics_keys:
                p_val = p_met.get(key, 0.0)
                l_val = l_met.get(key, 0.0)
                delta = l_val - p_val
                status = "[+] INFLATED" if delta > 0.0005 else ("[-] DEGRADED" if delta < -0.0005 else "EQUIVALENT")
                print(f"| **{label}** | {p_val:.6f} | {l_val:.6f} | {delta:+.6f} | {status} |")

        # C. Confusion Matrix Breakdown
        p_cm = p_met.get("confusion_matrix", {})
        l_cm = l_met.get("confusion_matrix", {})
        print("\n### 3. Confusion Matrix Breakdown:")
        print(f"- Proper: TN={p_cm.get('tn', 0):,}, FP={p_cm.get('fp', 0):,}, FN={p_cm.get('fn', 0):,}, TP={p_cm.get('tp', 0):,}")
        print(f"- Leaked: TN={l_cm.get('tn', 0):,}, FP={l_cm.get('fp', 0):,}, FN={l_cm.get('fn', 0):,}, TP={l_cm.get('tp', 0):,}")

        print("\n" + "=" * 80)
        print("EXPERIMENT COMPLETED SUCCESSFULLY")
        print("=" * 80)


if __name__ == "__main__":
    main()
