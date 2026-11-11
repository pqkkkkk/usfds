from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from usfds_core.services.insight_report.service import InsightReportService
from usfds_core.storage.base_storage import IFileStorage
from usfds_server.dependencies import get_insight_report_service, get_storage
from usfds_server.schemas.base_response import ApiResponse

router = APIRouter(prefix="/api/v1/reports", tags=["Insight & Report"])


def _parse_job_ids(job_ids_csv: Optional[str]) -> Optional[list[UUID]]:
	if not job_ids_csv or not job_ids_csv.strip():
		return None
	result: list[UUID] = []
	for token in job_ids_csv.split(","):
		clean = token.strip()
		if not clean:
			continue
		try:
			result.append(UUID(clean))
		except ValueError as err:
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail=f"Invalid job_id UUID '{clean}' in job_ids filter.",
			) from err
	return result or None


def _handle_service_error(err: Exception) -> None:
	if isinstance(err, LookupError):
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
	if isinstance(err, ValueError):
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err
	raise err


@router.get(
	"/overview",
	response_model=ApiResponse[dict[str, Any]],
	summary="SUC-22: Executive Financial & Case Operations Dashboard",
)
def get_executive_overview(
	project_id: UUID = Query(..., description="Active Project ID"),
	job_ids: Optional[str] = Query(None, description="Comma-separated DetectionJob IDs filter"),
	date_from: Optional[datetime] = Query(None, description="Optional ISO start timestamp"),
	date_to: Optional[datetime] = Query(None, description="Optional ISO end timestamp"),
	label_source: Literal["VERIFIED_ONLY", "VERIFIED_WITH_DATASET_FALLBACK"] = Query(
		"VERIFIED_WITH_DATASET_FALLBACK",
		description="Ground-truth label source mode (BR-IR-02)",
	),
	service: InsightReportService = Depends(get_insight_report_service),
) -> ApiResponse[dict[str, Any]]:
	try:
		parsed_jobs = _parse_job_ids(job_ids)
		data = service.get_executive_overview(
			project_id=project_id,
			job_ids=parsed_jobs,
			date_from=date_from,
			date_to=date_to,
			label_source=label_source,
		)
		return ApiResponse.ok(data=data, message="Executive overview computed successfully")
	except (LookupError, ValueError) as err:
		_handle_service_error(err)


@router.get(
	"/effectiveness",
	response_model=ApiResponse[dict[str, Any]],
	summary="SUC-23: Rule & Model Ground-Truth Performance Analysis",
)
def get_effectiveness_analysis(
	project_id: UUID = Query(..., description="Active Project ID"),
	job_ids: Optional[str] = Query(None, description="Comma-separated DetectionJob IDs filter"),
	model_version_id: Optional[UUID] = Query(None, description="Optional ModelVersion ID filter"),
	date_from: Optional[datetime] = Query(None, description="Optional ISO start timestamp"),
	date_to: Optional[datetime] = Query(None, description="Optional ISO end timestamp"),
	label_source: Literal["VERIFIED_ONLY", "VERIFIED_WITH_DATASET_FALLBACK"] = Query(
		"VERIFIED_WITH_DATASET_FALLBACK",
		description="Ground-truth label source mode (BR-IR-02)",
	),
	service: InsightReportService = Depends(get_insight_report_service),
) -> ApiResponse[dict[str, Any]]:
	try:
		parsed_jobs = _parse_job_ids(job_ids)
		data = service.get_effectiveness_analysis(
			project_id=project_id,
			job_ids=parsed_jobs,
			model_version_id=model_version_id,
			date_from=date_from,
			date_to=date_to,
			label_source=label_source,
		)
		return ApiResponse.ok(data=data, message="Rule & Model effectiveness computed successfully")
	except (LookupError, ValueError) as err:
		_handle_service_error(err)


@router.get(
	"/patterns",
	response_model=ApiResponse[dict[str, Any]],
	summary="SUC-24: Fraud Typologies & Temporal-Behavioral Patterns",
)
def get_typology_and_patterns(
	project_id: UUID = Query(..., description="Active Project ID"),
	job_ids: Optional[str] = Query(None, description="Comma-separated DetectionJob IDs filter"),
	date_from: Optional[datetime] = Query(None, description="Optional ISO start timestamp"),
	date_to: Optional[datetime] = Query(None, description="Optional ISO end timestamp"),
	label_source: Literal["VERIFIED_ONLY", "VERIFIED_WITH_DATASET_FALLBACK"] = Query(
		"VERIFIED_WITH_DATASET_FALLBACK",
		description="Ground-truth label source mode (BR-IR-02)",
	),
	service: InsightReportService = Depends(get_insight_report_service),
) -> ApiResponse[dict[str, Any]]:
	try:
		parsed_jobs = _parse_job_ids(job_ids)
		data = service.get_typology_and_patterns(
			project_id=project_id,
			job_ids=parsed_jobs,
			date_from=date_from,
			date_to=date_to,
			label_source=label_source,
		)
		return ApiResponse.ok(data=data, message="Fraud typologies and patterns computed successfully")
	except (LookupError, ValueError) as err:
		_handle_service_error(err)


