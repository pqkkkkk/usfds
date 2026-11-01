import io
from dataclasses import asdict
from typing import Literal
from uuid import UUID

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from usfds_core.domain.entities.case import Case, CaseStatus, EntityBlacklist
from usfds_core.domain.entities.enums import RiskLevel, RuleAction
from usfds_core.repositories.base_case_repo import CaseConflictError
from usfds_core.services.investigation.behavior_profile import build_behavior_profile, build_rule_draft
from usfds_core.services.investigation.case_service import BlacklistService, CaseService, rule_feedback
from usfds_infra.database import SqliteDatasetArtifactRepository, SqliteDatasetRepository, SqliteProjectRepository
from usfds_infra.database.case_repositories import SqliteAuditRepository, SqliteBlacklistRepository, SqliteCaseRepository
from usfds_infra.storage.local_storage import LocalFileStorage
from usfds_server.dependencies import get_db, get_storage
from usfds_server.schemas.base_response import ApiResponse
from usfds_server.schemas.investigation_api_schemas import (
	AddBlacklistRequest, CaseActionRequest, CaseIntakeRequest, CaseResponse,
	NoteRequest, RemoveBlacklistRequest, ResolveCaseRequest,
)


router = APIRouter(prefix="/api/v1/cases", tags=["Investigation"])
blacklist_router = APIRouter(prefix="/api/v1/blacklist", tags=["Blacklist"])


def get_actor() -> str:
	return "local-analyst"


def _service(session: Session) -> CaseService:
	return CaseService(SqliteCaseRepository(session), SqliteAuditRepository(session), SqliteBlacklistRepository(session))


def _project(session: Session, project_id: UUID, writable: bool = False):
	project = SqliteProjectRepository(session).get_by_id(project_id)
	if project is None:
		raise HTTPException(404, "Project not found")
	if writable and project.status == "ARCHIVED":
		raise HTTPException(400, "Archived projects cannot be changed")
	return project


def _artifact(session: Session, storage: LocalFileStorage, project_id: UUID, artifact_id: UUID) -> pd.DataFrame:
	artifact = SqliteDatasetArtifactRepository(session).get_by_id(artifact_id)
	if artifact is None:
		raise HTTPException(404, "Dataset artifact not found")
	dataset = SqliteDatasetRepository(session).get_by_id(artifact.dataset_id)
	if dataset is None or dataset.project_id != project_id:
		raise HTTPException(400, "Dataset artifact does not belong to this project")
	if artifact.pipeline_stage == "RAW":
		raise HTTPException(400, "Intake needs an artifact with canonical mapped columns")
	try:
		raw = io.BytesIO(storage.read_bytes(artifact.storage_path))
		frame = pd.read_csv(raw) if artifact.storage_path.lower().endswith(".csv") else pd.read_parquet(raw)
	except FileNotFoundError as error:
		raise HTTPException(404, "Dataset artifact file is unavailable") from error
	if not {"event_id", "user_id", "timestamp", "amount"}.issubset(frame.columns):
		raise HTTPException(400, "Artifact lacks canonical event_id/user_id/timestamp/amount columns")
	return frame


def _error(error: Exception):
	if isinstance(error, CaseConflictError):
		raise HTTPException(409, str(error)) from error
	if isinstance(error, LookupError):
		raise HTTPException(404, str(error)) from error
	if isinstance(error, ValueError):
		raise HTTPException(400, str(error)) from error
	raise error


@router.post("/intake", status_code=201, response_model=ApiResponse[dict])
def intake(request: CaseIntakeRequest, session: Session = Depends(get_db), storage: LocalFileStorage = Depends(get_storage), actor: str = Depends(get_actor)):
	_project(session, request.project_id, True)
	frame = _artifact(session, storage, request.project_id, request.dataset_artifact_id)
	frame = frame.assign(event_id=frame["event_id"].astype(str))
	indexed = frame.set_index("event_id")
	counts = frame["event_id"].value_counts()
	cases = []
	for transaction in request.transactions:
		if counts.get(transaction.event_id, 0) != 1:
			raise HTTPException(400, f"Event {transaction.event_id} must exist exactly once in the artifact")
		row = indexed.loc[transaction.event_id]
		try:
			matches = str(row["user_id"]) == transaction.user_id and float(row["amount"]) == transaction.amount and pd.to_datetime(row["timestamp"], utc=True) == pd.Timestamp(transaction.timestamp)
		except (ValueError, TypeError):
			matches = False
		if not matches:
			raise HTTPException(400, f"Snapshot differs from artifact for event {transaction.event_id}")
		cases.append(Case(
			request.project_id, transaction.event_id, transaction.user_id, transaction.timestamp, transaction.amount,
			RuleAction(transaction.final_action), request.dataset_artifact_id, model_score=transaction.model_score,
			detection_job_id=request.detection_job_id, model_version_id=request.model_version_id,
			triggered_rules=[rule.model_dump(mode="json") for rule in transaction.triggered_rules],
			feature_contributions=[feature.model_dump(mode="json") for feature in transaction.feature_contributions], attributes=transaction.attributes,
		))
	try:
		return ApiResponse.ok(_service(session).intake(cases, actor), status_code=201)
	except (ValueError, LookupError) as error:
		_error(error)


