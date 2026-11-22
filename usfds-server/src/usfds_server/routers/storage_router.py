from pathlib import Path
from typing import Literal, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from usfds_core.domain.entities.auth import ActorContext, PermissionDeniedError
from usfds_core.storage.base_storage import IFileStorage
from usfds_core.services.auth.authz_service import AuthzService
from usfds_infra.database import SqliteDatasetRepository, SqliteDetectionJobRepository
from usfds_server.dependencies import (
	get_actor_context,
	get_authz_service,
	get_dataset_repo,
	get_detection_job_repo,
	get_storage,
)
from usfds_server.schemas.base_response import ApiResponse

router = APIRouter(prefix="/api/v1/storage", tags=["Storage"])

ALLOWED_EXTENSIONS_BY_PURPOSE: dict[str, set[str]] = {
	"dataset_raw": {".csv", ".parquet", ".pq", ".json", ".txt"},
	"detection_input": {".csv", ".parquet", ".pq", ".json"},
	"model_plugin": {".zip"},
}


class PresignedUploadRequest(BaseModel):
	filename: str = Field(..., min_length=1, description="Original file name with extension")
	purpose: Literal["dataset_raw", "detection_input", "model_plugin"] = Field(
		"dataset_raw",
		description="Upload target category used for extension validation and key prefixing",
	)
	project_id: Optional[UUID] = Field(None, description="Optional active project ID")
	content_type: Optional[str] = Field(None, description="Optional MIME Content-Type header for PUT request")
	expires_in: int = Field(900, ge=60, le=86400, description="URL expiration time in seconds")


class PresignedUploadResponse(BaseModel):
	upload_url: str
	object_key: str
	expires_in: int


class PresignedDownloadResponse(BaseModel):
	download_url: str
	object_key: str
	filename: str
	expires_in: int


@router.post(
	"/presigned-upload",
	response_model=ApiResponse[PresignedUploadResponse],
	status_code=status.HTTP_200_OK,
	summary="Generate an S3 presigned PUT URL for direct client-to-storage upload",
)
def create_presigned_upload_url(
	req: PresignedUploadRequest,
	actor: ActorContext = Depends(get_actor_context),
	authz: AuthzService = Depends(get_authz_service),
	storage: IFileStorage = Depends(get_storage),
) -> ApiResponse[PresignedUploadResponse]:
	if req.purpose in ("dataset_raw", "detection_input"):
		if req.project_id is None:
			if not actor.is_system_admin:
				raise HTTPException(
					status_code=status.HTTP_400_BAD_REQUEST,
					detail=f"project_id is required for purpose '{req.purpose}'.",
				)
		else:
			perm = "dataset:create" if req.purpose == "dataset_raw" else "detection:create"
			authz.require_project_permission(actor, perm, req.project_id, action="create")
	elif req.project_id is not None:
		authz.require_project_permission(actor, "model:create", req.project_id, action="create")
	elif not actor.is_system_admin:
		raise PermissionDeniedError("System admin permission required for global model plugin upload")
	safe_name = Path(req.filename.strip()).name
	if not safe_name:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename.")

	ext = Path(safe_name).suffix.lower()
	allowed = ALLOWED_EXTENSIONS_BY_PURPOSE.get(req.purpose, set())
	if allowed and ext not in allowed:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=f"Unsupported file format '{ext}' for purpose '{req.purpose}'. Allowed: {sorted(allowed)}",
		)

	scope = str(req.project_id) if req.project_id else "global"
	object_key = f"uploads/{req.purpose}/{scope}/{uuid4()}/{safe_name}"
	upload_url = storage.generate_presigned_upload_url(
		file_path=object_key,
		content_type=req.content_type,
		expires_in=req.expires_in,
	)
	if not upload_url:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Active storage backend does not support presigned URLs.",
		)

	return ApiResponse.ok(
		data=PresignedUploadResponse(
			upload_url=upload_url,
			object_key=object_key,
			expires_in=req.expires_in,
		),
		message="Presigned upload URL generated successfully",
	)


