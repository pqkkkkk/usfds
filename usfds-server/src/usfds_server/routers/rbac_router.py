"""RBAC Role & Permission Management endpoints (/api/v1/rbac)."""
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from usfds_core.domain.entities.auth import ActorContext
from usfds_core.domain.entities.enums import GrantScope, RoleScope
from usfds_core.services.auth.authz_service import AuthzService
from usfds_server.providers.auth import get_actor_context, get_authz_service
from usfds_server.schemas.auth_schemas import (
	CreateRoleRequest,
	PermissionDto,
	RoleDto,
	RoleGrantDto,
	SetRolePermissionsRequest,
)
from usfds_server.schemas.base_response import ApiResponse

router = APIRouter(prefix="/api/v1/rbac", tags=["RBAC"])


def _resolve_grants_input(authz: AuthzService, grants: List[RoleGrantDto]) -> List[Tuple[str, GrantScope]]:
	perm_by_id = {p.permission_id: p.code for p in authz.permission_repo.list_all()}
	resolved: List[Tuple[str, GrantScope]] = []
	for g in grants:
		code = g.permission_code
		if not code and g.permission_id is not None:
			code = perm_by_id.get(g.permission_id)
		if not code:
			raise ValueError("Each grant must specify a valid permission_id or permission_code")
		resolved.append((code, GrantScope(g.grant_scope)))
	return resolved


def _to_role_dto(
	role,
	grants: List[Tuple[str, GrantScope]],
	perm_id_by_code: Dict[str, UUID],
) -> RoleDto:
	return RoleDto(
		role_id=role.role_id,
		name=role.name,
		display_name=role.display_name,
		scope=role.scope.value if hasattr(role.scope, "value") else str(role.scope),
		is_system=role.is_system,
		description=role.description,
		grants=[
			RoleGrantDto(
				permission_id=perm_id_by_code.get(code),
				permission_code=code,
				grant_scope=gs.value if hasattr(gs, "value") else str(gs),
			)
			for code, gs in grants
			if code in perm_id_by_code
		],
	)


@router.get("/roles", response_model=ApiResponse[List[RoleDto]], summary="List roles with grants")
def list_roles(
	scope: Optional[RoleScope] = Query(None, description="Optional SYSTEM or PROJECT filter"),
	actor: ActorContext = Depends(get_actor_context),
	authz: AuthzService = Depends(get_authz_service),
) -> ApiResponse[List[RoleDto]]:
	roles_with_grants = authz.list_roles(actor, scope=scope)
	perm_id_by_code = {p.code: p.permission_id for p in authz.permission_repo.list_all()}
	return ApiResponse.ok(
		data=[_to_role_dto(r, g, perm_id_by_code) for r, g in roles_with_grants],
		message="Roles retrieved",
	)


@router.post(
	"/roles",
	response_model=ApiResponse[RoleDto],
	status_code=status.HTTP_201_CREATED,
	summary="Create a custom role (system_admin)",
)
def create_role(
	request: CreateRoleRequest,
	actor: ActorContext = Depends(get_actor_context),
	authz: AuthzService = Depends(get_authz_service),
) -> ApiResponse[RoleDto]:
	try:
		role_scope = RoleScope(request.scope)
		role = authz.create_role(
			actor=actor,
			name=request.name,
			display_name=request.display_name,
			scope=role_scope,
			description=request.description,
		)
		grants_tuples: List[Tuple[str, GrantScope]] = []
		if request.grants:
			grants_tuples = _resolve_grants_input(authz, request.grants)
			authz.set_role_permissions(actor, role.role_id, grants_tuples)
		perm_id_by_code = {p.code: p.permission_id for p in authz.permission_repo.list_all()}
		return ApiResponse.ok(
			data=_to_role_dto(role, grants_tuples, perm_id_by_code),
			message="Role created",
			status_code=201,
		)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.put(
	"/roles/{role_id}/permissions",
	response_model=ApiResponse[RoleDto],
	summary="Replace permissions for a role (system_admin)",
)
def set_role_permissions(
	role_id: UUID,
	request: SetRolePermissionsRequest,
	actor: ActorContext = Depends(get_actor_context),
	authz: AuthzService = Depends(get_authz_service),
) -> ApiResponse[RoleDto]:
	try:
		grants_tuples = _resolve_grants_input(authz, request.grants)
		authz.set_role_permissions(actor, role_id, grants_tuples)
		role = authz.role_repo.get_by_id(role_id)
		perm_id_by_code = {p.code: p.permission_id for p in authz.permission_repo.list_all()}
		return ApiResponse.ok(
			data=_to_role_dto(role, grants_tuples, perm_id_by_code),
			message="Role permissions updated",
		)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/permissions", response_model=ApiResponse[List[PermissionDto]], summary="List permission catalog")
def list_permissions(
	actor: ActorContext = Depends(get_actor_context),
	authz: AuthzService = Depends(get_authz_service),
) -> ApiResponse[List[PermissionDto]]:
	perms = authz.list_permissions(actor)
	return ApiResponse.ok(
		data=[
			PermissionDto(
				permission_id=p.permission_id,
				code=p.code,
				resource=p.resource,
				action=p.action,
				scope=p.scope.value if hasattr(p.scope, "value") else str(p.scope),
				description=p.description,
			)
			for p in perms
		],
		message="Permissions retrieved",
	)
