"""System Column Metadata Management endpoints (/api/v1/system-metadata)."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from usfds_core.domain.entities.auth import ActorContext
from usfds_core.domain.entities.system_metadata import SystemColumnMetadata
from usfds_core.services.data_management.system_metadata_service import SystemMetadataService
from usfds_server.providers.auth import get_actor_context, require_system_permission
from usfds_server.providers.data import get_system_metadata_service
from usfds_server.schemas.base_response import ApiResponse
from usfds_server.schemas.system_metadata_api_schemas import (
	CreateSystemColumnRequest,
	SystemColumnMetadataResponse,
	UpdateSystemColumnRequest,
)

router = APIRouter(prefix="/api/v1/system-metadata", tags=["System Metadata"])


def _to_response(entity: SystemColumnMetadata) -> SystemColumnMetadataResponse:
	return SystemColumnMetadataResponse(
		metadata_id=entity.metadata_id,
		column_key=entity.column_key,
		display_name=entity.display_name,
		category=entity.category.value if hasattr(entity.category, "value") else str(entity.category),
		logical_type=entity.logical_type.value if hasattr(entity.logical_type, "value") else str(entity.logical_type),
		is_required=bool(entity.is_required),
		ml_role=entity.ml_role.value if hasattr(entity.ml_role, "value") else str(entity.ml_role),
		aliases=list(entity.aliases or []),
		description=entity.description,
		is_active=bool(entity.is_active),
		display_order=int(entity.display_order),
		created_at=entity.created_at,
		updated_at=entity.updated_at,
	)


@router.get(
	"/columns",
	response_model=ApiResponse[List[SystemColumnMetadataResponse]],
	summary="List canonical system and domain column metadata",
)
def list_system_columns(
	include_inactive: bool = Query(False, description="Include inactive DOMAIN columns"),
	_actor: ActorContext = Depends(get_actor_context),
	service: SystemMetadataService = Depends(get_system_metadata_service),
) -> ApiResponse[List[SystemColumnMetadataResponse]]:
	columns = service.list_columns(include_inactive=include_inactive)
	return ApiResponse.ok(
		data=[_to_response(c) for c in columns],
		message="System column metadata retrieved successfully",
	)


@router.post(
	"/columns",
	response_model=ApiResponse[SystemColumnMetadataResponse],
	status_code=status.HTTP_201_CREATED,
	summary="Create a new DOMAIN column metadata definition",
)
def create_system_column(
	request: CreateSystemColumnRequest,
	_actor: ActorContext = Depends(require_system_permission("system_metadata:manage")),
	service: SystemMetadataService = Depends(get_system_metadata_service),
) -> ApiResponse[SystemColumnMetadataResponse]:
	try:
		created = service.create_column(
			column_key=request.column_key,
			display_name=request.display_name,
			logical_type=request.logical_type,
			is_required=request.is_required,
			ml_role=request.ml_role,
			aliases=request.aliases,
			description=request.description,
			is_active=request.is_active,
			display_order=request.display_order,
		)
		return ApiResponse.ok(
			data=_to_response(created),
			status_code=status.HTTP_201_CREATED,
			message="System column metadata created successfully",
		)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.patch(
	"/columns/{metadata_id}",
	response_model=ApiResponse[SystemColumnMetadataResponse],
	summary="Update a system or domain column metadata definition",
)
def update_system_column(
	metadata_id: UUID,
	request: UpdateSystemColumnRequest,
	_actor: ActorContext = Depends(require_system_permission("system_metadata:manage")),
	service: SystemMetadataService = Depends(get_system_metadata_service),
) -> ApiResponse[SystemColumnMetadataResponse]:
	try:
		updated = service.update_column(
			metadata_id=metadata_id,
			column_key=request.column_key,
			display_name=request.display_name,
			logical_type=request.logical_type,
			is_required=request.is_required,
			ml_role=request.ml_role,
			aliases=request.aliases,
			description=request.description,
			is_active=request.is_active,
			display_order=request.display_order,
		)
		return ApiResponse.ok(
			data=_to_response(updated),
			message="System column metadata updated successfully",
		)
	except LookupError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete(
	"/columns/{metadata_id}",
	response_model=ApiResponse[None],
	summary="Delete a DOMAIN column metadata definition (CORE columns cannot be deleted)",
)
def delete_system_column(
	metadata_id: UUID,
	_actor: ActorContext = Depends(require_system_permission("system_metadata:manage")),
	service: SystemMetadataService = Depends(get_system_metadata_service),
) -> ApiResponse[None]:
	try:
		service.delete_column(metadata_id)
		return ApiResponse.ok(
			data=None,
			message="System column metadata deleted successfully",
		)
	except LookupError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
