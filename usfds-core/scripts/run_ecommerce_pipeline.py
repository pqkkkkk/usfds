#!/usr/bin/env python3
"""End-to-End Pipeline Execution Script for E-Commerce Fraud Detection Dataset.

Executes:
1. Stage FEATURE_ENGINEERED (FeatureEngineeringExecutionService):
   - Temporal train/test split to prevent future data leakage.
   - Stateful data cleansing (missing values imputation, duplicate removal).
   - Domain feature engineering (hour_of_day, amount_to_mean_ratio, optional velocity).
   - Saves train_enriched.parquet and test_enriched.parquet retaining all original metadata.

2. Stage PRE_PROCESSED (PreprocessingExecutionService):
   - Drops non-predictive identifiers/metadata (event_id, user_id, timestamp).
   - Transforms all predictive numerical features (Standard/Robust scaling).
   - Transforms all predictive categorical features (One-Hot / Ordinal encoding).
   - Preserves all predictive features without dropping any.
   - Saves train_processed.parquet, test_processed.parquet, and fitted_pipeline.joblib.
"""

import argparse
import io
from pathlib import Path
import sys
import time
from typing import Union
from uuid import uuid4
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
    MissingValueStrategy,
    PreprocessingConfig,
    ResamplingConfig,
    ResamplingStrategy,
    ScalerType,
    SplitConfig,
    TransformationConfig,
)
from usfds_core.services.preprocessing.feature_engineering_service import FeatureEngineeringExecutionService
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


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run End-to-End USFDS Pipeline on E-Commerce Fraud Detection Dataset"
    )
    # Default path resolves to datasets/e-commerce-fraud-detection-dataset/mapped.csv relative to workspace
    workspace_root = PROJECT_ROOT.parent
    default_csv = workspace_root / "datasets" / "e-commerce-fraud-detection-dataset" / "mapped.csv"

    parser.add_argument(
        "--data-path",
        type=str,
        default=str(default_csv),
        help=f"Path to input mapped CSV (default: {default_csv})",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(PROJECT_ROOT / "storage_output"),
        help="Base directory to save pipeline artifacts (default: usfds-core/storage_output)",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.3,
        help="Proportion of data for test split (default: 0.3, i.e. 70/30 train/test)",
    )
    parser.add_argument(
        "--scaler",
        type=str,
        choices=["robust", "standard", "minmax", "log1p"],
        default="robust",
        help="Scaler for numerical features (default: robust)",
    )
    parser.add_argument(
        "--encoder",
        type=str,
        choices=["one_hot", "ordinal", "binary"],
        default="one_hot",
        help="Encoder for categorical features (default: one_hot)",
    )
    parser.add_argument(
        "--dim-reduction",
        type=str,
        choices=["none", "pca", "select_k_best_mi", "select_k_best_f2", "rfe"],
        default="none",
        help="Dimensionality reduction / feature selection method (default: none, keeps all features)",
    )
    parser.add_argument(
        "--resampling",
        type=str,
        choices=[
            "none",
            "smote",
            "adasyn",
            "random_undersampling",
            "random_under",
            "tomek_links",
            "smote_tomek",
            "smote_enn",
        ],
        default="none",
        help="Resampling strategy for imbalanced data (default: none; options: none, smote, adasyn, random_undersampling, tomek_links, smote_tomek, smote_enn)",
    )
    parser.add_argument(
        "--enable-velocity",
        action="store_true",
        help="Enable rolling window velocity features (Note: takes several minutes on 300k rows)",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional limit on number of input rows (useful for fast testing)",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()
    data_path = Path(args.data_path).resolve()
    output_dir = Path(args.output_dir).resolve()

    print("=" * 80)
    print("USFDS PREPROCESSING & FEATURE ENGINEERING PIPELINE (END-TO-END)")
    print("=" * 80)
    print(f"Input Data File : {data_path}")
    print(f"Storage Dir     : {output_dir}")
    print(f"Test Size       : {args.test_size}")
    print(f"Scaler          : {args.scaler}")
    print(f"Encoder         : {args.encoder}")
    print(f"Dim Reduction   : {args.dim_reduction}")
    print(f"Resampling      : {args.resampling}")
    print(f"Velocity Features: {args.enable_velocity}")
    if args.max_rows:
        print(f"Max Rows Limit  : {args.max_rows}")
    print("=" * 80)

    if not data_path.is_file():
        print(f"[ERROR] Input data file does not exist: {data_path}")
        sys.exit(1)

    # Initialize file storage
    storage = LocalFileStorage(base_dir=output_dir)

    # If max-rows is specified, create a subsampled mapped CSV
    effective_data_path = str(data_path)
    if args.max_rows:
        print(f"\n[0/2] Preparing subsample with {args.max_rows:,} rows...")
        subsample_df = pd.read_csv(data_path, nrows=args.max_rows)
        sub_buf = io.StringIO()
        subsample_df.to_csv(sub_buf, index=False)
        sub_path = "datasets/staging/mapped_subsampled.csv"
        storage.save_bytes(sub_path, sub_buf.getvalue().encode("utf-8"))
        effective_data_path = sub_path
        print(f"      Subsampled dataset prepared at storage key: {sub_path}")

    # Inspect input schema
    sample_df = pd.read_csv(data_path, nrows=5)
    print("\n[Input Dataset Inspection]")
    print(f"Total input columns: {len(sample_df.columns)}")
    print(f"Columns: {list(sample_df.columns)}")

    # --------------------------------------------------------------------------
    # STAGE 1: FEATURE ENGINEERING (FeatureEngineeringExecutionService)
    # --------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("STAGE 1: FEATURE ENGINEERING (FeatureEngineeringExecutionService)")
    print("-" * 80)
    stage1_start = time.time()

    dataset_id = uuid4()
    mapped_artifact = DatasetArtifact(
        dataset_id=dataset_id,
        storage_path=effective_data_path,
        pipeline_stage=PipelineStage.MAPPED,
    )

    fe_config = FeatureEngineeringConfig(
        split=SplitConfig(
            time_column="timestamp",
            target_column="label",
            test_size=args.test_size,
        ),
        cleansing=CleansingConfig(
            drop_duplicates=True,
            missing_value_strategy=MissingValueStrategy.MEDIAN,
        ),
        time_col="timestamp",
        amount_col="amount",
        user_id_col="user_id",
        enable_amount_ratios=True,
        enable_hour_of_day=True,
        enable_velocity_features=args.enable_velocity,
        velocity_windows=[1, 24] if args.enable_velocity else [],
    )

    fe_service = FeatureEngineeringExecutionService(file_storage=storage)
    print("Executing FeatureEngineeringExecutionService.execute()...")
    fe_artifact = fe_service.execute(
        parent_artifact=mapped_artifact,
        config=fe_config,
        user_name="pipeline_runner",
    )
    stage1_duration = time.time() - stage1_start

    print(f" Stage 1 Completed in {stage1_duration:.2f}s")
    print(f" Artifact ID           : {fe_artifact.artifact_id}")
    print(f" Pipeline Stage        : {fe_artifact.pipeline_stage.value}")
    print(f" Validation Status     : {fe_artifact.validation_status.value}")
    print(f" Train Storage Path    : {fe_artifact.storage_path}")
    print(f" Test Storage Path     : {fe_artifact.test_storage_path}")
    print(f" Pipeline Transformers : {fe_artifact.pipeline_artifact_path}")
    print(f" Train Rows            : {fe_artifact.row_count:,}")
    print(f" Column Count          : {fe_artifact.column_count}")
    print(f" Validation Report     : {fe_artifact.validation_report}")

    # Inspect enriched columns
    train_enriched_bytes = storage.read_bytes(fe_artifact.storage_path)
    train_enriched_df = pd.read_parquet(io.BytesIO(train_enriched_bytes))
    print(f"\n[Stage 1 Enriched Features Preview]")
    print(f"Columns in enriched train set: {list(train_enriched_df.columns)}")

    # --------------------------------------------------------------------------
    # STAGE 2: PREPROCESSING & TRANSFORMATION (PreprocessingExecutionService)
    # --------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("STAGE 2: PREPROCESSING & TRANSFORMATION (PreprocessingExecutionService)")
    print("-" * 80)
    stage2_start = time.time()

    # Preprocessing Config using all features (auto-detected predictive features)
    prep_config = PreprocessingConfig(
        split=SplitConfig(
            time_column="timestamp",
            target_column="label",
        ),
        transformation=TransformationConfig(
            numeric_columns=[],     # Empty means auto-detect all numeric features
            categorical_columns=[], # Empty means auto-detect all categorical features
            scaler=ScalerType(args.scaler),
            categorical_encoder=CategoricalEncoderType(args.encoder),
        ),
        dim_reduction=DimReductionConfig(
            method=DimReductionType(args.dim_reduction),
        ),
        resampling=ResamplingConfig(
            method=ResamplingStrategy(
                "random_undersampling" if args.resampling == "random_under" else args.resampling
            ),
        ),
    )

    prep_service = PreprocessingExecutionService(file_storage=storage)
    print("Executing PreprocessingExecutionService.execute()...")
    prep_artifact = prep_service.execute(
        parent_artifact=fe_artifact,
        config=prep_config,
        user_name="pipeline_runner",
    )
    stage2_duration = time.time() - stage2_start

    print(f" Stage 2 Completed in {stage2_duration:.2f}s")
    print(f" Artifact ID           : {prep_artifact.artifact_id}")
    print(f" Pipeline Stage        : {prep_artifact.pipeline_stage.value}")
    print(f" Validation Status     : {prep_artifact.validation_status.value}")
    print(f" Train Processed Path  : {prep_artifact.storage_path}")
    print(f" Test Processed Path   : {prep_artifact.test_storage_path}")
    print(f" Fitted Pipeline Model : {prep_artifact.pipeline_artifact_path}")
    print(f" Train Rows            : {prep_artifact.row_count:,}")
    print(f" Total Features + Target: {prep_artifact.column_count}")
    print(f" Validation Report     : {prep_artifact.validation_report}")

    # Inspect processed datasets
    train_proc_bytes = storage.read_bytes(prep_artifact.storage_path)
    train_proc_df = pd.read_parquet(io.BytesIO(train_proc_bytes))
    test_proc_bytes = storage.read_bytes(prep_artifact.test_storage_path)
    test_proc_df = pd.read_parquet(io.BytesIO(test_proc_bytes))

    print("\n" + "=" * 80)
    print("PIPELINE EXECUTION SUMMARY")
    print("=" * 80)
    print(f"Train Matrix Shape : {train_proc_df.shape} (rows, columns)")
    print(f"Test Matrix Shape  : {test_proc_df.shape} (rows, columns)")
    print(f"Total Execution Time: {stage1_duration + stage2_duration:.2f} seconds")
    print("\nFeature Columns in Processed Output:")
    print(list(train_proc_df.columns))

    print("\nFirst 3 rows of processed train dataset:")
    print(train_proc_df.head(3))

    print("\nClass distribution in processed train dataset:")
    print(train_proc_df["label"].value_counts().to_dict())

    print("\n[SUCCESS] End-to-end pipeline finished cleanly.")
    print("=" * 80)


if __name__ == "__main__":
    main()
