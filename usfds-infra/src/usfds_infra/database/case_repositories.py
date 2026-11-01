from dataclasses import asdict, fields
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from usfds_core.domain.entities.case import AuditLog, BlacklistEntityType, Case, CaseStatus, EntityBlacklist
from usfds_core.domain.entities.enums import RiskLevel, RuleAction
from usfds_core.repositories.base_case_repo import CaseConflictError, IAuditRepository, IBlacklistRepository, ICaseRepository
from usfds_infra.database.case_models import AuditLogModel, CaseModel, EntityBlacklistModel


def _values(entity) -> dict:
	return {name: str(value) if isinstance(value, UUID) else value.value if isinstance(value, Enum) else value
		for name, value in asdict(entity).items()}


def _utc(value: datetime | None) -> datetime | None:
	return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def _case(model: CaseModel) -> Case:
	values = {field.name: getattr(model, field.name) for field in fields(Case)}
	for name in ("project_id", "case_id", "dataset_artifact_id", "detection_job_id", "model_version_id"):
		values[name] = UUID(values[name]) if values[name] else None
	for name in ("created_at", "updated_at", "tx_timestamp", "resolved_at"):
		values[name] = _utc(values[name])
	values.update(status=CaseStatus(model.status), priority=RiskLevel(model.priority), final_action=RuleAction(model.final_action))
	return Case(**values)


class SqliteCaseRepository(ICaseRepository):
	def __init__(self, session: Session):
		self.session = session

	def save(self, case: Case, expected_version: int | None = None) -> Case:
		values = _values(case)
		values["triggered_rule_codes"] = case.triggered_rule_codes
		if expected_version is None:
			self.session.add(CaseModel(**values))
			try:
				self.session.flush()
			except IntegrityError as error:
				raise CaseConflictError("Case already exists; retry intake") from error
		else:
			values["version"] = expected_version + 1
			result = self.session.execute(update(CaseModel).where(CaseModel.case_id == str(case.case_id),
				CaseModel.project_id == str(case.project_id), CaseModel.version == expected_version).values(**values))
			if result.rowcount != 1:
				raise CaseConflictError("Case changed; refresh before submitting again")
			self.session.flush()
		return self.get_by_id(case.case_id)

	def get_by_id(self, case_id: UUID) -> Case | None:
		model = self.session.execute(select(CaseModel).where(CaseModel.case_id == str(case_id)).execution_options(populate_existing=True)).scalar_one_or_none()
		return _case(model) if model else None

	def get_by_event(self, project_id: UUID, event_id: str) -> Case | None:
		model = self.session.execute(select(CaseModel).where(CaseModel.project_id == str(project_id), CaseModel.event_id == event_id)).scalar_one_or_none()
		return _case(model) if model else None

	def list_by_project(self, project_id: UUID) -> list[Case]:
		return [_case(model) for model in self.session.scalars(select(CaseModel).where(CaseModel.project_id == str(project_id)).order_by(CaseModel.created_at, CaseModel.case_id))]

	def search(self, project_id: UUID, filters: dict, sort: str, page: int, size: int) -> tuple[list[Case], int]:
		query = select(CaseModel).where(CaseModel.project_id == str(project_id))
		for key in ("status", "priority", "user_id", "assigned_to"):
			if filters.get(key):
				query = query.where(getattr(CaseModel, key) == filters[key])
		if filters.get("unassigned"):
			query = query.where(CaseModel.assigned_to.is_(None))
		if filters.get("rule_code"):
			rules = func.json_each(CaseModel.triggered_rule_codes).table_valued("value")
			query = query.where(select(1).select_from(rules).where(rules.c.value == filters["rule_code"]).exists())
		if filters.get("q"):
			pattern = "%" + filters["q"].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
			query = query.where(or_(*(column.ilike(pattern, escape="\\") for column in (CaseModel.case_code, CaseModel.event_id, CaseModel.user_id))))
		for key, column, direction in (("min_score", CaseModel.model_score, "min"), ("max_score", CaseModel.model_score, "max"),
			("min_amount", CaseModel.amount, "min"), ("max_amount", CaseModel.amount, "max")):
			if filters.get(key) is not None:
				query = query.where(column >= filters[key] if direction == "min" else column <= filters[key])
		total = self.session.scalar(select(func.count()).select_from(query.subquery()))
		order = {"priority": CaseModel.priority_score.desc(), "amount": CaseModel.amount.desc(), "created": CaseModel.created_at.desc()}[sort]
		models = self.session.scalars(query.order_by(order, CaseModel.case_id).offset((page - 1) * size).limit(size))
		return [_case(model) for model in models], total or 0

	def kpis(self, project_id: UUID) -> dict:
		counts = dict(self.session.execute(select(CaseModel.status, func.count()).where(CaseModel.project_id == str(project_id)).group_by(CaseModel.status)).all())
		critical = self.session.scalar(select(func.count()).select_from(CaseModel).where(CaseModel.project_id == str(project_id),
			CaseModel.priority == "CRITICAL", CaseModel.status.in_(["OPEN", "IN_PROGRESS", "PENDING_CUSTOMER"])))
		fraud = counts.get("RESOLVED_FRAUD", 0)
		resolved = fraud + counts.get("RESOLVED_LEGITIMATE", 0)
		return {"open": counts.get("OPEN", 0), "in_progress": counts.get("IN_PROGRESS", 0), "pending_customer": counts.get("PENDING_CUSTOMER", 0),
			"critical": critical or 0, "resolved": resolved, "confirmed_fraud_ratio": fraud / resolved if resolved else None}


