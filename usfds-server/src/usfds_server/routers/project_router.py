from typing import Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status

from usfds_core.domain.entities.enums import ProjectStatus
from usfds_core.domain.entities.system import Project
from usfds_core.services.project_management.project_service import ProjectManagementService
from usfds_server.dependencies import get_project_management_service
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
    service: ProjectManagementService = Depends(get_project_management_service),
) -> ApiResponse[ProjectResponse]:
    try:
        project = service.create_project(
            project_name=request.project_name,
            user_id=request.user_id,
            description=request.description,
        )
        return ApiResponse.ok(
            data=_to_project_response(project),
            status_code=status.HTTP_201_CREATED,
            message=f"Project '{project.project_name}' created successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


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
    service: ProjectManagementService = Depends(get_project_management_service),
) -> ApiResponse[List[ProjectResponse]]:
    items = service.list_projects(user_id=user_id, status=project_status, search=search)
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
    service: ProjectManagementService = Depends(get_project_management_service),
) -> ApiResponse[ProjectResponse]:
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
    service: ProjectManagementService = Depends(get_project_management_service),
) -> ApiResponse[ProjectResponse]:
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
    service: ProjectManagementService = Depends(get_project_management_service),
) -> ApiResponse[ProjectResponse]:
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
    service: ProjectManagementService = Depends(get_project_management_service),
) -> ApiResponse[bool]:
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


__all__ = ["router"]
