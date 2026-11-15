"""SQLAlchemy repositories for the `auth` domain."""
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from usfds_core.domain.entities.auth import (
	ActorContext,
	Permission,
	ProjectActorContext,
	ProjectMember,
	ProjectPermissions,
	Role,
	RolePermission,
	UserSession,
)
from usfds_core.domain.entities.enums import GrantScope, RoleScope, UserStatus
from usfds_core.domain.entities.system import User
from usfds_core.repositories.base_rbac_repo import (
	IPermissionRepository,
	IProjectMemberRepository,
	IRoleRepository,
)
from usfds_core.repositories.base_session_repo import IUserSessionRepository
from usfds_core.repositories.base_user_repo import IUserRepository
from usfds_infra.database.models import (
	PermissionModel,
	ProjectMemberModel,
	RoleModel,
	RolePermissionModel,
	SystemUserRoleModel,
	UserModel,
	UserSessionModel,
)


class SqlUserRepository(IUserRepository):
	"""SQLAlchemy implementation of IUserRepository."""

	def __init__(self, session: Session) -> None:
		self.session = session

	@staticmethod
	def _to_entity(model: UserModel) -> User:
		try:
			status_val: UserStatus | str = UserStatus(model.status)
		except ValueError:
			status_val = model.status
		return User(
			user_id=UUID(model.user_id),
			username=model.username,
			email=model.email,
			full_name=model.full_name,
			password_hash=model.password_hash,
			status=status_val,
			last_login_at=model.last_login_at,
			created_at=model.created_at,
			updated_at=model.updated_at,
		)

	def save(self, user: User) -> User:
		model = self.session.get(UserModel, str(user.user_id))
		status_str = user.status.value if hasattr(user.status, "value") else str(user.status)
		if model is None:
			model = UserModel(
				user_id=str(user.user_id),
				username=user.username,
				email=user.email,
				full_name=user.full_name,
				password_hash=user.password_hash,
				status=status_str,
				last_login_at=user.last_login_at,
				created_at=user.created_at or datetime.now(timezone.utc),
				updated_at=user.updated_at or datetime.now(timezone.utc),
			)
			self.session.add(model)
		else:
			model.username = user.username
			model.email = user.email
			model.full_name = user.full_name
			model.password_hash = user.password_hash
			model.status = status_str
			model.last_login_at = user.last_login_at
			model.updated_at = datetime.now(timezone.utc)
		self.session.flush()
		return self._to_entity(model)

	def get_by_id(self, user_id: UUID) -> Optional[User]:
		model = self.session.get(UserModel, str(user_id))
		return self._to_entity(model) if model else None

	def get_by_username(self, username: str) -> Optional[User]:
		stmt = select(UserModel).where(UserModel.username == username)
		model = self.session.execute(stmt).scalar_one_or_none()
		return self._to_entity(model) if model else None

	def get_by_email(self, email: str) -> Optional[User]:
		stmt = select(UserModel).where(UserModel.email == email)
		model = self.session.execute(stmt).scalar_one_or_none()
		return self._to_entity(model) if model else None

	def list_all(self) -> List[User]:
		stmt = select(UserModel).order_by(UserModel.created_at.asc(), UserModel.username.asc())
		return [self._to_entity(m) for m in self.session.execute(stmt).scalars().all()]

	def delete(self, user_id: UUID) -> bool:
		model = self.session.get(UserModel, str(user_id))
		if model is None:
			return False
		self.session.delete(model)
		self.session.flush()
		return True

	def load_actor_context(self, user_id: UUID) -> Optional[ActorContext]:
		user = self.session.get(UserModel, str(user_id))
		if user is None:
			return None

		sys_rows = self.session.execute(
			select(RoleModel.name, PermissionModel.code, RolePermissionModel.grant_scope)
			.select_from(SystemUserRoleModel)
			.join(RoleModel, RoleModel.role_id == SystemUserRoleModel.role_id)
			.outerjoin(RolePermissionModel, RolePermissionModel.role_id == RoleModel.role_id)
			.outerjoin(PermissionModel, PermissionModel.permission_id == RolePermissionModel.permission_id)
			.where(SystemUserRoleModel.user_id == str(user_id))
			.order_by(RoleModel.name.asc())
		).all()

		sys_role_keys: List[str] = []
		sys_perms: Dict[str, List[GrantScope]] = defaultdict(list)
		for role_name, perm_code, grant_scope in sys_rows:
			if role_name not in sys_role_keys:
				sys_role_keys.append(role_name)
			if perm_code and grant_scope:
				gs = GrantScope(grant_scope)
				if gs not in sys_perms[perm_code]:
					sys_perms[perm_code].append(gs)

		proj_rows = self.session.execute(
			select(ProjectMemberModel.project_id, RoleModel.name, PermissionModel.code, RolePermissionModel.grant_scope)
			.select_from(ProjectMemberModel)
			.join(RoleModel, RoleModel.role_id == ProjectMemberModel.role_id)
			.outerjoin(RolePermissionModel, RolePermissionModel.role_id == RoleModel.role_id)
			.outerjoin(PermissionModel, PermissionModel.permission_id == RolePermissionModel.permission_id)
			.where(ProjectMemberModel.user_id == str(user_id))
			.order_by(ProjectMemberModel.project_id.asc(), RoleModel.name.asc())
		).all()

		proj_roles_map: Dict[str, List[str]] = defaultdict(list)
		proj_perms_map: Dict[str, Dict[str, List[GrantScope]]] = defaultdict(lambda: defaultdict(list))
		for pid, role_name, perm_code, grant_scope in proj_rows:
			if role_name not in proj_roles_map[pid]:
				proj_roles_map[pid].append(role_name)
			if perm_code and grant_scope:
				gs = GrantScope(grant_scope)
				if gs not in proj_perms_map[pid][perm_code]:
					proj_perms_map[pid][perm_code].append(gs)

		projects = [
			ProjectPermissions(
				project_id=UUID(pid),
				role_keys=proj_roles_map[pid],
				permissions=dict(proj_perms_map[pid]),
			)
			for pid in sorted(proj_roles_map.keys())
		]

		try:
			status_val: UserStatus | str = UserStatus(user.status)
		except ValueError:
			status_val = user.status

		return ActorContext(
			user_id=UUID(user.user_id),
			username=user.username,
			status=status_val,
			projects=projects,
			system_role_keys=sys_role_keys,
			system_permissions=dict(sys_perms),
			is_system_admin="system_admin" in sys_role_keys,
		)