class SqliteBlacklistRepository(IBlacklistRepository):
	def __init__(self, session: Session):
		self.session = session

	def save(self, entry: EntityBlacklist) -> EntityBlacklist:
		values = _values(entry)
		if entry.status == "REMOVED":
			result = self.session.execute(update(EntityBlacklistModel).where(EntityBlacklistModel.blacklist_id == str(entry.blacklist_id),
				EntityBlacklistModel.project_id == str(entry.project_id), EntityBlacklistModel.status == "ACTIVE").values(**values))
			if result.rowcount != 1:
				raise CaseConflictError("Blacklist entry changed; refresh")
		else:
			self.session.add(EntityBlacklistModel(**values))
		try:
			self.session.flush()
		except IntegrityError as error:
			raise CaseConflictError("Entity is already blacklisted") from error
		return entry

	def list_by_project(self, project_id: UUID) -> list[EntityBlacklist]:
		entries = []
		for model in self.session.scalars(select(EntityBlacklistModel).where(EntityBlacklistModel.project_id == str(project_id)).order_by(EntityBlacklistModel.created_at.desc())):
			values = {field.name: getattr(model, field.name) for field in fields(EntityBlacklist)}
			for name in ("project_id", "blacklist_id", "source_case_id"):
				values[name] = UUID(values[name]) if values[name] else None
			values["entity_type"] = BlacklistEntityType(model.entity_type)
			values["created_at"], values["removed_at"] = _utc(model.created_at), _utc(model.removed_at)
			entries.append(EntityBlacklist(**values))
		return entries


class SqliteAuditRepository(IAuditRepository):
	def __init__(self, session: Session):
		self.session = session

	def append(self, log: AuditLog) -> None:
		self.session.add(AuditLogModel(**_values(log)))
		self.session.flush()

	def list_for_entity(self, project_id: UUID, entity_type: str, entity_id: str) -> list[AuditLog]:
		logs = []
		for model in self.session.scalars(select(AuditLogModel).where(AuditLogModel.project_id == str(project_id),
			AuditLogModel.entity_type == entity_type, AuditLogModel.entity_id == entity_id).order_by(AuditLogModel.created_at, AuditLogModel.log_id)):
			values = {field.name: getattr(model, field.name) for field in fields(AuditLog)}
			values.update(project_id=UUID(model.project_id) if model.project_id else None, log_id=UUID(model.log_id), created_at=_utc(model.created_at))
			logs.append(AuditLog(**values))
		return logs