@router.get("", response_model=ApiResponse[dict])
def list_cases(project_id: UUID, status: CaseStatus | None = None, priority: RiskLevel | None = None,
		q: str = "", user_id: str | None = None, assigned_to: str | None = None, unassigned: bool = False,
		rule_code: str | None = None, min_score: float | None = Query(None, ge=0, le=1), max_score: float | None = Query(None, ge=0, le=1),
		min_amount: float | None = Query(None, ge=0), max_amount: float | None = Query(None, ge=0),
		sort: Literal["priority", "amount", "created"] = "priority", page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=200), session: Session = Depends(get_db)):
	_project(session, project_id)
	if min_score is not None and max_score is not None and min_score > max_score or min_amount is not None and max_amount is not None and min_amount > max_amount:
		raise HTTPException(400, "Filter range is inverted")
	items, total = SqliteCaseRepository(session).search(project_id, {"status": status, "priority": priority,
		"q": q, "user_id": user_id, "assigned_to": assigned_to, "unassigned": unassigned, "rule_code": rule_code,
		"min_score": min_score, "max_score": max_score, "min_amount": min_amount, "max_amount": max_amount}, sort, page, size)
	return ApiResponse.ok({"items": [CaseResponse.model_validate(item).model_dump(mode="json") for item in items], "total": total, "page": page, "size": size})


@router.get("/kpis", response_model=ApiResponse[dict])
def kpis(project_id: UUID, session: Session = Depends(get_db)):
	_project(session, project_id)
	return ApiResponse.ok(SqliteCaseRepository(session).kpis(project_id))


@router.get("/rule-feedback", response_model=ApiResponse[list[dict]])
def feedback(project_id: UUID, session: Session = Depends(get_db)):
	_project(session, project_id)
	return ApiResponse.ok(rule_feedback(SqliteCaseRepository(session).list_by_project(project_id)))


@router.get("/{case_id}", response_model=ApiResponse[CaseResponse])
def get_case(case_id: UUID, project_id: UUID, session: Session = Depends(get_db)):
	try:
		return ApiResponse.ok(CaseResponse.model_validate(_service(session).get(project_id, case_id)))
	except LookupError as error:
		_error(error)


@router.get("/{case_id}/workbench", response_model=ApiResponse[dict])
def workbench(case_id: UUID, project_id: UUID, days: Literal[30, 90] = 30, session: Session = Depends(get_db), storage: LocalFileStorage = Depends(get_storage)):
	try:
		case = _service(session).get(project_id, case_id)
		try:
			profile = build_behavior_profile(_artifact(session, storage, project_id, case.dataset_artifact_id), case, days)
		except HTTPException as error:
			profile = {"available": False, "message": error.detail, "timeline": [], "comparison": []}
		related, related_total = SqliteCaseRepository(session).search(project_id, {"user_id": case.user_id}, "created", 1, 200)
		blocked = any(entry.status == "ACTIVE" and entry.entity_type == "USER_ID" and entry.entity_value == case.user_id for entry in SqliteBlacklistRepository(session).list_by_project(project_id))
		return ApiResponse.ok({"case": CaseResponse.model_validate(case).model_dump(mode="json"), "profile": profile,
			"subject_status": "BLOCKED" if blocked else "ACTIVE", "related_cases": [CaseResponse.model_validate(item).model_dump(mode="json") for item in related if item.case_id != case_id],
			"related_total": max(0, related_total - 1), "audit_logs": jsonable_encoder([asdict(log) for log in SqliteAuditRepository(session).list_for_entity(project_id, "CASE", str(case_id))])})
	except (ValueError, LookupError) as error:
		_error(error)


@router.get("/{case_id}/rule-draft", response_model=ApiResponse[dict])
def draft(case_id: UUID, project_id: UUID, session: Session = Depends(get_db)):
	try:
		project = _project(session, project_id)
		return ApiResponse.ok(build_rule_draft(_service(session).get(project_id, case_id), project.raw_schema))
	except (ValueError, LookupError) as error:
		_error(error)


