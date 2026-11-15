"""Authentication endpoints (/api/v1/auth)."""
from fastapi import APIRouter, Depends, HTTPException, Request, status

from usfds_core.domain.entities.auth import ActorContext
from usfds_core.domain.entities.system import User
from usfds_core.services.auth.auth_service import AuthService
from usfds_server.config import settings
from usfds_server.providers.auth import get_actor_context, get_auth_service, get_current_user
from usfds_server.schemas.auth_schemas import (
	AuthModeResponse,
	AuthUserResponse,
	ChangePasswordRequest,
	LoginRequest,
	LogoutRequest,
	ProjectPermissionsDto,
	RefreshRequest,
	TokenPairResponse,
	UpdateOwnProfileRequest,
)
from usfds_server.schemas.base_response import ApiResponse

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


def _to_auth_user_response(user: User, actor: ActorContext) -> AuthUserResponse:
	return AuthUserResponse(
		user_id=user.user_id,
		username=user.username,
		email=user.email,
		full_name=user.full_name,
		status=user.status.value if hasattr(user.status, "value") else str(user.status),
		last_login_at=user.last_login_at,
		is_system_admin=actor.is_system_admin,
		system_role_keys=actor.system_role_keys,
		system_permissions={
			k: [s.value if hasattr(s, "value") else str(s) for s in v]
			for k, v in actor.system_permissions.items()
		},
		projects=[
			ProjectPermissionsDto(
				project_id=p.project_id,
				role_keys=p.role_keys,
				permissions={
					k: [s.value if hasattr(s, "value") else str(s) for s in v]
					for k, v in p.permissions.items()
				},
			)
			for p in actor.projects
		],
	)


@router.get("/mode", response_model=ApiResponse[AuthModeResponse])
def get_auth_mode():
	return ApiResponse.ok(AuthModeResponse(auth_mode=settings.auth_mode))


@router.post("/login", response_model=ApiResponse[TokenPairResponse])
def login(
	payload: LoginRequest,
	request: Request,
	auth_service: AuthService = Depends(get_auth_service),
):
	user_agent = request.headers.get("user-agent")
	ip_address = request.client.host if request.client else None
	_, access_token, refresh_token = auth_service.login(
		username=payload.username,
		password=payload.password,
		user_agent=user_agent,
		ip_address=ip_address,
	)
	return ApiResponse.ok(
		TokenPairResponse(access_token=access_token, refresh_token=refresh_token),
		message="Login successful",
	)


@router.post("/refresh", response_model=ApiResponse[TokenPairResponse])
def refresh_token(
	payload: RefreshRequest,
	auth_service: AuthService = Depends(get_auth_service),
):
	_, access_token, new_refresh = auth_service.refresh(payload.refresh_token)
	return ApiResponse.ok(
		TokenPairResponse(access_token=access_token, refresh_token=new_refresh),
		message="Token refreshed",
	)


@router.post("/logout", response_model=ApiResponse[None])
def logout(
	payload: LogoutRequest,
	auth_service: AuthService = Depends(get_auth_service),
):
	auth_service.logout(payload.refresh_token)
	return ApiResponse.ok(None, message="Logged out")


@router.get("/me", response_model=ApiResponse[AuthUserResponse])
def get_me(
	current_user: User = Depends(get_current_user),
	actor: ActorContext = Depends(get_actor_context),
):
	return ApiResponse.ok(_to_auth_user_response(current_user, actor))


@router.patch("/me", response_model=ApiResponse[AuthUserResponse])
def update_me(
	payload: UpdateOwnProfileRequest,
	current_user: User = Depends(get_current_user),
	actor: ActorContext = Depends(get_actor_context),
	auth_service: AuthService = Depends(get_auth_service),
):
	try:
		updated = auth_service.update_own_profile(
			current_user.user_id,
			full_name=payload.full_name,
			email=payload.email,
		)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
	return ApiResponse.ok(_to_auth_user_response(updated, actor), message="Profile updated")


@router.post("/me/password", response_model=ApiResponse[None])
def change_own_password(
	payload: ChangePasswordRequest,
	current_user: User = Depends(get_current_user),
	auth_service: AuthService = Depends(get_auth_service),
):
	try:
		auth_service.change_password(
			current_user.user_id,
			current_password=payload.current_password,
			new_password=payload.new_password,
		)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
	return ApiResponse.ok(None, message="Password changed")
