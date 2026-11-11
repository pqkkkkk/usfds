from pathlib import Path
from typing import Literal, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from usfds_core.storage.base_storage import IFileStorage
from usfds_server.dependencies import get_storage
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
	storage: IFileStorage = Depends(get_storage),
) -> ApiResponse[PresignedUploadResponse]:
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


@router.get(
	"/presigned-download",
	response_model=ApiResponse[PresignedDownloadResponse],
	status_code=status.HTTP_200_OK,
	summary="Generate an S3 presigned GET URL for direct client download",
)
def create_presigned_download_url(
	object_key: str = Query(..., min_length=1, description="Storage object key"),
	filename: Optional[str] = Query(None, description="Optional attachment filename"),
	expires_in: int = Query(900, ge=60, le=86400, description="URL expiration time in seconds"),
	storage: IFileStorage = Depends(get_storage),
) -> ApiResponse[PresignedDownloadResponse]:
	clean_key = object_key.strip().lstrip("/")
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

