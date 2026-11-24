"""REST API routers for Feature Management (/api/v1/features) & Feature Sets (/api/v1/feature-sets)."""
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from usfds_core.domain.entities.auth import ActorContext
from usfds_core.domain.entities.feature import Feature, FeatureSet
from usfds_core.repositories.base_user_repo import IUserRepository
from usfds_core.services.auth.authz_service import AuthzService
from usfds_core.services.features.compiler import FeatureCompiler
from usfds_core.services.features.feature_service import FeatureManagementService
from usfds_server.dependencies import (
	get_actor_context,
	get_authz_service,
	get_feature_management_service,
)
from usfds_server.providers.auth import get_user_repo
from usfds_server.schemas.base_response import ApiResponse, ResourceOwnerDto
from usfds_server.schemas.feature_api_schemas import (
	CloneFeatureRequest,
	CreateFeatureRequest,
	CreateFeatureSetRequest,
	FeatureCompatibilityItemResponse,
	FeatureCompatibilityReportResponse,
	FeaturePreviewResponse,
	FeatureResponse,
	FeatureSetResponse,
	PreviewFeatureRequest,
	UpdateFeatureRequest,
	UpdateFeatureSetRequest,
)
from usfds_server.schemas.pagination import resolve_owners


router = APIRouter(prefix="/api/v1/features", tags=["Feature Management"])
feature_set_router = APIRouter(prefix="/api/v1/feature-sets", tags=["Feature Sets"])


def _to_feature_response(f: Feature, owner: Optional[ResourceOwnerDto] = None) -> FeatureResponse:
	sql_preview: Optional[str] = None
	try:
		sql_preview = FeatureCompiler.preview_sql_for_feature(f)
	except Exception:
		sql_preview = None

	return FeatureResponse(
		feature_id=f.feature_id,
		project_id=f.project_id,
		user_id=f.user_id,
		owner=owner,
		is_builtin=f.is_builtin,
		feature_key=f.feature_key,
		display_name=f.display_name,
		description=f.description,
		megafamily=f.megafamily.value if hasattr(f.megafamily, "value") else str(f.megafamily),
		compute_kind=f.compute_kind.value if hasattr(f.compute_kind, "value") else str(f.compute_kind),
		output_type=f.output_type.value if hasattr(f.output_type, "value") else str(f.output_type),
		is_stateful=bool(f.is_stateful),
		requires_label=bool(f.requires_label),
		config_json=dict(f.config_json or {}),
		source_code=f.source_code,
		compiled_sql_preview=sql_preview,
		required_inputs=list(f.required_inputs or []),
		depends_on_feature_ids=list(f.depends_on_feature_ids or []),
		status=f.status.value if hasattr(f.status, "value") else str(f.status),
		created_by=f.created_by,
		created_at=f.created_at,
		updated_at=f.updated_at,
	)


def _to_feature_set_response(fs: FeatureSet, owner: Optional[ResourceOwnerDto] = None) -> FeatureSetResponse:
	return FeatureSetResponse(
		feature_set_id=fs.feature_set_id,
		project_id=fs.project_id,
		user_id=fs.user_id,
		owner=owner,
		is_builtin=fs.is_builtin,
		set_key=fs.set_key,
		name=fs.name,
		description=fs.description,
		domain_tag=fs.domain_tag,
		default_config=dict(fs.default_config or {}),
		feature_ids=list(fs.feature_ids or []),
		created_by=fs.created_by,
		created_at=fs.created_at,
		updated_at=fs.updated_at,
	)


@router.get("", response_model=ApiResponse[List[FeatureResponse]])
def list_features(
	project_id: UUID = Query(..., description="Project ID"),
	megafamily: Optional[str] = Query(default=None),
	include_builtin: bool = Query(default=True),
	status_filter: Optional[str] = Query(default=None, alias="status"),
	actor: ActorContext = Depends(get_actor_context),
	authz: AuthzService = Depends(get_authz_service),
	service: FeatureManagementService = Depends(get_feature_management_service),
	user_repo: IUserRepository = Depends(get_user_repo),
) -> ApiResponse[List[FeatureResponse]]:
	authz.require_project_scope(actor, "feature:read", project_id)
	items = service.list_features(
		project_id=project_id,
		include_builtin=include_builtin,
		megafamily=megafamily,
		status=status_filter,
	)
	owners = resolve_owners(user_repo, (f.user_id for f in items if f.user_id is not None))
	data = [_to_feature_response(f, owner=owners.get(f.user_id) if f.user_id else None) for f in items]
	return ApiResponse.ok(data=data, message=f"Đã tải {len(data)} đặc trưng")