class SqlUserSessionRepository(IUserSessionRepository):
	"""SQLAlchemy implementation of IUserSessionRepository."""

	def __init__(self, session: Session) -> None:
		self.session = session

	@staticmethod
	def _to_entity(model: UserSessionModel) -> UserSession:
		return UserSession(
			session_id=UUID(model.session_id),
			user_id=UUID(model.user_id),
			refresh_token_hash=model.refresh_token_hash,
			expires_at=model.expires_at,
			revoked_at=model.revoked_at,
			user_agent=model.user_agent,
			ip_address=model.ip_address,
			created_at=model.created_at,
		)

	def save(self, session: UserSession) -> UserSession:
		model = self.session.get(UserSessionModel, str(session.session_id))
		if model is None:
			model = UserSessionModel(
				session_id=str(session.session_id),
				user_id=str(session.user_id),
				refresh_token_hash=session.refresh_token_hash,
				expires_at=session.expires_at,
				revoked_at=session.revoked_at,
				user_agent=session.user_agent,
				ip_address=session.ip_address,
				created_at=session.created_at or datetime.now(timezone.utc),
			)
			self.session.add(model)
		else:
			model.refresh_token_hash = session.refresh_token_hash
			model.expires_at = session.expires_at
			model.revoked_at = session.revoked_at
		self.session.flush()
		return self._to_entity(model)

	def get_by_id(self, session_id: UUID) -> Optional[UserSession]:
		model = self.session.get(UserSessionModel, str(session_id))
		return self._to_entity(model) if model else None

	def get_by_refresh_token_hash(self, token_hash: str) -> Optional[UserSession]:
		stmt = select(UserSessionModel).where(UserSessionModel.refresh_token_hash == token_hash)
		model = self.session.execute(stmt).scalar_one_or_none()
		return self._to_entity(model) if model else None

	def list_for_user(self, user_id: UUID) -> List[UserSession]:
		stmt = (
			select(UserSessionModel)
			.where(UserSessionModel.user_id == str(user_id))
			.order_by(UserSessionModel.created_at.desc())
		)
		return [self._to_entity(m) for m in self.session.execute(stmt).scalars().all()]

	def revoke_session(self, session_id: UUID, revoked_at: datetime) -> bool:
		model = self.session.get(UserSessionModel, str(session_id))
		if model is None:
			return False
		model.revoked_at = revoked_at
		self.session.flush()
		return True

	def revoke_all_for_user(self, user_id: UUID, revoked_at: datetime) -> int:
		stmt = select(UserSessionModel).where(
			UserSessionModel.user_id == str(user_id),
			UserSessionModel.revoked_at.is_(None),
		)
		models = self.session.execute(stmt).scalars().all()
		for m in models:
			m.revoked_at = revoked_at
		self.session.flush()
		return len(models)


