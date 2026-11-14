"""FastAPI dependency providers for the `insight` domain (moved from dependencies.py, 26-11-14, ISS-026)."""
from fastapi import Depends
from usfds_core.services.insight_report.service import InsightReportService
from usfds_infra.database import (
	SqliteDetectionJobRepository,
	SqliteProjectRepository,
	SqliteRuleRepository,
	SqliteRuleVersionRepository,
)
from usfds_infra.storage.local_storage import LocalFileStorage
from usfds_infra.database.case_repositories import SqliteAuditRepository, SqliteBlacklistRepository, SqliteCaseRepository
from usfds_server.providers.repos import get_detection_job_repo, get_case_repo, get_blacklist_repo, get_audit_repo, get_project_repo, get_rule_repo, get_rule_version_repo
from usfds_server.dependencies import get_storage


def get_insight_report_service(
	project_repo: SqliteProjectRepository = Depends(get_project_repo),
	detection_job_repo: SqliteDetectionJobRepository = Depends(get_detection_job_repo),
	case_repo: SqliteCaseRepository = Depends(get_case_repo),
	blacklist_repo: SqliteBlacklistRepository = Depends(get_blacklist_repo),
	audit_repo: SqliteAuditRepository = Depends(get_audit_repo),
	rule_repo: SqliteRuleRepository = Depends(get_rule_repo),
	rule_version_repo: SqliteRuleVersionRepository = Depends(get_rule_version_repo),
	storage: LocalFileStorage = Depends(get_storage),
) -> InsightReportService:
	return InsightReportService(
		project_repo=project_repo,
		detection_job_repo=detection_job_repo,
		case_repo=case_repo,
		blacklist_repo=blacklist_repo,
		audit_repo=audit_repo,
		rule_repo=rule_repo,
		rule_version_repo=rule_version_repo,
		file_storage=storage,
	)
