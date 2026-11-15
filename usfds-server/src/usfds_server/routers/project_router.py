from typing import Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status

from usfds_core.domain.entities.auth import ActorContext, BaseQueryFilter, ProjectActorContext
from usfds_core.domain.entities.enums import ProjectStatus
from usfds_core.domain.entities.system import Project
from usfds_core.services.auth.access_logic import effective_scope
from usfds_core.services.auth.auth_service import AuthService
from usfds_core.services.auth.authz_service import AuthzService
from usfds_core.services.project_management.project_service import ProjectManagementService
from usfds_server.dependencies import get_actor_context, get_auth_service, get_authz_service, get_project_management_service
from usfds_server.schemas.auth_schemas import (
    AddProjectMemberRequest,
    AssignProjectMemberRoleRequest,
    ProjectMemberDto,
    ProjectRoleSummaryDto,
    SetProjectMemberRolesRequest,
)
from usfds_server.schemas.base_response import ApiResponse
from usfds_server.schemas.project_api_schemas import (
    CreateProjectRequest,
    ProjectResponse,
    UpdateProjectRequest,
)

router = APIRouter(prefix="/api/v1/projects", tags=["Project Management"])


def _to_project_response(
    project: Project,
    stats: Optional[Dict[str, int]] = None,
) -> ProjectResponse:
    stats = stats or {}
    status_str = (
        project.status.value
        if hasattr(project.status, "value")
        else str(project.status)
    )
    return ProjectResponse(
        project_id=project.project_id,
        project_name=project.project_name,
        user_id=project.user_id,
        description=project.description,
        status=status_str,
        is_schema_locked=project.is_schema_locked,
        base_dataset_id=project.base_dataset_id,
        raw_schema=project.raw_schema,
        datasets_count=stats.get("datasets_count", 0),
        rules_count=stats.get("rules_count", 0),
        detection_jobs_count=stats.get("detection_jobs_count", 0),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.post(
    "",
    response_model=ApiResponse[ProjectResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new fraud detection project (unlocked RAW schema)",
)
def create_project(
    request: CreateProjectRequest,
    actor: ActorContext = Depends(get_actor_context),
    authz: AuthzService = Depends(get_authz_service),
    service: ProjectManagementService = Depends(get_project_management_service),
) -> ApiResponse[ProjectResponse]:
    authz.require_system_permission(actor, "project:create")
    try:
        project = service.create_project(
            project_name=request.project_name,
            user_id=actor.user_id,
            description=request.description,
        )
        return ApiResponse.ok(
            data=_to_project_response(project),
            status_code=status.HTTP_201_CREATED,
            message=f"Project '{project.project_name}' created successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


def _matches_project_filters(project: Project, filters: List[BaseQueryFilter]) -> bool:
    for qf in filters:
        if project.project_id in qf.project_ids:
            if qf.owner_id is None or project.user_id == qf.owner_id:
                return True
    return False


@router.get(
    "",
    response_model=ApiResponse[List[ProjectResponse]],
    summary="List projects with optional user, status, and search filters",
)
def list_projects(
    user_id: Optional[UUID] = Query(None, description="Filter by owner user ID"),
    project_status: Optional[ProjectStatus] = Query(
        None, alias="status", description="Filter by ACTIVE / ARCHIVED"
    ),
    search: Optional[str] = Query(None, description="Search by project name or description"),
    actor: ActorContext = Depends(get_actor_context),
    authz: AuthzService = Depends(get_authz_service),
    service: ProjectManagementService = Depends(get_project_management_service),
) -> ApiResponse[List[ProjectResponse]]:
    items = service.list_projects(user_id=user_id, status=project_status, search=search)
    if effective_scope(actor, "project:list_all", None) is None:
        filters = authz.can_list(actor, "project:read", [p.project_id for p, _ in items])
        items = [(p, stats) for p, stats in items if _matches_project_filters(p, filters)]
    return ApiResponse.ok(
        data=[_to_project_response(p, stats) for p, stats in items],
        message=f"Retrieved {len(items)} projects",
    )


@router.get(
    "/{project_id}",
    response_model=ApiResponse[ProjectResponse],
    summary="Get project details including locked RAW schema and resource counts",
)
def get_project(
    project_id: UUID,
    actor: ActorContext = Depends(get_actor_context),
    authz: AuthzService = Depends(get_authz_service),
    service: ProjectManagementService = Depends(get_project_management_service),
) -> ApiResponse[ProjectResponse]:
    authz.require_project_permission(actor, "project:read", project_id)
    try:
        project, stats = service.get_project_with_stats(project_id)
        return ApiResponse.ok(
            data=_to_project_response(project, stats),
            message="Project retrieved successfully",
        )
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/{project_id}",
    response_model=ApiResponse[ProjectResponse],
    summary="Update project name, description, or status (ACTIVE / ARCHIVED)",
)
def update_project(
    project_id: UUID,
    request: UpdateProjectRequest,
    actor: ActorContext = Depends(get_actor_context),
    authz: AuthzService = Depends(get_authz_service),
    service: ProjectManagementService = Depends(get_project_management_service),
) -> ApiResponse[ProjectResponse]:
    authz.require_project_permission(actor, "project:update", project_id, action="mutate")
    try:
        project = service.update_project(
            project_id=project_id,
            project_name=request.project_name,
            description=request.description,
            status=request.status,
        )
        _, stats = service.get_project_with_stats(project.project_id)
        return ApiResponse.ok(
            data=_to_project_response(project, stats),
            message=f"Project '{project.project_name}' updated successfully",
        )
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{project_id}/schema/reset",
    response_model=ApiResponse[ProjectResponse],
    summary="Unlock/reset project RAW schema when no dependent resources exist (BR-PM-03)",
)
def reset_project_schema(
    project_id: UUID,
    actor: ActorContext = Depends(get_actor_context),
    authz: AuthzService = Depends(get_authz_service),
    service: ProjectManagementService = Depends(get_project_management_service),
) -> ApiResponse[ProjectResponse]:
    authz.require_project_permission(actor, "project:reset_schema", project_id, action="mutate")
    try:
        project = service.reset_project_schema(project_id)
        _, stats = service.get_project_with_stats(project.project_id)
        return ApiResponse.ok(
            data=_to_project_response(project, stats),
            message="Project RAW schema reset and unlocked successfully",
        )
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/{project_id}",
    response_model=ApiResponse[bool],
    summary="Delete a project and cascade clean its resources (BR-PM-08)",
)
def delete_project(
    project_id: UUID,
    actor: ActorContext = Depends(get_actor_context),
    authz: AuthzService = Depends(get_authz_service),
    service: ProjectManagementService = Depends(get_project_management_service),
) -> ApiResponse[bool]:
    authz.require_project_permission(actor, "project:delete", project_id, action="mutate")
    try:
        deleted = service.delete_project(project_id)
        return ApiResponse.ok(
            data=deleted,
            message=f"Project '{project_id}' deleted successfully",
        )
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