def _authorize_download_key(
	actor: ActorContext,
	authz: AuthzService,
	project_id: UUID,
	raw_key: str,
	dataset_repo: SqliteDatasetRepository,
	detection_job_repo: SqliteDetectionJobRepository,
) -> str:
	if "\\" in raw_key:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid object_key.")
	clean_key = raw_key.strip().lstrip("/")
	parts = [p for p in clean_key.split("/") if p]
	if not parts or ".." in parts:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid object_key.")

	prefix = parts[0]
	if prefix == "uploads" and len(parts) >= 3:
		purpose_perms = {
			"dataset_raw": "dataset:read",
			"detection_input": "detection:read",
			"model_plugin": "model:read",
		}
		perm = purpose_perms.get(parts[1])
		if perm is None:
			authz.require_project_permission(actor, "project:read", project_id)
			raise PermissionDeniedError("Cannot verify project ownership for object key")
		authz.require_project_permission(actor, perm, project_id)
		if parts[2] != str(project_id):
			raise PermissionDeniedError("Object key does not belong to the specified project")
		return clean_key

	if prefix == "exports" and len(parts) >= 3:
		kind = parts[1]
		if kind == "reports":
			authz.require_project_permission(actor, "report:export", project_id)
			if parts[2] != str(project_id):
				raise PermissionDeniedError("Object key does not belong to the specified project")
			return clean_key
		if kind == "datasets":
			authz.require_project_scope(actor, "dataset:export", project_id)
			try:
				ds_id = UUID(parts[2])
			except ValueError as err:
				raise PermissionDeniedError("Cannot verify project ownership for object key") from err
			ds = dataset_repo.get_by_id(ds_id)
			if ds is None or ds.project_id != project_id:
				raise PermissionDeniedError("Object key does not belong to the specified project")
			authz.require_project_permission(actor, "dataset:export", project_id, owner_id=ds.user_id)
			return clean_key
		if kind == "detection":
			authz.require_project_scope(actor, "detection:export", project_id)
			try:
				job_id = UUID(parts[2])
			except ValueError as err:
				raise PermissionDeniedError("Cannot verify project ownership for object key") from err
			job = detection_job_repo.get_by_id(job_id)
			if job is None or job.project_id != project_id:
				raise PermissionDeniedError("Object key does not belong to the specified project")
			authz.require_project_permission(actor, "detection:export", project_id, owner_id=job.user_id)
			return clean_key

	if prefix == "datasets" and len(parts) >= 2:
		if len(parts) >= 3 and parts[2] == "inferences":
			authz.require_project_scope(actor, "detection:export", project_id)
			if parts[1] != str(project_id):
				raise PermissionDeniedError("Object key does not belong to the specified project")
			if len(parts) >= 4:
				try:
					job_id = UUID(parts[3])
					job = detection_job_repo.get_by_id(job_id)
				except ValueError:
					job = None
				if job is not None and job.project_id == project_id:
					authz.require_project_permission(actor, "detection:export", project_id, owner_id=job.user_id)
					return clean_key
			authz.require_project_permission(actor, "detection:export", project_id)
			return clean_key
		authz.require_project_scope(actor, "dataset:export", project_id)
		try:
			ds_id = UUID(parts[1])
		except ValueError as err:
			raise PermissionDeniedError("Cannot verify project ownership for object key") from err
		ds = dataset_repo.get_by_id(ds_id)
		if ds is None or ds.project_id != project_id:
			raise PermissionDeniedError("Object key does not belong to the specified project")
		authz.require_project_permission(actor, "dataset:export", project_id, owner_id=ds.user_id)
		return clean_key

	authz.require_project_permission(actor, "project:read", project_id)
	raise PermissionDeniedError("Cannot verify project ownership for object key")


@router.get(
	"/presigned-download",
	response_model=ApiResponse[PresignedDownloadResponse],
	status_code=status.HTTP_200_OK,
	summary="Generate an S3 presigned GET URL for direct client download",
)
def create_presigned_download_url(
	object_key: str = Query(..., min_length=1, description="Storage object key"),
	project_id: UUID = Query(..., description="Project ID"),
	filename: Optional[str] = Query(None, description="Optional attachment filename"),
	expires_in: int = Query(900, ge=60, le=86400, description="URL expiration time in seconds"),
	actor: ActorContext = Depends(get_actor_context),
	authz: AuthzService = Depends(get_authz_service),
	storage: IFileStorage = Depends(get_storage),
	dataset_repo: SqliteDatasetRepository = Depends(get_dataset_repo),
	detection_job_repo: SqliteDetectionJobRepository = Depends(get_detection_job_repo),
) -> ApiResponse[PresignedDownloadResponse]:
	clean_key = _authorize_download_key(
		actor=actor,
		authz=authz,
		project_id=project_id,
		raw_key=object_key,
		dataset_repo=dataset_repo,
		detection_job_repo=detection_job_repo,
	)
	resolved_name = Path(filename.strip()).name if filename and filename.strip() else Path(clean_key).name
	try:
		download_url = storage.generate_presigned_download_url(
			file_path=clean_key,
			filename=resolved_name,
			expires_in=expires_in,
		)
	except FileNotFoundError as e:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

	if not download_url:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Active storage backend does not support presigned URLs.",
		)

	return ApiResponse.ok(
		data=PresignedDownloadResponse(
			download_url=download_url,
			object_key=clean_key,
			filename=resolved_name,
			expires_in=expires_in,
		),
		message="Presigned download URL generated successfully",
	)


__all__ = ["router"]

