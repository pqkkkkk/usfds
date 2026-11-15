"""Pydantic request/response schemas for Authentication, Users, and RBAC."""
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class AuthModeResponse(BaseModel):
	auth_mode: str


class LoginRequest(BaseModel):
	username: str
	password: str


class RefreshRequest(BaseModel):
	refresh_token: str


class LogoutRequest(BaseModel):
	refresh_token: str


class TokenPairResponse(BaseModel):
	access_token: str
	refresh_token: str
	token_type: str = "bearer"


class UpdateOwnProfileRequest(BaseModel):
	full_name: Optional[str] = None
	email: Optional[str] = None


class ChangePasswordRequest(BaseModel):
	current_password: str
	new_password: str = Field(..., min_length=6)


class ProjectPermissionsDto(BaseModel):
	project_id: UUID
	role_keys: List[str]
	permissions: Dict[str, List[str]]


class AuthUserResponse(BaseModel):
	user_id: UUID
	username: str
	email: Optional[str] = None
	full_name: Optional[str] = None
	status: str
	last_login_at: Optional[datetime] = None
	is_system_admin: bool = False
	system_role_keys: List[str] = []
	system_permissions: Dict[str, List[str]] = {}
	projects: List[ProjectPermissionsDto] = []


class CreateUserRequest(BaseModel):
	username: str
	password: str = Field(..., min_length=6)
	email: Optional[str] = None
	full_name: Optional[str] = None
	system_roles: List[str] = ["system_member"]


class UpdateUserRequest(BaseModel):
	full_name: Optional[str] = None
	email: Optional[str] = None


class UpdateUserStatusRequest(BaseModel):
	status: str


class ResetPasswordRequest(BaseModel):
	new_password: str = Field(..., min_length=6)


class SetSystemRolesRequest(BaseModel):
	role_ids: List[UUID]


class AdminUserResponse(BaseModel):
	user_id: UUID
	username: str
	email: Optional[str] = None
	full_name: Optional[str] = None
	status: str
	last_login_at: Optional[datetime] = None
	created_at: datetime
	system_role_ids: List[UUID] = []


class RoleGrantDto(BaseModel):
	permission_id: Optional[UUID] = None
	permission_code: Optional[str] = None
	grant_scope: str


class RoleDto(BaseModel):
	role_id: UUID
	name: str
	display_name: str
	scope: str
	is_system: bool
	description: Optional[str] = None
	grants: List[RoleGrantDto] = []


class CreateRoleRequest(BaseModel):
	name: str
	display_name: str
	scope: str
	description: Optional[str] = None
	grants: List[RoleGrantDto] = []


class SetRolePermissionsRequest(BaseModel):
	grants: List[RoleGrantDto]


class PermissionDto(BaseModel):
	permission_id: UUID
	code: str
	resource: str
	action: str
	scope: str
	description: Optional[str] = None


class ProjectRoleSummaryDto(BaseModel):
	role_id: UUID
	name: str
	display_name: str


class ProjectMemberDto(BaseModel):
	project_id: UUID
	user_id: UUID
	username: str
	full_name: Optional[str] = None
	email: Optional[str] = None
	status: str
	roles: List[ProjectRoleSummaryDto] = []
	role_keys: List[str] = []
	permissions: Dict[str, List[str]] = {}
	added_by: Optional[UUID] = None
	created_at: Optional[datetime] = None


class AddProjectMemberRequest(BaseModel):
	user_id: Optional[UUID] = None
	username: Optional[str] = None
	password: Optional[str] = Field(default=None, min_length=6)
	full_name: Optional[str] = None
	email: Optional[str] = None
	role_id: UUID


class AssignProjectMemberRoleRequest(BaseModel):
	role_id: UUID


class SetProjectMemberRolesRequest(BaseModel):
	role_ids: List[UUID]