class SqlRoleRepository(IRoleRepository):
	"""SQLAlchemy implementation of IRoleRepository."""

	def __init__(self, session: Session) -> None:
		self.session = session

	@staticmethod
	def _to_entity(model: RoleModel) -> Role:
		try:
			scope_val: RoleScope | str = RoleScope(model.scope)
		except ValueError:
			scope_val = model.scope
		return Role(
			role_id=UUID(model.role_id),
			name=model.name,
			display_name=model.display_name,
			scope=scope_val,
			is_system=model.is_system,
			description=model.description,
			created_at=model.created_at,
			updated_at=model.updated_at,
		)

	def save(self, role: Role) -> Role:
		model = self.session.get(RoleModel, str(role.role_id))
		scope_str = role.scope.value if hasattr(role.scope, "value") else str(role.scope)
		if model is None:
			model = RoleModel(
				role_id=str(role.role_id),
				name=role.name,
				display_name=role.display_name,
				scope=scope_str,
				is_system=role.is_system,
				description=role.description,
				created_at=role.created_at or datetime.now(timezone.utc),
				updated_at=role.updated_at or datetime.now(timezone.utc),
			)
			self.session.add(model)
		else:
			model.name = role.name
			model.display_name = role.display_name
			model.scope = scope_str
			model.is_system = role.is_system
			model.description = role.description
			model.updated_at = datetime.now(timezone.utc)
		self.session.flush()
		return self._to_entity(model)

	def get_by_id(self, role_id: UUID) -> Optional[Role]:
		model = self.session.get(RoleModel, str(role_id))
		return self._to_entity(model) if model else None

	def get_by_scope_and_name(self, scope: RoleScope, name: str) -> Optional[Role]:
		scope_str = scope.value if hasattr(scope, "value") else str(scope)
		stmt = select(RoleModel).where(RoleModel.scope == scope_str, RoleModel.name == name)
		model = self.session.execute(stmt).scalar_one_or_none()
		return self._to_entity(model) if model else None

	def list_all(self, scope: Optional[RoleScope] = None) -> List[Role]:
		stmt = select(RoleModel)
		if scope is not None:
			scope_str = scope.value if hasattr(scope, "value") else str(scope)
			stmt = stmt.where(RoleModel.scope == scope_str)
		stmt = stmt.order_by(RoleModel.scope.asc(), RoleModel.name.asc())
		return [self._to_entity(m) for m in self.session.execute(stmt).scalars().all()]

	def get_role_permissions(self, role_id: UUID) -> List[RolePermission]:
		stmt = (
			select(RolePermissionModel)
			.where(RolePermissionModel.role_id == str(role_id))
			.order_by(RolePermissionModel.permission_id.asc())
		)
		rows = self.session.execute(stmt).scalars().all()
		return [
			RolePermission(
				role_id=UUID(r.role_id),
				permission_id=UUID(r.permission_id),
				grant_scope=GrantScope(r.grant_scope),
			)
			for r in rows
		]

	def set_role_permissions(self, role_id: UUID, grants: List[RolePermission]) -> List[RolePermission]:
		self.session.execute(delete(RolePermissionModel).where(RolePermissionModel.role_id == str(role_id)))
		for g in grants:
			scope_str = g.grant_scope.value if hasattr(g.grant_scope, "value") else str(g.grant_scope)
			self.session.add(
				RolePermissionModel(
					role_id=str(role_id),
					permission_id=str(g.permission_id),
					grant_scope=scope_str,
				)
			)
		self.session.flush()
		return self.get_role_permissions(role_id)

	def get_system_user_role_ids(self, user_id: UUID) -> List[UUID]:
		stmt = (
			select(SystemUserRoleModel.role_id)
			.where(SystemUserRoleModel.user_id == str(user_id))
			.order_by(SystemUserRoleModel.role_id.asc())
		)
		return [UUID(r) for r in self.session.execute(stmt).scalars().all()]

	def set_system_user_roles(self, user_id: UUID, role_ids: List[UUID], assigned_by: Optional[UUID] = None) -> None:
		self.session.execute(delete(SystemUserRoleModel).where(SystemUserRoleModel.user_id == str(user_id)))
		for rid in role_ids:
			self.session.add(
				SystemUserRoleModel(
					user_id=str(user_id),
					role_id=str(rid),
					assigned_by=str(assigned_by) if assigned_by else None,
				)
			)
		self.session.flush()

	def count_role_assignments(self, role_id: UUID) -> Dict[str, int]:
		sys_count = self.session.execute(
			select(func.count()).select_from(SystemUserRoleModel).where(SystemUserRoleModel.role_id == str(role_id))
		).scalar_one()
		proj_count = self.session.execute(
			select(func.count()).select_from(ProjectMemberModel).where(ProjectMemberModel.role_id == str(role_id))
		).scalar_one()
		return {"system": int(sys_count), "project": int(proj_count)}

	def delete(self, role_id: UUID) -> bool:
		model = self.session.get(RoleModel, str(role_id))
		if model is None:
			return False
		self.session.delete(model)
		self.session.flush()
		return True

	def load_actor_context(self, user_id: UUID) -> Optional[ActorContext]:
		user = self.session.get(UserModel, str(user_id))
		if user is None:
			return None

		sys_rows = self.session.execute(
			select(RoleModel.name, PermissionModel.code, RolePermissionModel.grant_scope)
			.select_from(SystemUserRoleModel)
			.join(RoleModel, RoleModel.role_id == SystemUserRoleModel.role_id)
			.outerjoin(RolePermissionModel, RolePermissionModel.role_id == RoleModel.role_id)
			.outerjoin(PermissionModel, PermissionModel.permission_id == RolePermissionModel.permission_id)
			.where(SystemUserRoleModel.user_id == str(user_id))
			.order_by(RoleModel.name.asc())
		).all()

		sys_role_keys: List[str] = []
		sys_perms: Dict[str, List[GrantScope]] = defaultdict(list)
		for role_name, perm_code, grant_scope in sys_rows:
			if role_name not in sys_role_keys:
				sys_role_keys.append(role_name)
			if perm_code and grant_scope:
				gs = GrantScope(grant_scope)
				if gs not in sys_perms[perm_code]:
					sys_perms[perm_code].append(gs)

		proj_rows = self.session.execute(
			select(ProjectMemberModel.project_id, RoleModel.name, PermissionModel.code, RolePermissionModel.grant_scope)
			.select_from(ProjectMemberModel)
			.join(RoleModel, RoleModel.role_id == ProjectMemberModel.role_id)
			.outerjoin(RolePermissionModel, RolePermissionModel.role_id == RoleModel.role_id)
			.outerjoin(PermissionModel, PermissionModel.permission_id == RolePermissionModel.permission_id)
			.where(ProjectMemberModel.user_id == str(user_id))
			.order_by(ProjectMemberModel.project_id.asc(), RoleModel.name.asc())
		).all()

		proj_roles_map: Dict[str, List[str]] = defaultdict(list)
		proj_perms_map: Dict[str, Dict[str, List[GrantScope]]] = defaultdict(lambda: defaultdict(list))
		for pid, role_name, perm_code, grant_scope in proj_rows:
			if role_name not in proj_roles_map[pid]:
				proj_roles_map[pid].append(role_name)
			if perm_code and grant_scope:
				gs = GrantScope(grant_scope)
				if gs not in proj_perms_map[pid][perm_code]:
					proj_perms_map[pid][perm_code].append(gs)

		projects = [
			ProjectPermissions(
				project_id=UUID(pid),
				role_keys=proj_roles_map[pid],
				permissions=dict(proj_perms_map[pid]),
			)
			for pid in sorted(proj_roles_map.keys())
		]

		try:
			status_val: UserStatus | str = UserStatus(user.status)
		except ValueError:
			status_val = user.status

		return ActorContext(
			user_id=UUID(user.user_id),
			username=user.username,
			status=status_val,
			projects=projects,
			system_role_keys=sys_role_keys,
			system_permissions=dict(sys_perms),
			is_system_admin="system_admin" in sys_role_keys,
		)


