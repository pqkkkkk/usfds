"""Synchronous job handlers. Each opens its own DB session so that the worker never shares state between jobs."""

import logging
from dataclasses import dataclass
from typing import Any, Dict

from sqlalchemy.orm import Session, sessionmaker

from usfds_core.domain.schemas.inference_payload import BatchInferencePayload
from usfds_core.domain.schemas.training_payload import TrainingRunPayload
from usfds_core.services.inference.executor import BatchInferenceExecutor
from usfds_core.services.inference.inference_service import InferenceService
from usfds_core.services.rule_engine.manager import RuleManager
from usfds_core.services.training.executor import TrainingRunExecutor
from usfds_core.services.training.notifiers.base_notifier import CallbackResultNotifier
from usfds_core.services.training.training_service import TrainingOrchestrationService
from usfds_core.storage.base_storage import IFileStorage
from usfds_infra.database import (
	SqliteDatasetArtifactRepository,
	SqliteDatasetRepository,
	SqliteDetectionJobRepository,
	SqliteModelRepository,
	SqliteModelVersionRepository,
	SqliteProjectRepository,
	SqliteRuleRepository,
	SqliteRuleVersionRepository,
	SqliteTrainingRunRepository,
)
from usfds_infra.database.case_repositories import SqliteCaseRepository

logger = logging.getLogger(__name__)


@dataclass
class WorkerContext:
	session_factory: sessionmaker[Session]
	storage: IFileStorage


def handle_training_run(ctx: WorkerContext, data: Dict[str, Any]) -> None:
	"""Execute a training run and persist the result (TrainingRun status + candidate ModelVersion)."""
	payload = TrainingRunPayload.model_validate(data)
	logger.info(f"Executing training run {payload.run_id}")
	with ctx.session_factory() as session:
		service = TrainingOrchestrationService(
			dispatcher=None,  # type: ignore[arg-type]  # worker never dispatches
			training_run_repo=SqliteTrainingRunRepository(session),
			model_version_repo=SqliteModelVersionRepository(session),
			model_repo=SqliteModelRepository(session),
			dataset_artifact_repo=SqliteDatasetArtifactRepository(session),
			file_storage=ctx.storage,
		)
		executor = TrainingRunExecutor(
			file_storage=ctx.storage,
			notifier=CallbackResultNotifier(callback=service.handle_training_completion),
		)
		executor.run(payload)
		session.commit()


def handle_batch_inference(ctx: WorkerContext, data: Dict[str, Any]) -> None:
	"""Execute a batch detection job and persist the result (DetectionJob status + summary)."""
	payload = BatchInferencePayload.model_validate(data)
	logger.info(f"Executing batch inference job {payload.job_id}")
	with ctx.session_factory() as session:
		service = InferenceService(
			file_storage=ctx.storage,
			detection_job_repo=SqliteDetectionJobRepository(session),
			project_repo=SqliteProjectRepository(session),
			dataset_repo=SqliteDatasetRepository(session),
			artifact_repo=SqliteDatasetArtifactRepository(session),
			model_repo=SqliteModelRepository(session),
			model_version_repo=SqliteModelVersionRepository(session),
			training_run_repo=SqliteTrainingRunRepository(session),
			rule_manager=RuleManager(
				rule_repo=SqliteRuleRepository(session),
				version_repo=SqliteRuleVersionRepository(session),
				project_repo=SqliteProjectRepository(session),
			),
			case_repo=SqliteCaseRepository(session),
		)
		executor = BatchInferenceExecutor(
			file_storage=ctx.storage,
			notifier=service.handle_job_completion,
		)
		executor.run(payload)
		session.commit()