def _to_member_actor_dto(ctx: ProjectActorContext) -> ProjectMemberDto:
    return ProjectMemberDto(
        project_id=ctx.project_id,
        user_id=ctx.user_id,
        username=ctx.username,
        full_name=ctx.full_name,
        email=ctx.email,
        status=ctx.status.value if hasattr(ctx.status, "value") else str(ctx.status),
        roles=[
            ProjectRoleSummaryDto(
                role_id=r.role_id,
                name=r.name,
                display_name=r.display_name,
            )
            for r in ctx.roles
        ],
        role_keys=list(ctx.role_keys),
        permissions={
            k: [s.value if hasattr(s, "value") else str(s) for s in v]
            for k, v in ctx.permissions.items()
        },
        added_by=ctx.added_by,
        created_at=ctx.created_at,
    )


def _load_single_member_dto(authz: AuthzService, project_id: UUID, user_id: UUID) -> ProjectMemberDto:
    items = authz.member_repo.load_project_actor_context(project_id, user_id=user_id)
    if not items:
        raise ValueError(f"Member {user_id} not found in project {project_id}")
    return _to_member_actor_dto(items[0])


@router.get(
    "/{project_id}/members",
    response_model=ApiResponse[List[ProjectMemberDto]],
    summary="List members and their project-level actor context in a project",
)
def list_project_members(
    project_id: UUID,
    actor: ActorContext = Depends(get_actor_context),
    authz: AuthzService = Depends(get_authz_service),
) -> ApiResponse[List[ProjectMemberDto]]:
    members = authz.list_project_members(actor, project_id)
    return ApiResponse.ok(
        data=[_to_member_actor_dto(m) for m in members],
        message="Project members retrieved",
    )


