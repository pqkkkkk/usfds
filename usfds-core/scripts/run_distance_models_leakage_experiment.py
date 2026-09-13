#!/usr/bin/env python3
"""End-to-End Experiment Script to Evaluate Data Leakage on Distance & Margin-Sensitive Models.

Models Evaluated:
1. Logistic Regression (Linear, distance & log-odds sensitive, regularized hyperplane)
2. Support Vector Machine / SVM (Margin-based, highly sensitive to geometric coordinates and feature scaling)

Purpose:
Unlike Tree-based models (Random Forest, XGBoost) which use orthogonal feature splits and are
relatively robust to coordinate shifts, Distance & Margin-based models rely directly on metric distances,
dot products, and geometric margins (w^T x + b = 0).
This script evaluates whether Imputation Data Leakage (computing global mean/median before temporal split)
has an amplified impact on Logistic Regression and SVM compared to tree ensembles.
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
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.svm import SVC, LinearSVC

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
from usfds_core.services.preprocessing.feature_engineering_service import FeatureEngineeringExecutionService
from usfds_core.services.preprocessing.leaked_feature_engineering_service import (
    LeakedFeatureEngineeringExecutionService,
)
from usfds_core.services.preprocessing.preprocessing_service import PreprocessingExecutionService
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
    """Artificially injects Missing Completely At Random (MCAR) null values into specified numerical columns."""
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
        description="Run Imputation Data Leakage Experiment on Distance-Sensitive Models (Logistic Regression & SVM)"
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
        default=str(PROJECT_ROOT / "storage_output" / "distance_models_leakage"),
        help="Base storage directory for experiment artifacts",
    )
    parser.add_argument(
        "--models",
        type=str,
        default="logistic_regression,svm",
        help="Comma-separated models to evaluate: 'logistic_regression', 'svm', or 'logistic_regression,svm'",
    )
    parser.add_argument(
        "--svm-type",
        type=str,
        choices=["linear", "rbf"],
        default="linear",
        help="SVM kernel type (default: linear with CalibratedClassifierCV; rbf uses SVC)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["compare", "proper", "leaky"],
        default="compare",
        help="Experiment mode: compare (Proper vs Leaked), proper (only proper), leaky (only leaked)",
    )
    parser.add_argument(
        "--missing-rate",
        type=float,
        default=0.2,
        help="Ratio of values to mask as missing in numerical columns (default: 0.2 = 20%%)",
    )
    parser.add_argument(
        "--missing-cols",
        type=str,
        default="amount,shipping_distance_km,avg_amount_user,account_age_days",
        help="Comma-separated numerical columns to inject missingness",
    )
    parser.add_argument(
        "--missing-strategy",
        type=str,
        choices=["mean", "median"],
        default="mean",
        help="Statistical imputation strategy to test (default: mean)",
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
        help="Fraction of latest transactions for test evaluation (default: 0.2)",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional row limit for fast testing (default: None, runs on full dataset)",
    )
    parser.add_argument(
        "--scaler",
        type=str,
        choices=["standard", "minmax", "robust"],
        default="standard",
        help="Feature scaler type (default: standard)",
    )
    parser.add_argument(
        "--class-weight",
        type=str,
        choices=["balanced", "none"],
        default="balanced",
        help="Class weight handling for imbalance (default: balanced)",
    )
    parser.add_argument(
        "--c-param",
        type=float,
        default=1.0,
        help="Regularization strength parameter C (default: 1.0)",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=1000,
        help="Maximum iterations for solver convergence (default: 1000)",
    )
    return parser.parse_args()


def build_and_train_model(
    model_name: str,
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    args: argparse.Namespace,
) -> Any:
    """Instantiates and fits distance/margin-based classifier."""
    cw = "balanced" if args.class_weight == "balanced" else None

    if model_name == "logistic_regression":
        model = LogisticRegression(
            C=args.c_param,
            class_weight=cw,
            max_iter=args.max_iter,
            random_state=args.seed,
            solver="lbfgs",
            n_jobs=-1,
        )
    elif model_name == "svm":
        if args.svm_type == "linear":
            base_svc = LinearSVC(
                C=args.c_param,
                class_weight=cw,
                max_iter=args.max_iter,
                random_state=args.seed,
                dual="auto",
            )
            model = CalibratedClassifierCV(estimator=base_svc, cv=3)
        else:
            model = SVC(
                C=args.c_param,
                kernel="rbf",
                probability=True,
                class_weight=cw,
                max_iter=args.max_iter,
                random_state=args.seed,
            )
    else:
        raise ValueError(f"Unsupported model: {model_name}")

    model.fit(X_train, y_train)
    return model


def evaluate_model(
    model: Any,
    X_test: pd.DataFrame,
    y_test: np.ndarray,
) -> Dict[str, Any]:
    """Computes fraud detection evaluation metrics."""
    y_pred = model.predict(X_test)
    if hasattr(model, "predict_proba"):
        y_prob = model.predict_proba(X_test)[:, 1]
    elif hasattr(model, "decision_function"):
        df_vals = model.decision_function(X_test)
        # Apply sigmoid to convert decision values to pseudo-probabilities
        y_prob = 1.0 / (1.0 + np.exp(-df_vals))
    else:
        y_prob = y_pred.astype(float)

    cm = confusion_matrix(y_test, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()

    roc_auc = float(roc_auc_score(y_test, y_prob)) if len(np.unique(y_test)) > 1 else 0.5
    pr_auc = float(average_precision_score(y_test, y_prob)) if len(np.unique(y_test)) > 1 else 0.0

    return {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1_score": float(f1_score(y_test, y_pred, zero_division=0)),
        "f2_score": float(fbeta_score(y_test, y_pred, beta=2, zero_division=0)),
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def execute_pipeline_stages(
    pipeline_name: str,
    fe_service_class: Any,
    input_storage_key: str,
    storage: LocalFileStorage,
    args: argparse.Namespace,
    model_name: str,
    is_clean_baseline: bool = False,
) -> Dict[str, Any]:
    """Executes FE Stage 1, Preprocessing Stage 2, and trains Logistic Regression / SVM."""
    dataset_id = uuid4()
    mapped_artifact = DatasetArtifact(
        dataset_id=dataset_id,
        storage_path=str(Path(input_storage_key).parent),
        output_paths={"mapped": input_storage_key},
        pipeline_stage=PipelineStage.MAPPED,
        validation_status=ValidationStatus.PASSED,
    )

    # Stage 1: Feature Engineering & Imputation
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
    fe_artifact = fe_service.execute(
        parent_artifact=mapped_artifact,
        config=fe_config,
        user_name="experiment_runner",
    )
    fe_duration = time.time() - fe_start

    # Extract learned imputer parameters
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
        pass

    # Stage 2: Preprocessing (One-hot encoding + Scaling)
    prep_config = PreprocessingConfig(
        split=SplitConfig(
            time_column="timestamp",
            target_column="label",
        ),
        transformation=TransformationConfig(
            numeric_columns=[],
            categorical_columns=[],
            scaler=ScalerType(args.scaler),
            categorical_encoder=CategoricalEncoderType.ONE_HOT,
        ),
        dim_reduction=DimReductionConfig(
            method=DimReductionType.NONE,
        ),
        resampling=ResamplingConfig(
            method=ResamplingStrategy.NONE,
        ),
    )

    prep_start = time.time()
    prep_service = PreprocessingExecutionService(file_storage=storage)
    prep_artifact = prep_service.execute(
        parent_artifact=fe_artifact,
        config=prep_config,
        user_name="experiment_runner",
    )
    prep_duration = time.time() - prep_start

    # Stage 3: Train Distance / Margin Model directly on preprocessed matrix
    train_bytes = storage.read_bytes(prep_artifact.output_paths["train"])
    train_df = pd.read_parquet(io.BytesIO(train_bytes))
    test_bytes = storage.read_bytes(prep_artifact.output_paths["test"])
    test_df = pd.read_parquet(io.BytesIO(test_bytes))

    target_col = "label"
    X_train = train_df.drop(columns=[target_col])
    y_train = train_df[target_col].values
    X_test = test_df.drop(columns=[target_col])
    y_test = test_df[target_col].values

    train_start = time.time()
    trained_model = build_and_train_model(model_name, X_train, y_train, args)
    train_duration = time.time() - train_start

    eval_metrics = evaluate_model(trained_model, X_test, y_test)

    print(
        f"[{pipeline_name} | {model_name.upper()}] "
        f"FE: {fe_duration:.2f}s, Prep: {prep_duration:.2f}s, Train: {train_duration:.2f}s | "
        f"ROC-AUC: {eval_metrics['roc_auc']:.6f} | PR-AUC: {eval_metrics['pr_auc']:.6f} | "
        f"F1: {eval_metrics['f1_score']:.6f} | TP: {eval_metrics['confusion_matrix']['tp']}"
    )

    return {
        "pipeline_name": pipeline_name,
        "model_name": model_name,
        "metrics": eval_metrics,
        "imputer_values": imputer_values,
        "fe_duration": fe_duration,
        "train_duration": train_duration,
    }


def print_comparison_table(
    model_name: str,
    p_res: Dict[str, Any],
    l_res: Dict[str, Any],
    c_res: Optional[Dict[str, Any]] = None,
):
    """Prints markdown comparison tables for a specific model."""
    print("\n" + "=" * 80)
    print(f"EXPERIMENT RESULTS: {model_name.upper()} (Distance / Margin Sensitive)")
    print("=" * 80)

    p_met = p_res["metrics"]
    l_met = l_res["metrics"]
    c_met = c_res["metrics"] if c_res else {}

    metrics_keys = [
        ("ROC-AUC", "roc_auc"),
        ("PR-AUC (Average Precision)", "pr_auc"),
        ("F1-Score", "f1_score"),
        ("F2-Score (Fraud-weighted)", "f2_score"),
        ("Precision", "precision"),
        ("Recall", "recall"),
        ("Accuracy", "accuracy"),
    ]

    print(f"\n### Model: {model_name.upper()} Performance Comparison:")
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

    p_cm = p_met["confusion_matrix"]
    l_cm = l_met["confusion_matrix"]
    print(f"\nConfusion Matrix ({model_name.upper()}):")
    print(f"- Proper: TN={p_cm['tn']:,}, FP={p_cm['fp']:,}, FN={p_cm['fn']:,}, TP={p_cm['tp']:,}")
    print(f"- Leaked: TN={l_cm['tn']:,}, FP={l_cm['fp']:,}, FN={l_cm['fn']:,}, TP={l_cm['tp']:,}")
    if c_met:
        c_cm = c_met["confusion_matrix"]
        print(f"- Clean Baseline: TN={c_cm['tn']:,}, FP={c_cm['fp']:,}, FN={c_cm['fn']:,}, TP={c_cm['tp']:,}")


def main():
    args = parse_arguments()
    data_path = Path(args.data_path).resolve()
    output_dir = Path(args.output_dir).resolve()

    selected_models = [m.strip().lower() for m in args.models.split(",") if m.strip()]

    print("=" * 80)
    print("DISTANCE & MARGIN MODELS: IMPUTATION DATA LEAKAGE EXPERIMENT")
    print("=" * 80)
    print(f"Dataset Path           : {data_path}")
    print(f"Output Storage Dir     : {output_dir}")
    print(f"Models to Evaluate     : {selected_models}")
    print(f"SVM Type               : {args.svm_type.upper()}")
    print(f"Execution Mode         : {args.mode}")
    print(f"Artificial Missing Rate: {args.missing_rate * 100:.1f}%")
    print(f"Injected Missing Cols  : {args.missing_cols}")
    print(f"Imputation Strategy    : {args.missing_strategy.upper()}")
    print(f"Scaler                 : {args.scaler.upper()}")
    print(f"Class Weight           : {args.class_weight.upper()}")
    if args.max_rows:
        print(f"Max Rows Limit         : {args.max_rows:,}")
    print("=" * 80)

    if not data_path.is_file():
        print(f"[ERROR] Input data file does not exist: {data_path}")
        sys.exit(1)

    storage = LocalFileStorage(base_dir=output_dir)

    # 1. Load data
    print("\n[Step 1] Loading raw dataset...")
    if args.max_rows:
        df_raw = pd.read_csv(data_path, nrows=args.max_rows)
    else:
        df_raw = pd.read_csv(data_path)

    print(f"Loaded {len(df_raw):,} rows, {len(df_raw.columns)} columns.")

    # 2. Prepare Clean Baseline Storage File
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

    # 4. Iterate over selected models and run pipelines
    all_results: Dict[str, Dict[str, Any]] = {}

    for model_name in selected_models:
        print(f"\n>>> EVALUATING ALGORITHM: {model_name.upper()} <<<")
        model_runs: Dict[str, Any] = {}

        if args.mode in ["proper", "compare"]:
            res_p = execute_pipeline_stages(
                pipeline_name="Proper (Split THEN Impute)",
                fe_service_class=FeatureEngineeringExecutionService,
                input_storage_key=corrupted_storage_key,
                storage=storage,
                args=args,
                model_name=model_name,
                is_clean_baseline=False,
            )
            model_runs["proper"] = res_p

        if args.mode in ["leaky", "compare"]:
            res_l = execute_pipeline_stages(
                pipeline_name="Leaked (Impute THEN Split)",
                fe_service_class=LeakedFeatureEngineeringExecutionService,
                input_storage_key=corrupted_storage_key,
                storage=storage,
                args=args,
                model_name=model_name,
                is_clean_baseline=False,
            )
            model_runs["leaky"] = res_l

        if args.include_clean_baseline and args.mode == "compare":
            res_c = execute_pipeline_stages(
                pipeline_name="Clean Baseline (0% Missing)",
                fe_service_class=FeatureEngineeringExecutionService,
                input_storage_key=clean_storage_key,
                storage=storage,
                args=args,
                model_name=model_name,
                is_clean_baseline=True,
            )
            model_runs["clean"] = res_c

        all_results[model_name] = model_runs

        if args.mode == "compare" and "proper" in model_runs and "leaky" in model_runs:
            print_comparison_table(
                model_name=model_name,
                p_res=model_runs["proper"],
                l_res=model_runs["leaky"],
                c_res=model_runs.get("clean"),
            )

    print("\n" + "=" * 80)
    print("ALL DISTANCE / MARGIN MODEL EXPERIMENTS COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    main()
