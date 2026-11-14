"""FastAPI dependency providers for the `project` domain (moved from dependencies.py, 26-11-14, ISS-026)."""
from fastapi import Depends
from sqlalchemy.orm import Session
from usfds_core.services.project_management.project_service import ProjectManagementService
from usfds_infra.database import (
	SqliteDatasetArtifactRepository,
	SqliteDatasetRepository,
	SqliteProjectRepository,
	SqliteRuleRepository,
)
from usfds_infra.storage.local_storage import LocalFileStorage
from usfds_server.providers.repos import get_dataset_repo, get_artifact_repo, get_project_repo, get_rule_repo
from usfds_server.dependencies import get_db, get_storage


def get_project_management_service(
    project_repo: SqliteProjectRepository = Depends(get_project_repo),
    dataset_repo: SqliteDatasetRepository = Depends(get_dataset_repo),
    artifact_repo: SqliteDatasetArtifactRepository = Depends(get_artifact_repo),
    rule_repo: SqliteRuleRepository = Depends(get_rule_repo),
    storage: LocalFileStorage = Depends(get_storage),
) -> ProjectManagementService:
    return ProjectManagementService(
        project_repo=project_repo,
        dataset_repo=dataset_repo,
        artifact_repo=artifact_repo,
        rule_repo=rule_repo,
        file_storage=storage,
    )
