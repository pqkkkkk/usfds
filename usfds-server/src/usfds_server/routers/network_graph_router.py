"""Read-only REST API for Fraud Network Graph Link Analysis (ISS-041 / SUC-19)."""
import threading
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from usfds_core.domain.entities.auth import ActorContext
from usfds_core.domain.entities.case import OPEN_STATUSES, BlacklistEntityType, CaseStatus
from usfds_core.services.auth.authz_service import AuthzService
from usfds_core.services.investigation.network_graph import (
	LadybugNetworkGraphService,
	LiveRiskOverlay,
)
from usfds_core.services.warehouse.project_warehouse import ProjectWarehouse
from usfds_core.storage.base_storage import IFileStorage
from usfds_infra.database import (
	SqliteDatasetArtifactRepository,
	SqliteDatasetRepository,
	SqliteDetectionJobRepository,
)
from usfds_infra.database.case_repositories import (
	SqliteBlacklistRepository,
	SqliteCaseRepository,
)
from usfds_server.config import settings
from usfds_server.dependencies import get_actor_context, get_authz_service, get_db, get_storage
from usfds_server.routers.investigation_router import _project
from usfds_server.schemas.base_response import ApiResponse
from usfds_server.schemas.network_graph_schemas import ExpandNodeRequest

router = APIRouter(prefix="/api/v1/network", tags=["Network Graph"])

_GRAPH_SERVICE_LOCK = threading.Lock()
_GRAPH_SERVICE: LadybugNetworkGraphService | None = None
_GRAPH_SERVICE_KEY: tuple[str, str, int, int, int, int] | None = None


def _get_graph_service(storage: IFileStorage) -> LadybugNetworkGraphService:
	global _GRAPH_SERVICE, _GRAPH_SERVICE_KEY
	storage_loc = str(getattr(storage, "base_dir", getattr(storage, "bucket", id(storage))))
	key = (
		type(storage).__name__,
		storage_loc,
		settings.graph_cache_max_entries,
		settings.graph_cache_ttl_seconds,
		settings.graph_buffer_pool_mb,
		settings.graph_super_node_degree,
	)
	with _GRAPH_SERVICE_LOCK:
		if _GRAPH_SERVICE is None or _GRAPH_SERVICE_KEY != key:
			_GRAPH_SERVICE = LadybugNetworkGraphService(
				file_storage=storage,
				cache_max_entries=settings.graph_cache_max_entries,
				cache_ttl_seconds=settings.graph_cache_ttl_seconds,
				buffer_pool_mb=settings.graph_buffer_pool_mb,
				super_node_degree_threshold=settings.graph_super_node_degree,
			)
			_GRAPH_SERVICE_KEY = key
		return _GRAPH_SERVICE


def _load_overlay(session: Session, project_id: UUID) -> LiveRiskOverlay:
	blacklist_entries = SqliteBlacklistRepository(session).list_by_project(project_id)
	blacklisted = {
		(entry.entity_type.value if hasattr(entry.entity_type, "value") else str(entry.entity_type), entry.entity_value)
		for entry in blacklist_entries
		if entry.status == "ACTIVE"
	}
	cases = SqliteCaseRepository(session).list_by_project(project_id)
	open_counts: dict[str, int] = {}
	fraud_counts: dict[str, int] = {}
	user_case_ids: dict[str, list[str]] = {}
	event_case_ids: dict[str, str] = {}
	for case in cases:
		cid = str(case.case_id)
		event_case_ids[case.event_id] = cid
		user_case_ids.setdefault(case.user_id, []).append(cid)
		if case.status in OPEN_STATUSES:
			open_counts[case.user_id] = open_counts.get(case.user_id, 0) + 1
		elif case.status == CaseStatus.RESOLVED_FRAUD:
			fraud_counts[case.user_id] = fraud_counts.get(case.user_id, 0) + 1

	return LiveRiskOverlay(
		blacklisted=blacklisted,
		open_case_counts=open_counts,
		resolved_fraud_counts=fraud_counts,
		user_case_ids=user_case_ids,
		event_case_ids=event_case_ids,
	)


def _resolve_sources(session: Session, storage: IFileStorage, project_id: UUID, case_id: UUID | None) -> tuple[list, str | None]:
	jobs = SqliteDetectionJobRepository(session).list_by_project(project_id)
	completed_jobs = [
		job for job in jobs
		if (job.status.value if hasattr(job.status, "value") else str(job.status)) == "COMPLETED" and job.output_path
	]
	if completed_jobs:
		ProjectWarehouse(storage).sync_missing_jobs(completed_jobs)
		return completed_jobs, None

	if case_id is not None:
		case = SqliteCaseRepository(session).get_by_id(case_id)
		if case is None or case.project_id != project_id:
			raise HTTPException(404, "Case not found in this project")
		if case.dataset_artifact_id is not None:
			artifact = SqliteDatasetArtifactRepository(session).get_by_id(case.dataset_artifact_id)
			if artifact is not None and artifact.pipeline_stage != "RAW":
				dataset = SqliteDatasetRepository(session).get_by_id(artifact.dataset_id)
				if dataset is not None and dataset.project_id == project_id:
					return [], artifact.storage_path
	return [], None


