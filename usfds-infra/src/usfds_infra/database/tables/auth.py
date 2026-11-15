"""ORM tables for the `auth` domain (users, sessions, roles, permissions, memberships)."""
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from usfds_infra.database.base import Base, TimestampMixin


class UserModel(Base, TimestampMixin):
	"""SQLAlchemy model for system users."""
	__tablename__ = "users"

	user_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
	username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
	email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True, index=True)
	full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
	password_hash: Mapped[str] = mapped_column(String(255), nullable=False, default="")
	status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE", index=True)
	last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class UserSessionModel(Base):
	"""SQLAlchemy model for refresh-token user sessions."""
	__tablename__ = "user_sessions"

	session_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
	user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
	refresh_token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
	expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
	revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
	user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
	ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class RoleModel(Base, TimestampMixin):
	"""SQLAlchemy model for RBAC roles (SYSTEM or PROJECT scope)."""
	__tablename__ = "roles"

	role_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
	name: Mapped[str] = mapped_column(String(100), nullable=False)
	display_name: Mapped[str] = mapped_column(String(150), nullable=False)
	scope: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
	is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
	description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

	__table_args__ = (
		UniqueConstraint("scope", "name", name="uq_roles_scope_name"),
	)


class PermissionModel(Base):
	"""SQLAlchemy model for normalized resource:action permission catalog."""
	__tablename__ = "permissions"

	permission_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
	code: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
	resource: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
	action: Mapped[str] = mapped_column(String(100), nullable=False)
	scope: Mapped[str] = mapped_column(String(32), nullable=False)
	description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class RolePermissionModel(Base):
	"""SQLAlchemy model mapping roles to permissions with a grant scope (OWN | PROJECT | SYSTEM)."""
	__tablename__ = "role_permissions"

	role_id: Mapped[str] = mapped_column(String(36), ForeignKey("roles.role_id", ondelete="CASCADE"), primary_key=True)
	permission_id: Mapped[str] = mapped_column(String(36), ForeignKey("permissions.permission_id", ondelete="CASCADE"), primary_key=True)
	grant_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="PROJECT")


class SystemUserRoleModel(Base):
	"""SQLAlchemy model assigning SYSTEM-scoped roles to users."""
	__tablename__ = "system_user_roles"

	user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
	role_id: Mapped[str] = mapped_column(String(36), ForeignKey("roles.role_id", ondelete="CASCADE"), primary_key=True)
	assigned_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ProjectMemberModel(Base, TimestampMixin):
	"""SQLAlchemy model assigning PROJECT-scoped roles to users within a project (supports multiple roles per user)."""
	__tablename__ = "project_members"

	project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.project_id", ondelete="CASCADE"), primary_key=True)
	user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
	role_id: Mapped[str] = mapped_column(String(36), ForeignKey("roles.role_id", ondelete="CASCADE"), primary_key=True)
	added_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