@router.post("/{case_id}/notes", response_model=ApiResponse[bool])
def add_note(case_id: UUID, project_id: UUID, request: NoteRequest, session: Session = Depends(get_db), actor: str = Depends(get_actor)):
	_project(session, project_id, True)
	try:
		_service(session).add_note(project_id, case_id, actor, request.note)
		return ApiResponse.ok(True)
	except (ValueError, LookupError) as error:
		_error(error)


def _mutate(case_id: UUID, project_id: UUID, request: CaseActionRequest, action: str, session: Session, actor: str,
		reason: str = "", block_entities=None):
	_project(session, project_id, True)
	try:
		case, warnings = _service(session).update(project_id, case_id, request.expected_version, action, actor,
			reason=reason, summary=request.summary, assignee=request.assignee, block_entities=block_entities)
		return ApiResponse.ok({"case": CaseResponse.model_validate(case).model_dump(mode="json"), "related_assignees": warnings})
	except (ValueError, LookupError) as error:
		_error(error)


@router.post("/{case_id}/claim", response_model=ApiResponse[dict])
def claim(case_id: UUID, project_id: UUID, request: CaseActionRequest, session: Session = Depends(get_db), actor: str = Depends(get_actor)):
	return _mutate(case_id, project_id, request, "claim", session, actor)


@router.post("/{case_id}/pending-customer", response_model=ApiResponse[dict])
def pending(case_id: UUID, project_id: UUID, request: CaseActionRequest, session: Session = Depends(get_db), actor: str = Depends(get_actor)):
	return _mutate(case_id, project_id, request, "pending-customer", session, actor)


@router.post("/{case_id}/escalate", response_model=ApiResponse[dict])
def escalate(case_id: UUID, project_id: UUID, request: CaseActionRequest, session: Session = Depends(get_db), actor: str = Depends(get_actor)):
	return _mutate(case_id, project_id, request, "escalate", session, actor)


@router.post("/{case_id}/reopen", response_model=ApiResponse[dict])
def reopen(case_id: UUID, project_id: UUID, request: CaseActionRequest, session: Session = Depends(get_db), actor: str = Depends(get_actor)):
	return _mutate(case_id, project_id, request, "reopen", session, actor)


@router.post("/{case_id}/resolve", response_model=ApiResponse[dict])
def resolve(case_id: UUID, project_id: UUID, request: ResolveCaseRequest, session: Session = Depends(get_db), actor: str = Depends(get_actor)):
	return _mutate(case_id, project_id, request, "resolve-fraud" if request.verdict == "FRAUD" else "resolve-legitimate", session, actor,
		reason=request.reason, block_entities=[(entity.entity_type, entity.entity_value) for entity in request.block_entities])


@blacklist_router.get("", response_model=ApiResponse[list[dict]])
def list_blacklist(project_id: UUID, session: Session = Depends(get_db)):
	_project(session, project_id)
	return ApiResponse.ok(jsonable_encoder([asdict(entry) for entry in SqliteBlacklistRepository(session).list_by_project(project_id)]))


@blacklist_router.post("", status_code=201, response_model=ApiResponse[dict])
def add_blacklist(request: AddBlacklistRequest, session: Session = Depends(get_db), actor: str = Depends(get_actor)):
	_project(session, request.project_id, True)
	try:
		if request.source_case_id:
			_service(session).get(request.project_id, request.source_case_id)
		entry = BlacklistService(SqliteBlacklistRepository(session), SqliteAuditRepository(session)).add(EntityBlacklist(
			request.project_id, request.entity_type, request.entity_value, request.reason, actor, source_case_id=request.source_case_id))
		return ApiResponse.ok(jsonable_encoder(asdict(entry)), status_code=201)
	except (ValueError, LookupError) as error:
		_error(error)


@blacklist_router.post("/{blacklist_id}/remove", response_model=ApiResponse[dict])
def remove_blacklist(blacklist_id: UUID, project_id: UUID, request: RemoveBlacklistRequest, session: Session = Depends(get_db), actor: str = Depends(get_actor)):
	_project(session, project_id, True)
	try:
		entry = BlacklistService(SqliteBlacklistRepository(session), SqliteAuditRepository(session)).remove(project_id, blacklist_id, actor, request.reason)
		return ApiResponse.ok(jsonable_encoder(asdict(entry)))
	except (ValueError, LookupError) as error:
		_error(error)