"""Admin User Management endpoints (/api/v1/users)."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from usfds_core.domain.entities.auth import ActorContext
from usfds_core.domain.entities.enums import UserStatus
from usfds_core.domain.entities.system import User
from usfds_core.services.auth.auth_service import AuthService
from usfds_core.services.auth.authz_service import AuthzService
from usfds_server.providers.auth import get_actor_context, get_auth_service, get_authz_service
from usfds_server.schemas.auth_schemas import (
	AdminUserResponse,
	CreateUserRequest,
	ResetPasswordRequest,
	SetSystemRolesRequest,
	UpdateUserRequest,
	UpdateUserStatusRequest,
)
from usfds_server.schemas.base_response import ApiResponse

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


def _to_admin_user(user: User, authz: AuthzService) -> AdminUserResponse:
	role_ids = authz.role_repo.get_system_user_role_ids(user.user_id)
	return AdminUserResponse(
		user_id=user.user_id,
		username=user.username,
		email=user.email,
		full_name=user.full_name,
		status=user.status.value if hasattr(user.status, "value") else str(user.status),
		last_login_at=user.last_login_at,
		created_at=user.created_at,
		system_role_ids=role_ids,
	)


@router.get("", response_model=ApiResponse[List[AdminUserResponse]], summary="List all users (system_admin)")
def list_users(
	actor: ActorContext = Depends(get_actor_context),
	auth_service: AuthService = Depends(get_auth_service),
	authz: AuthzService = Depends(get_authz_service),
) -> ApiResponse[List[AdminUserResponse]]:
	authz.require_system_permission(actor, "user:read")
	users = auth_service.list_users()
	return ApiResponse.ok(data=[_to_admin_user(u, authz) for u in users], message="Users retrieved")


@router.post(
	"",
	response_model=ApiResponse[AdminUserResponse],
	status_code=status.HTTP_201_CREATED,
	summary="Create a user (system_admin)",
)
def create_user(
	request: CreateUserRequest,
	actor: ActorContext = Depends(get_actor_context),
	auth_service: AuthService = Depends(get_auth_service),
	authz: AuthzService = Depends(get_authz_service),
) -> ApiResponse[AdminUserResponse]:
	authz.require_system_permission(actor, "user:create")
	try:
		user = auth_service.create_user(
			username=request.username,
			password=request.password,
			email=request.email,
			full_name=request.full_name,
			system_role_names=request.system_roles,
			assigned_by=actor.user_id,
		)
		return ApiResponse.ok(data=_to_admin_user(user, authz), message="User created", status_code=201)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{user_id}", response_model=ApiResponse[AdminUserResponse], summary="Get user by ID (system_admin)")
def get_user(
	user_id: UUID,
	actor: ActorContext = Depends(get_actor_context),
	auth_service: AuthService = Depends(get_auth_service),
	authz: AuthzService = Depends(get_authz_service),
) -> ApiResponse[AdminUserResponse]:
	authz.require_system_permission(actor, "user:read")
	try:
		user = auth_service.get_user(user_id)
		return ApiResponse.ok(data=_to_admin_user(user, authz), message="User retrieved")
	except LookupError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/{user_id}", response_model=ApiResponse[AdminUserResponse], summary="Update user (system_admin)")
def update_user(
	user_id: UUID,
	request: UpdateUserRequest,
	actor: ActorContext = Depends(get_actor_context),
	auth_service: AuthService = Depends(get_auth_service),
	authz: AuthzService = Depends(get_authz_service),
) -> ApiResponse[AdminUserResponse]:
	authz.require_system_permission(actor, "user:update")
	try:
		user = auth_service.update_user(user_id=user_id, full_name=request.full_name, email=request.email)
		return ApiResponse.ok(data=_to_admin_user(user, authz), message="User updated")
	except LookupError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.patch("/{user_id}/status", response_model=ApiResponse[AdminUserResponse], summary="Enable/Disable user (system_admin)")
def set_user_status(
	user_id: UUID,
	request: UpdateUserStatusRequest,
	actor: ActorContext = Depends(get_actor_context),
	auth_service: AuthService = Depends(get_auth_service),
	authz: AuthzService = Depends(get_authz_service),
) -> ApiResponse[AdminUserResponse]:
	authz.require_system_permission(actor, "user:manage")
	try:
		next_status = UserStatus(request.status)
		user = auth_service.set_user_status(user_id=user_id, status=next_status)
		return ApiResponse.ok(data=_to_admin_user(user, authz), message="User status updated")
	except LookupError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{user_id}/reset-password", response_model=ApiResponse[bool], summary="Reset user password (system_admin)")
def reset_password(
	user_id: UUID,
	request: ResetPasswordRequest,
	actor: ActorContext = Depends(get_actor_context),
	auth_service: AuthService = Depends(get_auth_service),
	authz: AuthzService = Depends(get_authz_service),
) -> ApiResponse[bool]:
	authz.require_system_permission(actor, "user:manage")
	try:
		auth_service.reset_password(user_id=user_id, new_password=request.new_password)
		return ApiResponse.ok(data=True, message="Password reset successfully")
	except LookupError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.put("/{user_id}/system-roles", response_model=ApiResponse[List[str]], summary="Assign system roles to user")
def set_system_roles(
	user_id: UUID,
	request: SetSystemRolesRequest,
	actor: ActorContext = Depends(get_actor_context),
	authz: AuthzService = Depends(get_authz_service),
) -> ApiResponse[List[str]]:
	authz.require_system_permission(actor, "user:manage")
	try:
		role_keys: List[str] = []
		for rid in request.role_ids:
			role = authz.role_repo.get_by_id(rid)
			if role is None:
				raise ValueError(f"Role {rid} not found")
			role_keys.append(role.name)
		assigned = authz.set_system_user_roles(actor, user_id, role_keys)
		return ApiResponse.ok(data=assigned, message="System roles updated")
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
