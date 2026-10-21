#!/usr/bin/env python3
"""Manual Execution & Verification Script for USFDS Model Plugin Architecture.

Runs the full 5-step End-to-End flow on the real FEATURE_ENGINEERED dataset
(`storage_output/datasets/bf842480-4581-4cf2-bccc-fc2f540ddfce/artifacts/f4b0bb1a-b7a4-4f5e-b856-78cd5054d49f`):
1. Upload & 2-Stage Validation (Static AST + Dynamic Dry-Run) of custom plugins in `custom-models/`.
2. Registration of `Model` metadata and `plugin_source.zip` into `storage_output/models/`.
3. Training Run on `train_enriched.parquet` & `test_enriched.parquet` -> produces `model_bundle.zip`,
   `model.joblib`, `preprocessor.joblib`, `metrics.json`, and `eval_predictions.parquet`.
4. Online Inference on a single transaction event.
5. Batch Inference on `test_enriched.parquet` -> produces `predictions.parquet`.
"""

import argparse
import json
from pathlib import Path
import sys
from typing import List, Optional, Union
from uuid import UUID, uuid4
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
CORE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = CORE_ROOT.parent
SRC_DIR = CORE_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.detection import Deployment, Pipeline
from usfds_core.domain.entities.enums import (
    DeploymentEnvironment,
    DeploymentStatus,
    PipelineStage,
    ValidationStatus,
)
from usfds_core.domain.schemas.training_config import TrainingRunConfig
from usfds_core.domain.schemas.training_payload import TrainingRunPayload
from usfds_core.repositories.in_memory_repos import (
    InMemoryDatasetArtifactRepository,
    InMemoryDetectionJobRepository,
    InMemoryModelRepository,
    InMemoryModelVersionRepository,
    InMemoryPipelineRepository,
    InMemoryTrainingRunRepository,
)
from usfds_core.services.inference.inference_service import InferenceService
from usfds_core.services.training.dispatchers.local_dispatcher import SynchronousRunDispatcher
from usfds_core.services.training.executor import TrainingRunExecutor
from usfds_core.services.training.notifiers.base_notifier import CallbackResultNotifier
from usfds_core.services.training.plugins import ModelPluginRegistrationService
from usfds_core.services.training.training_service import TrainingOrchestrationService
from usfds_core.storage.base_storage import IFileStorage


