from datetime import datetime, timezone
import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from usfds_core.domain.entities.enums import (
    DatasetRole,
    ExecutionType,
    ModelVersionStatus,
    PipelineStage,
    TrainingRunStatus,
    ValidationStatus,
)
from usfds_core.domain.entities.model import Model, ModelVersion, TrainingRun
from usfds_core.domain.schemas.model_plugin import ModelPluginManifest
from usfds_core.domain.schemas.training_config import TrainingRunConfig
from usfds_core.domain.schemas.training_payload import TrainingRunPayload, TrainingRunResult
from usfds_core.repositories.base_dataset_artifact_repo import IDatasetArtifactRepository
from usfds_core.repositories.base_model_repo import IModelRepository
from usfds_core.repositories.base_model_version_repo import IModelVersionRepository
from usfds_core.repositories.base_training_run_repo import ITrainingRunRepository
from usfds_core.services.training.dispatchers.base_dispatcher import ITrainingRunDispatcher
from usfds_core.services.training.plugins.register import ModelPluginRegistrationService
from usfds_core.storage.base_storage import IFileStorage
from usfds_core.storage.in_memory_storage import InMemoryFileStorage

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
        file_storage: Optional[IFileStorage] = None,
        plugin_registry: Optional[ModelPluginRegistrationService] = None,
    ):
        self.dispatcher = dispatcher
        self.training_run_repo = training_run_repo
        self.model_version_repo = model_version_repo
        self.model_repo = model_repo
        self.dataset_artifact_repo = dataset_artifact_repo
        self.file_storage = file_storage or InMemoryFileStorage()
        self.plugin_registry = plugin_registry or ModelPluginRegistrationService(
            model_repo=self.model_repo,
            file_storage=self.file_storage,
        )

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

        allowed_stages = (PipelineStage.FEATURE_ENGINEERED, PipelineStage.PRE_PROCESSED)
        if artifact.pipeline_stage not in allowed_stages:
            raise ValueError(
                f"Training requires a FEATURE_ENGINEERED or PRE_PROCESSED dataset artifact, but received '{artifact.pipeline_stage}'."
            )

        if artifact.validation_status == ValidationStatus.FAILED:
            raise ValueError(
                "Cannot initiate training run on a dataset artifact with validation status FAILED."
            )

        output_paths = artifact.output_paths or {}
        train_storage_path = output_paths.get("train") or output_paths.get("train_enriched")
        if not train_storage_path:
            raise ValueError("Dataset artifact must specify an output path for 'train'.")
        test_storage_path = output_paths.get("test") or output_paths.get("test_enriched")

        # 3. Extract target column from validation report
        val_report = artifact.validation_report or {}
        target_column = val_report.get("target_column", "label")

        # 4. Merge hyperparameters
        default_params = model.default_hyperparameters or {}
        run_params = config.hyperparameters or {}
        merged_params = {**default_params, **run_params}

        # 5. Create TrainingRun
        run_name = (
            config.run_name
            or f"run-{model.model_name}-{int(datetime.now(timezone.utc).timestamp())}"
        )
        resolved_project_id = config.project_id or model.project_id
        run = TrainingRun(
            project_id=resolved_project_id,
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
                project_id=run.project_id,
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

    def register_plugged_model(
        self,
        model_artifact_path: Optional[str] = None,
        user_id: Optional[Union[UUID, str]] = "mock_user",
        project_id: Optional[UUID] = None,
        manifest_override: Optional[ModelPluginManifest] = None,
        zip_bytes: Optional[bytes] = None,
    ) -> Model:
        """Validate and register a user-imported custom model plugin from storage path, local directory/zip, or raw ZIP bytes."""
        if zip_bytes is not None:
            model, validation_result = self.plugin_registry.register_from_zip(
                zip_bytes=zip_bytes,
                user_id=user_id,
                manifest_override=manifest_override,
                project_id=project_id,
            )
        else:
            if not model_artifact_path:
                raise ValueError("Either model_artifact_path or zip_bytes must be provided.")

            local_path = Path(model_artifact_path)
            if self.file_storage.exists(model_artifact_path):
                model_source = self.file_storage.read_bytes(model_artifact_path)
                model, validation_result = self.plugin_registry.register_from_zip(
                    zip_bytes=model_source,
                    user_id=user_id,
                    manifest_override=manifest_override,
                    project_id=project_id,
                )
            elif local_path.is_dir():
                model, validation_result = self.plugin_registry.register_from_directory(
                    plugin_dir=local_path,
                    user_id=user_id,
                    manifest_override=manifest_override,
                    project_id=project_id,
                )
            elif local_path.is_file():
                model_source = local_path.read_bytes()
                model, validation_result = self.plugin_registry.register_from_zip(
                    zip_bytes=model_source,
                    user_id=user_id,
                    manifest_override=manifest_override,
                    project_id=project_id,
                )
            else:
                raise ValueError(f"Model artifact at {model_artifact_path} not found.")

        if model:
            logger.info(f"Model registered: {model.model_name} (ID: {model.model_id})")
            return model

        logger.error(f"Model registration failed: {validation_result.errors}")
        raise ValueError(f"Model registration failed: {validation_result.errors}")

    def register_builtin_model(
        self,
        model_name: str,
        user_id: Optional[Union[UUID, str]] = "system",
        project_id: Optional[UUID] = None,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        default_hyperparameters: Optional[Dict[str, Any]] = None,
        hyperparameter_schema: Optional[Dict[str, Any]] = None,
    ) -> Model:
        """Register a built-in algorithm model (e.g., 'random_forest' or 'xgboost') in the Model Registry."""
        supported_builtins = {"random_forest", "rf", "xgboost", "xgb"}
        if model_name.strip().lower() not in supported_builtins:
            raise ValueError(
                f"Unsupported built-in model '{model_name}'. Supported built-in models: {sorted(supported_builtins)}"
            )

        resolved_user_id = self.plugin_registry._resolve_user_id(user_id)
        model = Model(
            project_id=project_id,
            model_name=model_name.strip().lower(),
            user_id=resolved_user_id,
            display_name=display_name or model_name,
            description=description,
            execution_type=ExecutionType.BUILTIN,
            default_hyperparameters=default_hyperparameters or {},
            hyperparameter_schema=hyperparameter_schema or {},
        )
        self.model_repo.save(model)
        logger.info(f"Built-in model registered: {model.model_name} (ID: {model.model_id})")
        return model

    def list_models(self, project_id: Optional[UUID] = None) -> List[Model]:
        """List all registered models, optionally filtered by project_id."""
        models = self.model_repo.list_models()
        if project_id is not None:
            return [m for m in models if m.project_id == project_id or m.project_id is None]
        return models

    def get_model(self, model_id: UUID) -> Model:
        """Retrieve a Model by ID or raise ValueError if not found."""
        model = self.model_repo.get_by_id(model_id)
        if not model:
            raise ValueError(f"Model with ID {model_id} not found.")
        return model

    def list_model_versions(self, model_id: UUID) -> List[ModelVersion]:
        """List all versions registered for a given model."""
        self.get_model(model_id)
        return self.model_version_repo.list_by_model(model_id)

    def get_model_version(self, version_id: UUID) -> ModelVersion:
        """Retrieve a ModelVersion by ID or raise ValueError if not found."""
        version = self.model_version_repo.get_by_id(version_id)
        if not version:
            raise ValueError(f"ModelVersion with ID {version_id} not found.")
        return version

    def activate_model_version(
        self,
        version_id: UUID,
        decision_threshold: Optional[float] = None,
        description: Optional[str] = None,
    ) -> ModelVersion:
        """Verify artifact integrity, update decision_threshold, and set ModelVersion status to APPROVED (SUC-10)."""
        version = self.get_model_version(version_id)

        if not version.artifact_uri:
            raise ValueError("ModelVersion has no artifact_uri registered.")

        # 1. Read artifact bytes from storage or local filesystem to verify existence & SHA-256 checksum
        artifact_bytes: Optional[bytes] = None
        if self.file_storage.exists(version.artifact_uri):
            artifact_bytes = self.file_storage.read_bytes(version.artifact_uri)
        else:
            local_p = Path(version.artifact_uri)
            if local_p.is_file():
                artifact_bytes = local_p.read_bytes()

        if artifact_bytes is None:
            raise ValueError(
                f"Integrity check failed: Model artifact '{version.artifact_uri}' does not exist in storage."
            )

        if version.checksum_sha256:
            actual_checksum = hashlib.sha256(artifact_bytes).hexdigest()
            if actual_checksum != version.checksum_sha256:
                raise ValueError(
                    "Integrity check failed: Model artifact SHA-256 checksum mismatch."
                )

        # 2. Update threshold and optional description
        if decision_threshold is not None:
            if not (0.0 < decision_threshold < 1.0):
                raise ValueError("decision_threshold must be strictly between 0.0 and 1.0.")
            version.decision_threshold = round(float(decision_threshold), 4)

        if description is not None:
            version.description = description

        # 3. Independently activate version (APPROVED)
        version.status = ModelVersionStatus.APPROVED
        self.model_version_repo.save(version)
        logger.info(
            f"Activated ModelVersion {version.version_id} ({version.semver}) "
            f"with threshold={version.decision_threshold}."
        )
        return version

    def get_run_dataset_artifact_id(self, run_id: UUID) -> Optional[UUID]:
        """Return the primary training dataset_artifact_id linked to a training run."""
        linked = self.training_run_repo.get_linked_datasets(run_id)
        if not linked:
            return None
        return linked[0].dataset_artifact_id

    def list_training_runs(
        self,
        model_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None,
    ) -> List[TrainingRun]:
        """List training runs, optionally filtered by model_id and/or project_id."""
        if model_id is not None:
            runs = self.training_run_repo.list_by_model(model_id)
        else:
            models = self.model_repo.list_models()
            runs = []
            for m in models:
                runs.extend(self.training_run_repo.list_by_model(m.model_id))
            runs.sort(key=lambda r: r.created_at, reverse=True)

        if project_id is not None:
            runs = [
                r for r in runs
                if r.project_id == project_id or r.project_id is None
            ]
        return runs

    def get_training_run(self, run_id: UUID) -> TrainingRun:
        """Retrieve a TrainingRun by ID or raise ValueError if not found."""
        run = self.training_run_repo.get_by_id(run_id)
        if not run:
            raise ValueError(f"TrainingRun with ID {run_id} not found.")
        return run
        
        
        
        