@router.get("/compatibility", response_model=ApiResponse[FeatureCompatibilityReportResponse])
def get_feature_compatibility(
	project_id: UUID = Query(..., description="Project ID"),
	dataset_id: Optional[UUID] = Query(default=None),
	artifact_id: Optional[UUID] = Query(default=None),
	actor: ActorContext = Depends(get_actor_context),
	authz: AuthzService = Depends(get_authz_service),
	service: FeatureManagementService = Depends(get_feature_management_service),
) -> ApiResponse[FeatureCompatibilityReportResponse]:
	authz.require_project_scope(actor, "feature:read", project_id)
	report = service.check_compatibility(
		project_id=project_id,
		dataset_id=dataset_id,
		artifact_id=artifact_id,
	)
	dto = FeatureCompatibilityReportResponse(
		available_columns=report.available_columns,
		items=[FeatureCompatibilityItemResponse(**it.model_dump()) for it in report.items],
		available_count=report.available_count,
		unavailable_count=report.unavailable_count,
	)
	return ApiResponse.ok(data=dto)


@router.post("", response_model=ApiResponse[FeatureResponse], status_code=status.HTTP_201_CREATED)
def create_feature(
	req: CreateFeatureRequest,
	actor: ActorContext = Depends(get_actor_context),
	authz: AuthzService = Depends(get_authz_service),
	service: FeatureManagementService = Depends(get_feature_management_service),
	user_repo: IUserRepository = Depends(get_user_repo),
) -> ApiResponse[FeatureResponse]:
	authz.require_project_permission(actor, "feature:create", req.project_id, action="create")
	try:
		created = service.create_feature(
			project_id=req.project_id,
			user_id=actor.user_id,
			feature_key=req.feature_key,
			display_name=req.display_name,
			megafamily=req.megafamily,
			compute_kind=req.compute_kind,
			output_type=req.output_type,
			description=req.description,
			is_stateful=req.is_stateful,
			requires_label=req.requires_label,
			config_json=req.config_json,
			source_code=req.source_code,
			required_inputs=req.required_inputs,
			depends_on_feature_ids=req.depends_on_feature_ids,
			status=req.status,
			created_by=actor.username,
		)
	except LookupError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

	owner = resolve_owners(user_repo, [created.user_id] if created.user_id else []).get(created.user_id)
	return ApiResponse.ok(data=_to_feature_response(created, owner=owner), message="Tạo đặc trưng thành công")


@router.post("/preview", response_model=ApiResponse[FeaturePreviewResponse])
def preview_feature(
	req: PreviewFeatureRequest,
	actor: ActorContext = Depends(get_actor_context),
	authz: AuthzService = Depends(get_authz_service),
	service: FeatureManagementService = Depends(get_feature_management_service),
) -> ApiResponse[FeaturePreviewResponse]:
	authz.require_project_scope(actor, "feature:read", req.project_id)
	try:
		res = service.preview_feature(
			project_id=req.project_id,
			artifact_id=req.artifact_id,
			feature_id=req.feature_id,
			feature_spec=req.feature_spec,
		)
	except LookupError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
	except (ValueError, TimeoutError, RuntimeError) as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

	return ApiResponse.ok(data=FeaturePreviewResponse(**res.model_dump()), message="Chạy thử đặc trưng hoàn tất")


@router.get("/{feature_id}", response_model=ApiResponse[FeatureResponse])
def get_feature(
	feature_id: UUID,
	project_id: UUID = Query(..., description="Project ID"),
	actor: ActorContext = Depends(get_actor_context),
	authz: AuthzService = Depends(get_authz_service),
	service: FeatureManagementService = Depends(get_feature_management_service),
	user_repo: IUserRepository = Depends(get_user_repo),
) -> ApiResponse[FeatureResponse]:
	authz.require_project_scope(actor, "feature:read", project_id)
	try:
		feat = service.get_feature(feature_id, project_id=project_id)
	except LookupError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
	owner = resolve_owners(user_repo, [feat.user_id] if feat.user_id else []).get(feat.user_id)
	return ApiResponse.ok(data=_to_feature_response(feat, owner=owner))


