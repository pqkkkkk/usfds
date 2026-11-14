"""Repository providers for every domain (pure: depend only on get_db). Append new repo getters here (26-11-14, ISS-026)."""
from fastapi import Depends
from sqlalchemy.orm import Session
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
from usfds_infra.database.case_repositories import SqliteAuditRepository, SqliteBlacklistRepository, SqliteCaseRepository
from usfds_server.dependencies import get_db


def get_dataset_repo(session: Session = Depends(get_db)) -> SqliteDatasetRepository:
    return SqliteDatasetRepository(session)


def get_artifact_repo(session: Session = Depends(get_db)) -> SqliteDatasetArtifactRepository:
    return SqliteDatasetArtifactRepository(session)


def get_detection_job_repo(session: Session = Depends(get_db)) -> SqliteDetectionJobRepository:
	return SqliteDetectionJobRepository(session)


def get_case_repo(session: Session = Depends(get_db)) -> SqliteCaseRepository:
	return SqliteCaseRepository(session)


def get_blacklist_repo(session: Session = Depends(get_db)) -> SqliteBlacklistRepository:
	return SqliteBlacklistRepository(session)


def get_audit_repo(session: Session = Depends(get_db)) -> SqliteAuditRepository:
	return SqliteAuditRepository(session)


def _unused_legacy_case_repo(session: Session = Depends(get_db)) -> SqliteCaseRepository:
    return SqliteCaseRepository(session)


def get_project_repo(session: Session = Depends(get_db)) -> SqliteProjectRepository:
    return SqliteProjectRepository(session)


def get_rule_repo(session: Session = Depends(get_db)) -> SqliteRuleRepository:
    return SqliteRuleRepository(session)


def get_rule_version_repo(session: Session = Depends(get_db)) -> SqliteRuleVersionRepository:
    return SqliteRuleVersionRepository(session)


def get_model_repo(session: Session = Depends(get_db)) -> SqliteModelRepository:
    return SqliteModelRepository(session)


def get_model_version_repo(session: Session = Depends(get_db)) -> SqliteModelVersionRepository:
    return SqliteModelVersionRepository(session)


def get_training_run_repo(session: Session = Depends(get_db)) -> SqliteTrainingRunRepository:
	return SqliteTrainingRunRepository(session)