class LocalDiskStorage(IFileStorage):
    """Persists all artifacts directly into `storage_output/` on disk for manual inspection."""

    def __init__(self, base_dir: Union[str, Path]):
        self.base_dir = Path(base_dir).resolve()

    def _resolve(self, file_path: str) -> Path:
        p = Path(file_path)
        return p if p.is_absolute() else (self.base_dir / p).resolve()

    def save_bytes(self, file_path: str, data: bytes) -> str:
        target = self._resolve(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return str(target)

    def read_bytes(self, file_path: str) -> bytes:
        target = self._resolve(file_path)
        if not target.is_file():
            raise FileNotFoundError(f"File not found: {target}")
        return target.read_bytes()

    def exists(self, file_path: str) -> bool:
        return self._resolve(file_path).is_file()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test and inspect custom Model Plugins (LR, SVM, or custom folder) on FEATURE_ENGINEERED data."
    )
    parser.add_argument(
        "--plugin-dir",
        type=str,
        default=None,
        help="Path to a specific plugin directory (default: runs both custom-models/logistic_regression and custom-models/svm)",
    )
    parser.add_argument(
        "--dataset-artifact-dir",
        type=str,
        default=str(
            REPO_ROOT
            / "storage_output"
            / "datasets"
            / "bf842480-4581-4cf2-bccc-fc2f540ddfce"
            / "artifacts"
            / "f4b0bb1a-b7a4-4f5e-b856-78cd5054d49f"
        ),
        help="Path to the FEATURE_ENGINEERED artifact directory containing train_enriched.parquet and test_enriched.parquet",
    )
    parser.add_argument(
        "--storage-dir",
        type=str,
        default=str(REPO_ROOT / "storage_output"),
        help="Base storage_output directory where trained models and metrics will be written",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    storage_root = Path(args.storage_dir).resolve()
    fe_dir = Path(args.dataset_artifact_dir).resolve()

    train_pq = fe_dir / "train_enriched.parquet"
    test_pq = fe_dir / "test_enriched.parquet"
    fe_joblib = fe_dir / "fitted_feature_engineers.joblib"

    if not train_pq.exists() or not test_pq.exists():
        raise FileNotFoundError(f"Could not find train_enriched.parquet or test_enriched.parquet in {fe_dir}")

    if args.plugin_dir:
        plugin_dirs: List[Path] = [Path(args.plugin_dir).resolve()]
    else:
        plugin_dirs = [
            REPO_ROOT / "custom-models" / "logistic_regression",
            REPO_ROOT / "custom-models" / "svm",
        ]

    storage = LocalDiskStorage(base_dir=storage_root)
    model_repo = InMemoryModelRepository()
    run_repo = InMemoryTrainingRunRepository()
    version_repo = InMemoryModelVersionRepository()
    artifact_repo = InMemoryDatasetArtifactRepository()
    pipeline_repo = InMemoryPipelineRepository(use_storage_fallback=False)
    job_repo = InMemoryDetectionJobRepository()

    fe_artifact = DatasetArtifact(
        artifact_id=UUID("f4b0bb1a-b7a4-4f5e-b856-78cd5054d49f"),
        dataset_id=UUID("bf842480-4581-4cf2-bccc-fc2f540ddfce"),
        pipeline_stage=PipelineStage.FEATURE_ENGINEERED,
        storage_path=str(fe_dir),
        output_paths={
            "train": str(train_pq),
            "test": str(test_pq),
            "fitted_engineers": str(fe_joblib) if fe_joblib.exists() else "",
        },
        validation_status=ValidationStatus.PASSED,
        validation_report={"target_column": "label"},
    )
    artifact_repo.save(fe_artifact)

    executor: Optional[TrainingRunExecutor] = None

    def dispatch_fn(payload: TrainingRunPayload) -> None:
        assert executor is not None
        executor.run(payload)

    training_service = TrainingOrchestrationService(
        dispatcher=SynchronousRunDispatcher(executor_func=dispatch_fn),
        training_run_repo=run_repo,
        model_version_repo=version_repo,
        model_repo=model_repo,
        dataset_artifact_repo=artifact_repo,
    )
    executor = TrainingRunExecutor(
        file_storage=storage,
        notifier=CallbackResultNotifier(callback=training_service.handle_training_completion),
    )
    plugin_service = ModelPluginRegistrationService(
        model_repo=model_repo,
        file_storage=storage,
    )
    inference_service = InferenceService(
        pipeline_repo=pipeline_repo,
        file_storage=storage,
        detection_job_repo=job_repo,
    )

    sample_event = pd.read_parquet(test_pq).drop(columns=["label"], errors="ignore").iloc[0].to_dict()

    print("=" * 85)
    print(" USFDS MODEL PLUGIN END-TO-END RUNNER")
    print(f" Dataset (FEATURE_ENGINEERED): {fe_dir}")
    print(f" Persistent Storage Output   : {storage_root}")
    print("=" * 85)

    for p_dir in plugin_dirs:
        print(f"\n>>> [1/4] Validating & Registering Plugin: {p_dir.name} ({p_dir})")
        model, val_res = plugin_service.register_from_directory(plugin_dir=p_dir, user_id=uuid4())
        if not val_res.is_valid or model is None:
            print(f"    [FAILED] Validation errors: {val_res.errors}")
            continue

        print(f"    [PASSED] Static AST Check     : {val_res.static_check_passed}")
        print(f"    [PASSED] Dry-Run Training     : {val_res.dry_run_train_passed}")
        print(f"    [PASSED] Dry-Run Inference    : {val_res.dry_run_inference_passed}")
        print(f"    [INFO]   Detected Artifacts   : {val_res.detected_artifacts}")
        print(f"    [INFO]   Registered Model ID  : {model.model_id} (format={val_res.manifest.data_format})")

        print(f"\n>>> [2/4] Running Full Training on FEATURE_ENGINEERED Dataset for '{model.model_name}'...")
        run_cfg = TrainingRunConfig(
            model_id=model.model_id,
            dataset_artifact_id=fe_artifact.artifact_id,
            run_name=f"manual-run-{model.model_name}",
        )
        run = training_service.prepare_and_dispatch(run_cfg)
        completed_run = run_repo.get_by_id(run.run_id)
        version = version_repo.get_by_id(completed_run.version_id)

        run_output_dir = storage_root / "models" / str(model.model_id) / "runs" / str(run.run_id)
        metrics_file = run_output_dir / "metrics.json"
        metrics_data = json.loads(metrics_file.read_text(encoding="utf-8")) if metrics_file.exists() else {}

        print(f"    [STATUS]   {completed_run.status} in {completed_run.duration_seconds}s (SemVer: {version.semver})")
        print(f"    [METRICS]  Accuracy  : {completed_run.accuracy}")
        print(f"               Precision : {completed_run.precision_score}")
        print(f"               Recall    : {completed_run.recall_score}")
        print(f"               F1-Score  : {completed_run.f1_score}")
        print(f"               ROC-AUC   : {metrics_data.get('roc_auc')}")
        print(f"               PR-AUC    : {metrics_data.get('pr_auc')}")
        print(f"               Threshold : {version.decision_threshold}")
        print(f"    [FILES]    Run Folder          : {run_output_dir}")
        print(f"               Model Bundle (.zip) : {storage_root / version.artifact_uri}")
        print(f"               Metrics JSON        : {metrics_file}")
        print(f"               Eval Predictions    : {run_output_dir / 'eval_predictions.parquet'}")

        print(f"\n>>> [3/4] Testing Online Single-Event Inference for '{model.model_name}'...")
        deployment_id = uuid4()
        pipeline_repo.register_pipeline(
            deployment_id,
            Pipeline(
                feature_engineered_dataset_artifact=fe_artifact,
                model_version=version,
                deployment=Deployment(
                    deployment_id=deployment_id,
                    version_id=version.version_id,
                    deployment_name=f"deploy-{model.model_name}",
                    environment=DeploymentEnvironment.PRODUCTION,
                    status=DeploymentStatus.RUNNING,
                ),
            ),
        )
        online_res = inference_service.online_inference(deployment_id, sample_event)
        print(
            f"    [ONLINE]   Prediction={online_res['prediction']} | "
            f"Probability={online_res['probability']:.4f} | "
            f"RiskScore={online_res['risk_score']} | "
            f"Latency={online_res['latency_ms']} ms"
        )

        print(f"\n>>> [4/4] Testing Batch Inference on test_enriched.parquet for '{model.model_name}'...")
        job = inference_service.batch_inference(
            project_id=UUID("bf842480-4581-4cf2-bccc-fc2f540ddfce"),
            deployment_id=deployment_id,
            input_path=str(test_pq),
            job_name=f"batch-{model.model_name}",
        )
        completed_job = job_repo.get_by_id(job.job_id)
        pred_output_path = storage_root / completed_job.output_path
        print(
            f"    [BATCH]    Status={completed_job.status} | "
            f"Total={completed_job.total_records:,} | "
            f"Flagged Fraud={completed_job.fraud_records:,} ({completed_job.fraud_rate * 100:.2f}%)"
        )
        print(f"    [OUTPUT]   Predictions File: {pred_output_path}")
        print("-" * 85)


if __name__ == "__main__":
    main()
