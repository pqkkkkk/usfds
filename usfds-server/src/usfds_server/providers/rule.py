"""FastAPI dependency providers for the `rule` domain (moved from dependencies.py, 26-11-14, ISS-026)."""
from fastapi import Depends
from sqlalchemy.orm import Session
from usfds_core.services.rule_engine.executor import RuleExecutor
from usfds_core.services.rule_engine.manager import RuleManager
from usfds_infra.database import SqliteProjectRepository, SqliteRuleRepository, SqliteRuleVersionRepository
from usfds_server.providers.repos import get_project_repo, get_rule_repo, get_rule_version_repo
from usfds_server.dependencies import get_db


def get_rule_manager(
    rule_repo: SqliteRuleRepository = Depends(get_rule_repo),
    version_repo: SqliteRuleVersionRepository = Depends(get_rule_version_repo),
    project_repo: SqliteProjectRepository = Depends(get_project_repo),
) -> RuleManager:
    return RuleManager(
        rule_repo=rule_repo,
        version_repo=version_repo,
        project_repo=project_repo,
    )


def get_rule_executor() -> RuleExecutor:
    return RuleExecutor()