@router.get(
	"/sar/{case_id}",
	response_model=ApiResponse[dict[str, Any]],
	summary="SUC-25: Generate 5-section SAR Dossier preview for a Case (BR-IR-03)",
)
def get_sar_dossier(
	case_id: UUID,
	project_id: UUID = Query(..., description="Active Project ID"),
	prepared_by: str = Query("local-analyst", description="Name/ID of report preparer"),
	reviewer_notes: str = Query("", description="Optional compliance reviewer notes"),
	service: InsightReportService = Depends(get_insight_report_service),
) -> ApiResponse[dict[str, Any]]:
	try:
		data = service.generate_sar_dossier(
			project_id=project_id,
			case_id=case_id,
			prepared_by=prepared_by,
			reviewer_notes=reviewer_notes,
		)
		return ApiResponse.ok(data=data, message="SAR Dossier generated successfully")
	except (LookupError, ValueError) as err:
		_handle_service_error(err)


@router.get(
	"/executive-summary",
	response_model=ApiResponse[dict[str, Any]],
	summary="SUC-25: Generate Executive Fraud & Policy Audit Report preview",
)
def get_executive_audit_report(
	project_id: UUID = Query(..., description="Active Project ID"),
	job_ids: Optional[str] = Query(None, description="Comma-separated DetectionJob IDs filter"),
	date_from: Optional[datetime] = Query(None, description="Optional ISO start timestamp"),
	date_to: Optional[datetime] = Query(None, description="Optional ISO end timestamp"),
	label_source: Literal["VERIFIED_ONLY", "VERIFIED_WITH_DATASET_FALLBACK"] = Query(
		"VERIFIED_WITH_DATASET_FALLBACK",
	),
	prepared_by: str = Query("local-analyst", description="Name/ID of report preparer"),
	reviewer_notes: str = Query("", description="Optional compliance reviewer notes"),
	service: InsightReportService = Depends(get_insight_report_service),
) -> ApiResponse[dict[str, Any]]:
	try:
		parsed_jobs = _parse_job_ids(job_ids)
		data = service.generate_executive_audit_report(
			project_id=project_id,
			job_ids=parsed_jobs,
			date_from=date_from,
			date_to=date_to,
			label_source=label_source,
			prepared_by=prepared_by,
			reviewer_notes=reviewer_notes,
		)
		return ApiResponse.ok(data=data, message="Executive Audit Report generated successfully")
	except (LookupError, ValueError) as err:
		_handle_service_error(err)


@router.get(
	"/export",
	summary="SUC-25: Download SAR Dossier or Executive Audit Report (.md, .json, .csv, .html)",
)
def export_compliance_report(
	project_id: UUID = Query(..., description="Active Project ID"),
	report_type: Literal["sar", "executive"] = Query(..., description="Report template: sar | executive"),
	file_format: Literal["md", "json", "csv", "html"] = Query("md", description="Output file format"),
	case_id: Optional[UUID] = Query(None, description="Case ID (required when report_type == 'sar')"),
	job_ids: Optional[str] = Query(None, description="Comma-separated DetectionJob IDs filter"),
	date_from: Optional[datetime] = Query(None),
	date_to: Optional[datetime] = Query(None),
	label_source: Literal["VERIFIED_ONLY", "VERIFIED_WITH_DATASET_FALLBACK"] = Query(
		"VERIFIED_WITH_DATASET_FALLBACK",
	),
	prepared_by: str = Query("local-analyst"),
	reviewer_notes: str = Query(""),
	presigned: bool = Query(False, description="Return a presigned download URL when backed by S3"),
	service: InsightReportService = Depends(get_insight_report_service),
	storage: IFileStorage = Depends(get_storage),
) -> Any:
	try:
		parsed_jobs = _parse_job_ids(job_ids)
		file_bytes, filename, media_type = service.export_report(
			project_id=project_id,
			report_type=report_type,
			file_format=file_format,
			case_id=case_id,
			job_ids=parsed_jobs,
			date_from=date_from,
			date_to=date_to,
			label_source=label_source,
			prepared_by=prepared_by,
			reviewer_notes=reviewer_notes,
		)
		if presigned:
			export_key = f"exports/reports/{project_id}/{filename}"
			storage.save_bytes(export_key, file_bytes)
			dl_url = storage.generate_presigned_download_url(export_key, filename=filename)
			if dl_url:
				return ApiResponse.ok(
					data={"download_url": dl_url, "filename": filename, "object_key": export_key},
					message="Compliance report export ready",
				)
		return Response(
			content=file_bytes,
			media_type=media_type,
			headers={"Content-Disposition": f'attachment; filename="{filename}"'},
		)
	except (LookupError, ValueError) as err:
		_handle_service_error(err)


__all__ = ["router"]
