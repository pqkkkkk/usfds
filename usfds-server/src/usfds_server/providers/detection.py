"""FastAPI dependency providers for the `detection` domain (moved from dependencies.py, 26-11-14, ISS-026)."""
from fastapi import Depends
from sqlalchemy.orm import Session
from usfds_core.services.inference.inference_service import InferenceService
from usfds_core.services.rule_engine.manager import RuleManager
from usfds_infra.database import (
	SqliteDatasetArtifactRepository,
	SqliteDatasetRepository,
	SqliteDetectionJobRepository,
	SqliteModelRepository,
	SqliteModelVersionRepository,
	SqliteProjectRepository,
	SqliteTrainingRunRepository,
)
from usfds_infra.job_queue import QueueBatchInferenceDispatcher
from usfds_infra.storage.local_storage import LocalFileStorage
from usfds_infra.database.case_repositories import SqliteCaseRepository
from usfds_server.providers.repos import get_dataset_repo, get_artifact_repo, get_detection_job_repo, get_case_repo, get_project_repo, get_model_repo, get_model_version_repo, get_training_run_repo
from usfds_server.dependencies import get_db, get_storage, get_job_queue
from usfds_server.config import settings
from usfds_server.providers.rule import get_rule_manager


def get_inference_service(
	project_repo: SqliteProjectRepository = Depends(get_project_repo),
	dataset_repo: SqliteDatasetRepository = Depends(get_dataset_repo),
	artifact_repo: SqliteDatasetArtifactRepository = Depends(get_artifact_repo),
	model_repo: SqliteModelRepository = Depends(get_model_repo),
	model_version_repo: SqliteModelVersionRepository = Depends(get_model_version_repo),
	training_run_repo: SqliteTrainingRunRepository = Depends(get_training_run_repo),
	detection_job_repo: SqliteDetectionJobRepository = Depends(get_detection_job_repo),
    case_repo: SqliteCaseRepository = Depends(get_case_repo),
	rule_manager: RuleManager = Depends(get_rule_manager),
	storage: LocalFileStorage = Depends(get_storage),
) -> InferenceService:
	return InferenceService(
		file_storage=storage,
		dispatcher=QueueBatchInferenceDispatcher(get_job_queue()) if settings.dispatch_backend == "queue" else None,
		detection_job_repo=detection_job_repo,
		project_repo=project_repo,
		dataset_repo=dataset_repo,
		artifact_repo=artifact_repo,
		model_repo=model_repo,
		model_version_repo=model_version_repo,
		training_run_repo=training_run_repo,
		rule_manager=rule_manager,
        case_repo=case_repo,
	)