@router.post(
    "/{project_id}/members",
    response_model=ApiResponse[ProjectMemberDto],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user (system_member) or attach an existing user to the project",
)
def add_project_member(
    project_id: UUID,
    request: AddProjectMemberRequest,
    actor: ActorContext = Depends(get_actor_context),
    auth_service: AuthService = Depends(get_auth_service),
    authz: AuthzService = Depends(get_authz_service),
) -> ApiResponse[ProjectMemberDto]:
    authz.require_project_permission(actor, "project_member:manage", project_id, action="mutate")
    try:
        if request.user_id is not None:
            authz.add_project_member(actor, project_id, request.user_id, request.role_id)
            return ApiResponse.ok(
                data=_load_single_member_dto(authz, project_id, request.user_id),
                message="Member added",
                status_code=201,
            )

        if not request.username or not request.password:
            raise ValueError("Either user_id or username + password is required")

        role = authz.role_repo.get_by_id(request.role_id)
        if role is None:
            raise ValueError(f"Role {request.role_id} not found")
        from usfds_core.domain.entities.auth import PermissionDeniedError
        from usfds_core.domain.entities.enums import RoleScope
        from usfds_core.services.auth.access_logic import delegation_refusal

        if role.scope != RoleScope.PROJECT:
            raise PermissionDeniedError(f"Role {role.name} is not a PROJECT role")
        grants = authz._resolve_role_grants(role.role_id)
        refusal = delegation_refusal(
            actor=actor,
            caller_project_ids=[p.project_id for p in actor.projects],
            project_id=project_id,
            role_name=role.name,
            role_scope=role.scope,
            grants=grants,
        )
        if refusal:
            raise PermissionDeniedError(refusal)

        user = auth_service.create_user(
            username=request.username,
            password=request.password,
            email=request.email,
            full_name=request.full_name,
            system_role_names=["system_member"],
            assigned_by=actor.user_id,
        )
        authz.add_project_member(actor, project_id, user.user_id, request.role_id)
        return ApiResponse.ok(
            data=_load_single_member_dto(authz, project_id, user.user_id),
            message="Member created",
            status_code=201,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/{project_id}/members/{user_id}",
    response_model=ApiResponse[int],
    summary="Remove a member completely from the project",
)
def remove_project_member_user(
    project_id: UUID,
    user_id: UUID,
    actor: ActorContext = Depends(get_actor_context),
    authz: AuthzService = Depends(get_authz_service),
) -> ApiResponse[int]:
    try:
        removed_count = authz.remove_user_from_project(actor, project_id, user_id)
        return ApiResponse.ok(data=removed_count, message="Member removed from project")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{project_id}/members/{user_id}/roles",
    response_model=ApiResponse[ProjectMemberDto],
    status_code=status.HTTP_201_CREATED,
    summary="Assign an additional role to a project member",
)
def assign_project_member_role(
    project_id: UUID,
    user_id: UUID,
    request: AssignProjectMemberRoleRequest,
    actor: ActorContext = Depends(get_actor_context),
    authz: AuthzService = Depends(get_authz_service),
) -> ApiResponse[ProjectMemberDto]:
    try:
        authz.add_project_member(actor, project_id, user_id, request.role_id)
        return ApiResponse.ok(
            data=_load_single_member_dto(authz, project_id, user_id),
            message="Role assigned",
            status_code=201,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put(
    "/{project_id}/members/{user_id}/roles",
    response_model=ApiResponse[ProjectMemberDto],
    summary="Replace all roles of a project member",
)
def set_project_member_roles(
    project_id: UUID,
    user_id: UUID,
    request: SetProjectMemberRolesRequest,
    actor: ActorContext = Depends(get_actor_context),
    authz: AuthzService = Depends(get_authz_service),
) -> ApiResponse[ProjectMemberDto]:
    try:
        authz.set_project_member_roles(actor, project_id, user_id, request.role_ids)
        return ApiResponse.ok(
            data=_load_single_member_dto(authz, project_id, user_id),
            message="Member roles updated",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/{project_id}/members/{user_id}/roles/{role_id}",
    response_model=ApiResponse[bool],
    summary="Revoke a specific role from a project member",
)
def remove_project_member(
    project_id: UUID,
    user_id: UUID,
    role_id: UUID,
    actor: ActorContext = Depends(get_actor_context),
    authz: AuthzService = Depends(get_authz_service),
) -> ApiResponse[bool]:
    try:
        removed = authz.remove_project_member(actor, project_id, user_id, role_id)
        return ApiResponse.ok(data=removed, message="Member role removed")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


__all__ = ["router"]