@router.get("/hubs", response_model=ApiResponse[dict])
def list_network_hubs(
	project_id: UUID,
	days: int = Query(90, ge=1, le=3650),
	limit: int = Query(20, ge=1, le=100),
	case_id: UUID | None = None,
	session: Session = Depends(get_db),
	storage: IFileStorage = Depends(get_storage),
	actor: ActorContext = Depends(get_actor_context),
	authz: AuthzService = Depends(get_authz_service),
):
	authz.require_project_permission(actor, "case:read", project_id)
	_project(session, project_id)
	jobs, artifact_path = _resolve_sources(session, storage, project_id, case_id)
	overlay = _load_overlay(session, project_id)
	result = _get_graph_service(storage).list_hubs(
		project_id, jobs, overlay=overlay, days=days, limit=limit, artifact_path=artifact_path,
	)
	return ApiResponse.ok(result)


@router.get("/subgraph", response_model=ApiResponse[dict])
def get_network_subgraph(
	project_id: UUID,
	seed_type: BlacklistEntityType,
	seed_value: str = Query(..., min_length=1, max_length=255),
	hops: int = Query(2, ge=1, le=2),
	days: int = Query(90, ge=1, le=3650),
	entity_types: list[BlacklistEntityType] | None = Query(None),
	hide_super_nodes: bool = False,
	case_id: UUID | None = None,
	session: Session = Depends(get_db),
	storage: IFileStorage = Depends(get_storage),
	actor: ActorContext = Depends(get_actor_context),
	authz: AuthzService = Depends(get_authz_service),
):
	authz.require_project_permission(actor, "case:read", project_id)
	_project(session, project_id)
	jobs, artifact_path = _resolve_sources(session, storage, project_id, case_id)
	overlay = _load_overlay(session, project_id)
	try:
		result = _get_graph_service(storage).get_subgraph(
			project_id,
			jobs,
			seed_type.value,
			seed_value,
			overlay=overlay,
			hops=hops,
			days=days,
			entity_types=[et.value for et in entity_types] if entity_types else None,
			hide_super_nodes=hide_super_nodes,
			artifact_path=artifact_path,
		)
		return ApiResponse.ok(result)
	except ValueError as error:
		raise HTTPException(400, str(error)) from error


@router.post("/expand", response_model=ApiResponse[dict])
def expand_network_node(
	request: ExpandNodeRequest,
	session: Session = Depends(get_db),
	storage: IFileStorage = Depends(get_storage),
	actor: ActorContext = Depends(get_actor_context),
	authz: AuthzService = Depends(get_authz_service),
):
	authz.require_project_permission(actor, "case:read", request.project_id)
	_project(session, request.project_id)
	jobs, artifact_path = _resolve_sources(session, storage, request.project_id, request.case_id)
	overlay = _load_overlay(session, request.project_id)
	try:
		result = _get_graph_service(storage).expand_node(
			request.project_id,
			jobs,
			request.entity_type.value,
			request.entity_value,
			request.existing_node_ids,
			overlay=overlay,
			days=request.days,
			entity_types=[et.value for et in request.entity_types] if request.entity_types else None,
			hide_super_nodes=request.hide_super_nodes,
			artifact_path=artifact_path,
		)
		return ApiResponse.ok(result)
	except ValueError as error:
		raise HTTPException(400, str(error)) from error


@router.get("/edge-transactions", response_model=ApiResponse[dict])
def get_network_edge_transactions(
	project_id: UUID,
	user_id: str = Query(..., min_length=1, max_length=255),
	entity_type: BlacklistEntityType = Query(...),
	entity_value: str = Query(..., min_length=1, max_length=255),
	days: int = Query(90, ge=1, le=3650),
	limit: int = Query(100, ge=1, le=500),
	case_id: UUID | None = None,
	session: Session = Depends(get_db),
	storage: IFileStorage = Depends(get_storage),
	actor: ActorContext = Depends(get_actor_context),
	authz: AuthzService = Depends(get_authz_service),
):
	authz.require_project_permission(actor, "case:read", project_id)
	_project(session, project_id)
	jobs, artifact_path = _resolve_sources(session, storage, project_id, case_id)
	overlay = _load_overlay(session, project_id)
	try:
		result = _get_graph_service(storage).get_edge_transactions(
			project_id,
			jobs,
			user_id,
			entity_type.value,
			entity_value,
			overlay=overlay,
			days=days,
			limit=limit,
			artifact_path=artifact_path,
		)
		return ApiResponse.ok(result)
	except ValueError as error:
		raise HTTPException(400, str(error)) from error