class SqlPermissionRepository(IPermissionRepository):
	"""SQLAlchemy implementation of IPermissionRepository."""

	def __init__(self, session: Session) -> None:
		self.session = session

	@staticmethod
	def _to_entity(model: PermissionModel) -> Permission:
		return Permission(
			permission_id=UUID(model.permission_id),
			code=model.code,
			resource=model.resource,
			action=model.action,
			scope=GrantScope(model.scope),
			description=model.description,
		)

	def save(self, permission: Permission) -> Permission:
		model = self.session.get(PermissionModel, str(permission.permission_id))
		scope_str = permission.scope.value if hasattr(permission.scope, "value") else str(permission.scope)
		if model is None:
			model = PermissionModel(
				permission_id=str(permission.permission_id),
				code=permission.code,
				resource=permission.resource,
				action=permission.action,
				scope=scope_str,
				description=permission.description,
			)
			self.session.add(model)
		else:
			model.code = permission.code
			model.resource = permission.resource
			model.action = permission.action
			model.scope = scope_str
			model.description = permission.description
		self.session.flush()
		return self._to_entity(model)

	def get_by_id(self, permission_id: UUID) -> Optional[Permission]:
		model = self.session.get(PermissionModel, str(permission_id))
		return self._to_entity(model) if model else None

	def get_by_code(self, code: str) -> Optional[Permission]:
		stmt = select(PermissionModel).where(PermissionModel.code == code)
		model = self.session.execute(stmt).scalar_one_or_none()
		return self._to_entity(model) if model else None

	def list_all(self) -> List[Permission]:
		stmt = select(PermissionModel).order_by(PermissionModel.code.asc())
		return [self._to_entity(m) for m in self.session.execute(stmt).scalars().all()]