@router.patch("/{feature_id}", response_model=ApiResponse[FeatureResponse])
def update_feature(
	feature_id: UUID,
	req: UpdateFeatureRequest,
	project_id: UUID = Query(..., description="Project ID"),
	actor: ActorContext = Depends(get_actor_context),
	authz: AuthzService = Depends(get_authz_service),
	service: FeatureManagementService = Depends(get_feature_management_service),
	user_repo: IUserRepository = Depends(get_user_repo),
) -> ApiResponse[FeatureResponse]:
	try:
		existing = service.get_feature(feature_id, project_id=project_id)
	except LookupError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

	if existing.is_builtin:
		authz.require_project_scope(actor, "feature:update", project_id)
	else:
		authz.require_project_permission(
			actor, "feature:update", project_id, owner_id=existing.user_id, action="mutate"
		)

	try:
		updated = service.update_feature(
			feature_id=feature_id,
			project_id=project_id,
			display_name=req.display_name,
			description=req.description,
			megafamily=req.megafamily,
			output_type=req.output_type,
			is_stateful=req.is_stateful,
			requires_label=req.requires_label,
			config_json=req.config_json,
			source_code=req.source_code,
			required_inputs=req.required_inputs,
			depends_on_feature_ids=req.depends_on_feature_ids,
			status=req.status,
		)
	except LookupError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

	owner = resolve_owners(user_repo, [updated.user_id] if updated.user_id else []).get(updated.user_id)
	return ApiResponse.ok(data=_to_feature_response(updated, owner=owner), message="Cập nhật đặc trưng thành công")


@router.delete("/{feature_id}", response_model=ApiResponse[bool])
def delete_feature(
	feature_id: UUID,
	project_id: UUID = Query(..., description="Project ID"),
	actor: ActorContext = Depends(get_actor_context),
	authz: AuthzService = Depends(get_authz_service),
	service: FeatureManagementService = Depends(get_feature_management_service),
) -> ApiResponse[bool]:
	try:
		existing = service.get_feature(feature_id, project_id=project_id)
	except LookupError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

	if existing.is_builtin:
		authz.require_project_scope(actor, "feature:delete", project_id)
	else:
		authz.require_project_permission(
			actor, "feature:delete", project_id, owner_id=existing.user_id, action="mutate"
		)

	try:
		deleted = service.delete_feature(feature_id, project_id=project_id)
	except LookupError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

	return ApiResponse.ok(data=deleted, message="Đã xóa đặc trưng")


@router.post("/{feature_id}/clone", response_model=ApiResponse[FeatureResponse], status_code=status.HTTP_201_CREATED)
def clone_feature(
	feature_id: UUID,
	req: CloneFeatureRequest,
	project_id: UUID = Query(..., description="Target Project ID"),
	actor: ActorContext = Depends(get_actor_context),
	authz: AuthzService = Depends(get_authz_service),
	service: FeatureManagementService = Depends(get_feature_management_service),
	user_repo: IUserRepository = Depends(get_user_repo),
) -> ApiResponse[FeatureResponse]:
	authz.require_project_permission(actor, "feature:create", project_id, action="create")
	try:
		cloned = service.clone_feature(
			feature_id=feature_id,
			target_project_id=project_id,
			user_id=actor.user_id,
			new_feature_key=req.new_feature_key,
			new_display_name=req.new_display_name,
			created_by=actor.username,
		)
	except LookupError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

	owner = resolve_owners(user_repo, [cloned.user_id] if cloned.user_id else []).get(cloned.user_id)
	return ApiResponse.ok(data=_to_feature_response(cloned, owner=owner), message="Clone đặc trưng thành công")


# =====================================================================
# Feature Sets (/api/v1/feature-sets)
# =====================================================================

@feature_set_router.get("", response_model=ApiResponse[List[FeatureSetResponse]])
def list_feature_sets(
	project_id: UUID = Query(..., description="Project ID"),
	include_builtin: bool = Query(default=True),
	actor: ActorContext = Depends(get_actor_context),
	authz: AuthzService = Depends(get_authz_service),
	service: FeatureManagementService = Depends(get_feature_management_service),
	user_repo: IUserRepository = Depends(get_user_repo),
) -> ApiResponse[List[FeatureSetResponse]]:
	authz.require_project_scope(actor, "feature:read", project_id)
	sets = service.list_feature_sets(project_id=project_id, include_builtin=include_builtin)
	owners = resolve_owners(user_repo, (s.user_id for s in sets if s.user_id is not None))
	data = [_to_feature_set_response(s, owner=owners.get(s.user_id) if s.user_id else None) for s in sets]
	return ApiResponse.ok(data=data)


