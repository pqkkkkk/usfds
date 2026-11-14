"""SQLAlchemy repositories for the `rule` domain (moved from database/repositories.py, 26-11-14)."""
from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from usfds_core.domain.entities.enums import RuleAction, RuleStatus
from usfds_core.domain.entities.rule import Rule, RuleVersion
from usfds_core.repositories.base_rule_repo import IRuleRepository, IRuleVersionRepository
from usfds_infra.database.models import RuleModel, RuleVersionModel
from usfds_infra.database.repos.model import SqliteTrainingRunRepository  # shared _sanitize_json helper


class SqliteRuleRepository(IRuleRepository):
    """SQLite implementation of IRuleRepository using SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _sanitize_json(obj: Any) -> Any:
        import math
        if isinstance(obj, float):
            if math.isnan(obj):
                return None
            if math.isinf(obj):
                return 1.0 if obj > 0 else 0.0
            return obj
        if isinstance(obj, dict):
            return {k: SqliteTrainingRunRepository._sanitize_json(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [SqliteTrainingRunRepository._sanitize_json(v) for v in obj]
        return obj

    def _to_entity(self, model: RuleModel) -> Rule:
        status_val = RuleStatus.ACTIVE
        if model.status:
            try:
                status_val = RuleStatus(model.status)
            except ValueError:
                status_val = model.status

        return Rule(
            rule_id=UUID(model.rule_id),
            project_id=UUID(model.project_id),
            rule_code=model.rule_code,
            name=model.name,
            description=model.description or "",
            status=status_val,
            current_version_id=UUID(model.current_version_id) if model.current_version_id else None,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def save(self, rule: Rule) -> Rule:
        model = self.session.get(RuleModel, str(rule.rule_id))
        status_str = rule.status.value if hasattr(rule.status, "value") else str(rule.status)

        if model is None:
            model = RuleModel(
                rule_id=str(rule.rule_id),
                project_id=str(rule.project_id),
                rule_code=rule.rule_code,
                name=rule.name,
                description=rule.description,
                status=status_str,
                current_version_id=str(rule.current_version_id) if rule.current_version_id else None,
                created_by=rule.created_by,
                created_at=rule.created_at or datetime.now(timezone.utc),
                updated_at=rule.updated_at or datetime.now(timezone.utc),
            )
            self.session.add(model)
        else:
            model.rule_code = rule.rule_code
            model.name = rule.name
            model.description = rule.description
            model.status = status_str
            model.current_version_id = str(rule.current_version_id) if rule.current_version_id else None
            model.updated_at = datetime.now(timezone.utc)

        self.session.flush()
        return self._to_entity(model)

    def get_by_id(self, rule_id: UUID) -> Optional[Rule]:
        model = self.session.get(RuleModel, str(rule_id))
        return self._to_entity(model) if model else None

    def get_by_code(self, project_id: UUID, rule_code: str) -> Optional[Rule]:
        stmt = select(RuleModel).where(
            RuleModel.project_id == str(project_id),
            RuleModel.rule_code == rule_code,
        )
        model = self.session.execute(stmt).scalar_one_or_none()
        return self._to_entity(model) if model else None

    def list_by_project(self, project_id: UUID) -> List[Rule]:
        stmt = select(RuleModel).where(
            RuleModel.project_id == str(project_id)
        ).order_by(RuleModel.created_at.asc())
        models = self.session.execute(stmt).scalars().all()
        return [self._to_entity(m) for m in models]

    def delete(self, rule_id: UUID) -> bool:
        model = self.session.get(RuleModel, str(rule_id))
        if model:
            self.session.delete(model)
            self.session.flush()
            return True
        return False


class SqliteRuleVersionRepository(IRuleVersionRepository):
    """SQLite implementation of IRuleVersionRepository using SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _sanitize_json(obj: Any) -> Any:
        import math
        if isinstance(obj, float):
            if math.isnan(obj):
                return None
            if math.isinf(obj):
                return 1.0 if obj > 0 else 0.0
            return obj
        if isinstance(obj, dict):
            return {k: SqliteTrainingRunRepository._sanitize_json(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [SqliteTrainingRunRepository._sanitize_json(v) for v in obj]
        return obj

    def _to_entity(self, model: RuleVersionModel) -> RuleVersion:
        action_val = RuleAction.REVIEW
        if model.action:
            try:
                action_val = RuleAction(model.action)
            except ValueError:
                action_val = model.action

        return RuleVersion(
            rule_version_id=UUID(model.rule_version_id),
            rule_id=UUID(model.rule_id),
            version_number=model.version_number,
            condition=model.condition or {},
            action=action_val,
            change_summary=model.change_summary,
            created_by=model.created_by,
            created_at=model.created_at,
        )

    def save(self, version: RuleVersion) -> RuleVersion:
        model = self.session.get(RuleVersionModel, str(version.rule_version_id))
        action_str = version.action.value if hasattr(version.action, "value") else str(version.action)

        if model is None:
            model = RuleVersionModel(
                rule_version_id=str(version.rule_version_id),
                rule_id=str(version.rule_id),
                version_number=version.version_number,
                condition=version.condition or {},
                action=action_str,
                change_summary=version.change_summary,
                created_by=version.created_by,
                created_at=version.created_at or datetime.now(timezone.utc),
            )
            self.session.add(model)
        else:
            model.condition = version.condition or {}
            model.action = action_str
            model.change_summary = version.change_summary

        self.session.flush()
        return self._to_entity(model)

    def get_by_id(self, rule_version_id: UUID) -> Optional[RuleVersion]:
        model = self.session.get(RuleVersionModel, str(rule_version_id))
        return self._to_entity(model) if model else None

    def get_latest_version(self, rule_id: UUID) -> Optional[RuleVersion]:
        stmt = select(RuleVersionModel).where(
            RuleVersionModel.rule_id == str(rule_id)
        ).order_by(RuleVersionModel.version_number.desc()).limit(1)
        model = self.session.execute(stmt).scalar_one_or_none()
        return self._to_entity(model) if model else None

    def list_by_rule(self, rule_id: UUID) -> List[RuleVersion]:
        stmt = select(RuleVersionModel).where(
            RuleVersionModel.rule_id == str(rule_id)
        ).order_by(RuleVersionModel.version_number.asc())
        models = self.session.execute(stmt).scalars().all()
        return [self._to_entity(m) for m in models]
