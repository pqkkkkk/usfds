"""FastAPI dependency providers for the `data` domain (moved from dependencies.py, 26-11-14, ISS-026)."""
from fastapi import Depends
from sqlalchemy.orm import Session
from usfds_core.services.data_management.service import DataManagementService
from usfds_core.services.data_management.system_metadata_service import SystemMetadataService
from usfds_core.services.project_management.project_service import ProjectManagementService
from usfds_infra.database import (
    SqlSystemColumnMetadataRepository,
    SqliteDatasetArtifactRepository,
    SqliteDatasetRepository,
    SqliteDetectionJobRepository,
    SqliteProjectRepository,
    SqliteTrainingRunRepository,
)
from usfds_infra.storage.local_storage import LocalFileStorage
from usfds_server.providers.repos import (
    get_artifact_repo,
    get_dataset_repo,
    get_detection_job_repo,
    get_project_repo,
    get_system_metadata_repo,
    get_training_run_repo,
)
from usfds_server.dependencies import get_db, get_storage
from usfds_server.providers.project import get_project_management_service


def get_system_metadata_service(
    metadata_repo: SqlSystemColumnMetadataRepository = Depends(get_system_metadata_repo),
) -> SystemMetadataService:
    return SystemMetadataService(metadata_repo=metadata_repo)


def get_data_management_service(
    dataset_repo: SqliteDatasetRepository = Depends(get_dataset_repo),
    artifact_repo: SqliteDatasetArtifactRepository = Depends(get_artifact_repo),
    project_repo: SqliteProjectRepository = Depends(get_project_repo),
    project_service: ProjectManagementService = Depends(get_project_management_service),
    training_run_repo: SqliteTrainingRunRepository = Depends(get_training_run_repo),
    detection_job_repo: SqliteDetectionJobRepository = Depends(get_detection_job_repo),
    metadata_repo: SqlSystemColumnMetadataRepository = Depends(get_system_metadata_repo),
    storage: LocalFileStorage = Depends(get_storage),
) -> DataManagementService:
    return DataManagementService(
        dataset_repo=dataset_repo,
        artifact_repo=artifact_repo,
        file_storage=storage,
        project_repo=project_repo,
        project_service=project_service,
        training_run_repo=training_run_repo,
        detection_job_repo=detection_job_repo,
        metadata_repo=metadata_repo,
    )