@feature_set_router.post("", response_model=ApiResponse[FeatureSetResponse], status_code=status.HTTP_201_CREATED)
def create_feature_set(
	req: CreateFeatureSetRequest,
	actor: ActorContext = Depends(get_actor_context),
	authz: AuthzService = Depends(get_authz_service),
	service: FeatureManagementService = Depends(get_feature_management_service),
	user_repo: IUserRepository = Depends(get_user_repo),
) -> ApiResponse[FeatureSetResponse]:
	authz.require_project_permission(actor, "feature:create", req.project_id, action="create")
	try:
		created = service.create_feature_set(
			project_id=req.project_id,
			user_id=actor.user_id,
			set_key=req.set_key,
			name=req.name,
			feature_ids=req.feature_ids,
			description=req.description,
			domain_tag=req.domain_tag,
			default_config=req.default_config,
			created_by=actor.username,
		)
	except LookupError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

	owner = resolve_owners(user_repo, [created.user_id] if created.user_id else []).get(created.user_id)
	return ApiResponse.ok(data=_to_feature_set_response(created, owner=owner), message="Tạo gói đặc trưng thành công")


@feature_set_router.get("/{feature_set_id}", response_model=ApiResponse[FeatureSetResponse])
def get_feature_set(
	feature_set_id: UUID,
	project_id: UUID = Query(..., description="Project ID"),
	actor: ActorContext = Depends(get_actor_context),
	authz: AuthzService = Depends(get_authz_service),
	service: FeatureManagementService = Depends(get_feature_management_service),
	user_repo: IUserRepository = Depends(get_user_repo),
) -> ApiResponse[FeatureSetResponse]:
	authz.require_project_scope(actor, "feature:read", project_id)
	try:
		fs = service.get_feature_set(feature_set_id, project_id=project_id)
	except LookupError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
	owner = resolve_owners(user_repo, [fs.user_id] if fs.user_id else []).get(fs.user_id)
	return ApiResponse.ok(data=_to_feature_set_response(fs, owner=owner))


@feature_set_router.patch("/{feature_set_id}", response_model=ApiResponse[FeatureSetResponse])
def update_feature_set(
	feature_set_id: UUID,
	req: UpdateFeatureSetRequest,
	project_id: UUID = Query(..., description="Project ID"),
	actor: ActorContext = Depends(get_actor_context),
	authz: AuthzService = Depends(get_authz_service),
	service: FeatureManagementService = Depends(get_feature_management_service),
	user_repo: IUserRepository = Depends(get_user_repo),
) -> ApiResponse[FeatureSetResponse]:
	try:
		existing = service.get_feature_set(feature_set_id, project_id=project_id)
	except LookupError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

	if existing.is_builtin:
		authz.require_project_scope(actor, "feature:update", project_id)
	else:
		authz.require_project_permission(
			actor, "feature:update", project_id, owner_id=existing.user_id, action="mutate"
		)

	try:
		updated = service.update_feature_set(
			feature_set_id=feature_set_id,
			project_id=project_id,
			name=req.name,
			description=req.description,
			domain_tag=req.domain_tag,
			default_config=req.default_config,
			feature_ids=req.feature_ids,
		)
	except LookupError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

	owner = resolve_owners(user_repo, [updated.user_id] if updated.user_id else []).get(updated.user_id)
	return ApiResponse.ok(data=_to_feature_set_response(updated, owner=owner), message="Cập nhật gói đặc trưng thành công")


@feature_set_router.delete("/{feature_set_id}", response_model=ApiResponse[bool])
def delete_feature_set(
	feature_set_id: UUID,
	project_id: UUID = Query(..., description="Project ID"),
	actor: ActorContext = Depends(get_actor_context),
	authz: AuthzService = Depends(get_authz_service),
	service: FeatureManagementService = Depends(get_feature_management_service),
) -> ApiResponse[bool]:
	try:
		existing = service.get_feature_set(feature_set_id, project_id=project_id)
	except LookupError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

	if existing.is_builtin:
		authz.require_project_scope(actor, "feature:delete", project_id)
	else:
		authz.require_project_permission(
			actor, "feature:delete", project_id, owner_id=existing.user_id, action="mutate"
		)

	try:
		deleted = service.delete_feature_set(feature_set_id, project_id=project_id)
	except LookupError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

	return ApiResponse.ok(data=deleted, message="Đã xóa gói đặc trưng")
