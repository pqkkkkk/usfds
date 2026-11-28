"""FastAPI dependency providers for the `training` domain (moved from dependencies.py, 26-11-14, ISS-026)."""
from typing import Optional
from fastapi import Depends
from sqlalchemy.orm import Session
from usfds_core.domain.schemas.training_payload import TrainingRunPayload
from usfds_core.services.training.compute_policy import (
	ComputePolicyThresholds,
	ComputeSelectionPolicy,
)
from usfds_core.services.training.dispatchers.local_dispatcher import SynchronousRunDispatcher
from usfds_core.services.training.dispatchers.routing_dispatcher import RoutingTrainingDispatcher
from usfds_core.services.training.executor import TrainingRunExecutor
from usfds_core.services.training.notifiers.base_notifier import CallbackResultNotifier
from usfds_core.services.training.plugins.register import ModelPluginRegistrationService
from usfds_core.services.training.providers.base_provider import RemoteProviderRegistry
from usfds_core.services.training.training_service import TrainingOrchestrationService
from usfds_core.storage.base_storage import IFileStorage
from usfds_infra.compute import ModalTrainingProvider
from usfds_infra.database import (
	SqliteDatasetArtifactRepository,
	SqliteDatasetRepository,
	SqliteModelRepository,
	SqliteModelVersionRepository,
	SqliteTrainingRunRepository,
)
from usfds_infra.job_queue import QueueTrainingDispatcher
from usfds_server.providers.repos import get_artifact_repo, get_dataset_repo, get_model_repo, get_model_version_repo, get_training_run_repo
from usfds_server.dependencies import get_db, get_storage, get_job_queue
from usfds_server.config import settings


def get_remote_provider_registry(
    storage: IFileStorage = Depends(get_storage),
) -> RemoteProviderRegistry:
    """Build the remote compute provider registry from current server settings (ISS-009)."""
    registry = RemoteProviderRegistry()
    registry.register(
        ModalTrainingProvider(
            enabled=settings.modal_enabled,
            app_name=settings.modal_app_name,
            gpu_type=settings.modal_gpu_type,
            cpu_cores=settings.modal_cpu_cores,
            memory_mb=settings.modal_memory_mb,
            gpu_memory_mb=settings.modal_gpu_memory_mb,
            timeout_seconds=settings.modal_timeout_seconds,
            file_storage=storage,
            s3_public_endpoint_url=settings.s3_public_endpoint_url or settings.s3_endpoint_url or "",
        )
    )
    return registry


def get_compute_selection_policy() -> ComputeSelectionPolicy:
    """Build ComputeSelectionPolicy using configured thresholds (ISS-009)."""
    return ComputeSelectionPolicy(
        thresholds=ComputePolicyThresholds(
            row_count_threshold=settings.auto_compute_row_threshold,
        )
    )


def _assemble_training_service(
    model_repo: SqliteModelRepository,
    model_version_repo: SqliteModelVersionRepository,
    training_run_repo: SqliteTrainingRunRepository,
    artifact_repo: SqliteDatasetArtifactRepository,
    dataset_repo: SqliteDatasetRepository,
    storage: IFileStorage,
    provider_registry: RemoteProviderRegistry,
    compute_policy: ComputeSelectionPolicy,
) -> TrainingOrchestrationService:
    executor: Optional[TrainingRunExecutor] = None

    def dispatch_fn(payload: TrainingRunPayload) -> None:
        assert executor is not None
        executor.run(payload)

    if settings.dispatch_backend == "queue":
        local_dispatcher = QueueTrainingDispatcher(get_job_queue())
    else:
        local_dispatcher = SynchronousRunDispatcher(executor_func=dispatch_fn)

    dispatcher = RoutingTrainingDispatcher(
        local_dispatcher=local_dispatcher,
        provider_registry=provider_registry,
        file_storage=storage,
        presigned_ttl_seconds=settings.remote_presigned_ttl_seconds,
    )
    plugin_registry = ModelPluginRegistrationService(
        model_repo=model_repo,
        file_storage=storage,
    )
    service = TrainingOrchestrationService(
        dispatcher=dispatcher,
        training_run_repo=training_run_repo,
        model_version_repo=model_version_repo,
        model_repo=model_repo,
        dataset_artifact_repo=artifact_repo,
        dataset_repo=dataset_repo,
        file_storage=storage,
        plugin_registry=plugin_registry,
        provider_registry=provider_registry,
        compute_policy=compute_policy,
        remote_timeout_seconds=settings.modal_timeout_seconds,
    )
    executor = TrainingRunExecutor(
        file_storage=storage,
        notifier=CallbackResultNotifier(callback=service.handle_training_completion),
    )
    return service


def build_training_service_for_session(
    session: Session,
    storage: IFileStorage,
    provider_registry: RemoteProviderRegistry,
    compute_policy: ComputeSelectionPolicy,
) -> TrainingOrchestrationService:
    """Construct TrainingOrchestrationService bound to an explicit DB Session."""
    return _assemble_training_service(
        model_repo=SqliteModelRepository(session),
        model_version_repo=SqliteModelVersionRepository(session),
        training_run_repo=SqliteTrainingRunRepository(session),
        artifact_repo=SqliteDatasetArtifactRepository(session),
        dataset_repo=SqliteDatasetRepository(session),
        storage=storage,
        provider_registry=provider_registry,
        compute_policy=compute_policy,
    )


def get_training_service(
    model_repo: SqliteModelRepository = Depends(get_model_repo),
    model_version_repo: SqliteModelVersionRepository = Depends(get_model_version_repo),
    training_run_repo: SqliteTrainingRunRepository = Depends(get_training_run_repo),
    artifact_repo: SqliteDatasetArtifactRepository = Depends(get_artifact_repo),
    dataset_repo: SqliteDatasetRepository = Depends(get_dataset_repo),
    storage: IFileStorage = Depends(get_storage),
    provider_registry: RemoteProviderRegistry = Depends(get_remote_provider_registry),
    compute_policy: ComputeSelectionPolicy = Depends(get_compute_selection_policy),
) -> TrainingOrchestrationService:
    return _assemble_training_service(
        model_repo=model_repo,
        model_version_repo=model_version_repo,
        training_run_repo=training_run_repo,
        artifact_repo=artifact_repo,
        dataset_repo=dataset_repo,
        storage=storage,
        provider_registry=provider_registry,
        compute_policy=compute_policy,
    )