class SqlProjectMemberRepository(IProjectMemberRepository):
	"""SQLAlchemy implementation of IProjectMemberRepository and ActorContext assembly."""

	def __init__(self, session: Session) -> None:
		self.session = session

	@staticmethod
	def _to_entity(model: ProjectMemberModel) -> ProjectMember:
		return ProjectMember(
			project_id=UUID(model.project_id),
			user_id=UUID(model.user_id),
			role_id=UUID(model.role_id),
			added_by=UUID(model.added_by) if model.added_by else None,
			created_at=model.created_at,
			updated_at=model.updated_at,
		)

	def add_member(
		self,
		project_id: UUID,
		user_id: UUID,
		role_id: UUID,
		added_by: Optional[UUID] = None,
	) -> ProjectMember:
		existing = self.session.get(ProjectMemberModel, (str(project_id), str(user_id), str(role_id)))
		if existing is not None:
			return self._to_entity(existing)
		model = ProjectMemberModel(
			project_id=str(project_id),
			user_id=str(user_id),
			role_id=str(role_id),
			added_by=str(added_by) if added_by else None,
		)
		self.session.add(model)
		self.session.flush()
		return self._to_entity(model)

	def remove_member(self, project_id: UUID, user_id: UUID, role_id: UUID) -> bool:
		existing = self.session.get(ProjectMemberModel, (str(project_id), str(user_id), str(role_id)))
		if existing is None:
			return False
		self.session.delete(existing)
		self.session.flush()
		return True

	def remove_user_from_project(self, project_id: UUID, user_id: UUID) -> int:
		stmt = delete(ProjectMemberModel).where(
			ProjectMemberModel.project_id == str(project_id),
			ProjectMemberModel.user_id == str(user_id),
		)
		res = self.session.execute(stmt)
		self.session.flush()
		return int(res.rowcount or 0)

	def list_members(self, project_id: UUID) -> List[ProjectMember]:
		stmt = (
			select(ProjectMemberModel)
			.where(ProjectMemberModel.project_id == str(project_id))
			.order_by(ProjectMemberModel.created_at.asc(), ProjectMemberModel.user_id.asc(), ProjectMemberModel.role_id.asc())
		)
		return [self._to_entity(m) for m in self.session.execute(stmt).scalars().all()]

	def list_user_roles_in_project(self, project_id: UUID, user_id: UUID) -> List[Role]:
		stmt = (
			select(RoleModel)
			.join(ProjectMemberModel, ProjectMemberModel.role_id == RoleModel.role_id)
			.where(
				ProjectMemberModel.project_id == str(project_id),
				ProjectMemberModel.user_id == str(user_id),
			)
			.order_by(RoleModel.name.asc())
		)
		return [SqlRoleRepository._to_entity(m) for m in self.session.execute(stmt).scalars().all()]

	def list_user_project_ids(self, user_id: UUID) -> List[UUID]:
		stmt = (
			select(ProjectMemberModel.project_id)
			.where(ProjectMemberModel.user_id == str(user_id))
			.distinct()
			.order_by(ProjectMemberModel.project_id.asc())
		)
		return [UUID(pid) for pid in self.session.execute(stmt).scalars().all()]

	def has_active_membership(self, user_id: UUID, project_id: UUID) -> bool:
		stmt = (
			select(ProjectMemberModel.project_id)
			.where(
				ProjectMemberModel.user_id == str(user_id),
				ProjectMemberModel.project_id == str(project_id),
			)
			.limit(1)
		)
		return self.session.execute(stmt).first() is not None

	def count_role_members_in_project(self, project_id: UUID, role_name: str) -> int:
		stmt = (
			select(func.count())
			.select_from(ProjectMemberModel)
			.join(RoleModel, RoleModel.role_id == ProjectMemberModel.role_id)
			.where(
				ProjectMemberModel.project_id == str(project_id),
				RoleModel.name == role_name,
			)
		)
		return int(self.session.execute(stmt).scalar_one())

	def load_project_actor_context(
		self,
		project_id: UUID,
		user_id: Optional[UUID] = None,
	) -> List[ProjectActorContext]:
		stmt = (
			select(
				UserModel,
				RoleModel,
				PermissionModel.code,
				RolePermissionModel.grant_scope,
				ProjectMemberModel.added_by,
				ProjectMemberModel.created_at,
			)
			.select_from(ProjectMemberModel)
			.join(UserModel, UserModel.user_id == ProjectMemberModel.user_id)
			.join(RoleModel, RoleModel.role_id == ProjectMemberModel.role_id)
			.outerjoin(RolePermissionModel, RolePermissionModel.role_id == RoleModel.role_id)
			.outerjoin(PermissionModel, PermissionModel.permission_id == RolePermissionModel.permission_id)
			.where(ProjectMemberModel.project_id == str(project_id))
			.order_by(UserModel.username.asc(), RoleModel.name.asc())
		)
		if user_id is not None:
			stmt = stmt.where(ProjectMemberModel.user_id == str(user_id))

		rows = self.session.execute(stmt).all()
		if not rows:
			return []

		grouped: Dict[str, ProjectActorContext] = {}
		seen_roles: Dict[str, set[str]] = defaultdict(set)
		perms_map: Dict[str, Dict[str, List[GrantScope]]] = defaultdict(lambda: defaultdict(list))

		for user_m, role_m, perm_code, grant_scope, added_by, created_at in rows:
			uid_str = user_m.user_id
			if uid_str not in grouped:
				try:
					status_val: UserStatus | str = UserStatus(user_m.status)
				except ValueError:
					status_val = user_m.status
				grouped[uid_str] = ProjectActorContext(
					project_id=project_id,
					user_id=UUID(uid_str),
					username=user_m.username,
					full_name=user_m.full_name,
					email=user_m.email,
					status=status_val,
					roles=[],
					role_keys=[],
					permissions={},
					added_by=UUID(added_by) if added_by else None,
					created_at=created_at,
				)
			elif created_at and grouped[uid_str].created_at and created_at < grouped[uid_str].created_at:
				grouped[uid_str].created_at = created_at

			if role_m.role_id not in seen_roles[uid_str]:
				seen_roles[uid_str].add(role_m.role_id)
				grouped[uid_str].roles.append(SqlRoleRepository._to_entity(role_m))
				if role_m.name not in grouped[uid_str].role_keys:
					grouped[uid_str].role_keys.append(role_m.name)

			if perm_code and grant_scope:
				gs = GrantScope(grant_scope)
				if gs in (GrantScope.OWN, GrantScope.PROJECT) and gs not in perms_map[uid_str][perm_code]:
					perms_map[uid_str][perm_code].append(gs)

		result = list(grouped.values())
		for ctx in result:
			ctx.permissions = dict(perms_map[str(ctx.user_id)])
		return result
