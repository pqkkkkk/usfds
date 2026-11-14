"""FastAPI dependency providers for the `training` domain (moved from dependencies.py, 26-11-14, ISS-026)."""
from fastapi import Depends
from sqlalchemy.orm import Session
from usfds_core.domain.schemas.training_payload import TrainingRunPayload
from usfds_core.services.training.dispatchers.local_dispatcher import SynchronousRunDispatcher
from usfds_core.services.training.executor import TrainingRunExecutor
from usfds_core.services.training.notifiers.base_notifier import CallbackResultNotifier
from usfds_core.services.training.plugins.register import ModelPluginRegistrationService
from usfds_core.services.training.training_service import TrainingOrchestrationService
from usfds_infra.database import (
	SqliteDatasetArtifactRepository,
	SqliteModelRepository,
	SqliteModelVersionRepository,
	SqliteTrainingRunRepository,
)
from usfds_infra.job_queue import QueueTrainingDispatcher
from usfds_infra.storage.local_storage import LocalFileStorage
from usfds_server.providers.repos import get_artifact_repo, get_model_repo, get_model_version_repo, get_training_run_repo
from usfds_server.dependencies import get_db, get_storage, get_job_queue
from usfds_server.config import settings


def get_training_service(
    model_repo: SqliteModelRepository = Depends(get_model_repo),
    model_version_repo: SqliteModelVersionRepository = Depends(get_model_version_repo),
    training_run_repo: SqliteTrainingRunRepository = Depends(get_training_run_repo),
    artifact_repo: SqliteDatasetArtifactRepository = Depends(get_artifact_repo),
    storage: LocalFileStorage = Depends(get_storage),
) -> TrainingOrchestrationService:
    executor: TrainingRunExecutor | None = None

    def dispatch_fn(payload: TrainingRunPayload) -> None:
        assert executor is not None
        executor.run(payload)

    if settings.dispatch_backend == "queue":
        dispatcher = QueueTrainingDispatcher(get_job_queue())
    else:
        dispatcher = SynchronousRunDispatcher(executor_func=dispatch_fn)
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
        file_storage=storage,
        plugin_registry=plugin_registry,
    )
    executor = TrainingRunExecutor(
        file_storage=storage,
        notifier=CallbackResultNotifier(callback=service.handle_training_completion),
    )
    return service
