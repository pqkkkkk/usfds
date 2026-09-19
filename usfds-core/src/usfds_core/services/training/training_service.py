from datetime import datetime, timezone
import logging
from typing import Optional
from uuid import UUID

from usfds_core.domain.entities.enums import (
    DatasetRole,
    ModelVersionStatus,
    PipelineStage,
    TrainingRunStatus,
    ValidationStatus,
)
from usfds_core.domain.entities.model import ModelVersion, TrainingRun
from usfds_core.domain.schemas.training_config import TrainingRunConfig
from usfds_core.domain.schemas.training_payload import TrainingRunPayload, TrainingRunResult
from usfds_core.repositories.base_dataset_artifact_repo import IDatasetArtifactRepository
from usfds_core.repositories.base_model_repo import IModelRepository
from usfds_core.repositories.base_model_version_repo import IModelVersionRepository
from usfds_core.repositories.base_training_run_repo import ITrainingRunRepository
from usfds_core.services.training.dispatchers.base_dispatcher import ITrainingRunDispatcher

logger = logging.getLogger(__name__)


class TrainingOrchestrationService:
    """Service orchestrating the complete lifecycle of Model Training:
    Pre-dispatch -> Dispatch -> Post-execution Registry Update.
    """

    def __init__(
        self,
        dispatcher: ITrainingRunDispatcher,
        training_run_repo: ITrainingRunRepository,
        model_version_repo: IModelVersionRepository,
        model_repo: IModelRepository,
        dataset_artifact_repo: IDatasetArtifactRepository,
    ):
        self.dispatcher = dispatcher
        self.training_run_repo = training_run_repo
        self.model_version_repo = model_version_repo
        self.model_repo = model_repo
        self.dataset_artifact_repo = dataset_artifact_repo

    def prepare_and_dispatch(
        self, config: TrainingRunConfig, user_name: str = "system"
    ) -> TrainingRun:
        """Pre-dispatch of training run. Validate, persist TrainingRun (PENDING/RUNNING), and dispatch payload."""
        # 1. Retrieve model
        model = self.model_repo.get_by_id(config.model_id)
        if not model:
            raise ValueError(f"Model with ID {config.model_id} not found.")

        # 2. Retrieve & validate dataset artifact
        artifact = self.dataset_artifact_repo.get_by_id(config.dataset_artifact_id)
        if not artifact:
            raise ValueError(f"DatasetArtifact with ID {config.dataset_artifact_id} not found.")

        if artifact.pipeline_stage != PipelineStage.PRE_PROCESSED:
            raise ValueError(
                f"Training requires a PRE_PROCESSED dataset artifact, but received '{artifact.pipeline_stage}'."
            )

        if artifact.validation_status == ValidationStatus.FAILED:
            raise ValueError(
                "Cannot initiate training run on a dataset artifact with validation status FAILED."
            )

        output_paths = artifact.output_paths or {}
        train_storage_path = output_paths.get("train")
        if not train_storage_path:
            raise ValueError("Preprocessed dataset artifact must specify an output path for 'train'.")
        test_storage_path = output_paths.get("test")

        # 3. Extract target column from validation report
        val_report = artifact.validation_report or {}
        target_column = val_report.get("target_column", "is_fraud")

        # 4. Merge hyperparameters
        default_params = model.default_hyperparameters or {}
        run_params = config.hyperparameters or {}
        merged_params = {**default_params, **run_params}

        # 5. Create TrainingRun
        run_name = (
            config.run_name
            or f"run-{model.model_name}-{int(datetime.now(timezone.utc).timestamp())}"
        )
        run = TrainingRun(
            model_id=model.model_id,
            run_name=run_name,
            hyperparameters=merged_params,
            compute_target=config.compute_target,
            status=TrainingRunStatus.PENDING,
            created_by=user_name,
        )
        self.training_run_repo.save(run)

        # 6. Link RunDataset
        self.training_run_repo.link_dataset(
            run_id=run.run_id,
            dataset_artifact_id=artifact.artifact_id,
            dataset_role=DatasetRole.TRAIN,
            sample_count=artifact.row_count,
        )

        # 7. Package Payload
        payload = TrainingRunPayload(
            run_id=run.run_id,
            model_id=model.model_id,
            model_name=model.model_name,
            execution_type=str(model.execution_type),
            entrypoint_uri=model.entrypoint_uri,
            train_storage_path=train_storage_path,
            test_storage_path=test_storage_path,
            target_column=target_column,
            hyperparameters=merged_params,
            compute_target=config.compute_target,
        )

        # 8. Mark running and dispatch
        run.status = TrainingRunStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        self.training_run_repo.save(run)

        logger.info(f"Dispatching training run {run.run_id} via {type(self.dispatcher).__name__}...")
        self.dispatcher.dispatch_run(payload)

        return run

    def handle_training_completion(self, result: TrainingRunResult) -> TrainingRun:
        """Post-execution of training run. Handle worker results and register candidate ModelVersion if succeeded."""
        run = self.training_run_repo.get_by_id(result.run_id)
        if not run:
            raise ValueError(f"TrainingRun with ID {result.run_id} not found.")

        run.completed_at = datetime.now(timezone.utc)
        run.duration_seconds = result.duration_seconds

        if result.is_success:
            run.status = TrainingRunStatus.COMPLETED
            run.accuracy = result.metrics.get("accuracy")
            run.precision_score = result.metrics.get("precision")
            run.recall_score = result.metrics.get("recall")
            run.f1_score = result.metrics.get("f1_score")
            run.loss = result.metrics.get("loss")
            run.custom_metrics = result.metrics
            run.metrics_path = getattr(result, "metrics_uri", None)
            run.eval_predictions_path = getattr(result, "eval_predictions_uri", None)

            rec = result.metrics.get("recommended_thresholds", {})
            if isinstance(rec, dict) and "best_f1" in rec and isinstance(rec["best_f1"], dict):
                run.recommended_threshold = rec["best_f1"].get("threshold")


            # Auto-increment semver
            next_semver = self._resolve_next_semver(run.model_id)

            model_version = ModelVersion(
                model_id=run.model_id,
                run_id=run.run_id,
                semver=next_semver,
                artifact_uri=result.artifact_uri or "",
                checksum_sha256=result.checksum_sha256,
                framework=result.framework,
                decision_threshold=run.recommended_threshold if run.recommended_threshold is not None else 0.5,
                status=ModelVersionStatus.CANDIDATE,
            )
            self.model_version_repo.save(model_version)
            run.version_id = model_version.version_id
            logger.info(f"Training run {run.run_id} succeeded. Registered ModelVersion {next_semver} with threshold {model_version.decision_threshold}.")
        else:
            run.status = TrainingRunStatus.FAILED
            run.error_message = result.error_message
            logger.error(f"Training run {run.run_id} failed: {result.error_message}")

        self.training_run_repo.save(run)
        return run

    def _resolve_next_semver(self, model_id: Optional[UUID]) -> str:
        """Determine next semver for candidate model release (auto-increment patch)."""
        if not model_id:
            return "1.0.0"

        latest = self.model_version_repo.get_latest_version(model_id)
        if not latest or not latest.semver:
            return "1.0.0"

        try:
            parts = latest.semver.split(".")
            if len(parts) == 3:
                major, minor, patch = map(int, parts)
                return f"{major}.{minor}.{patch + 1}"
            return f"{latest.semver}.1"
        except Exception:
            return "1.0.0"
