from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from usfds_core.domain.entities.detection import DetectionJob
from usfds_core.domain.entities.enums import InvestigationStatus
from usfds_core.domain.entities.investigation import InvestigationCase
from usfds_core.services.inference.inference_service import InferenceService
from usfds_server.dependencies import get_inference_service
from usfds_server.schemas.base_response import ApiResponse
from usfds_server.schemas.detection_api_schemas import (
	DetectionJobResponse,
	DetectionJobResultsResponse,
	DetectionTransactionRecordResponse,
	InvestigationCaseResponse,
	SendToInvestigationRequest,
	StartDetectionJobRequest,
	TriggeredRuleDetailResponse,
)

router = APIRouter(prefix="/api/v1/detection", tags=["Detection & Inference"])


def _to_job_response(job: DetectionJob) -> DetectionJobResponse:
	status_str = (
		job.status.value
		if hasattr(job.status, "value")
		else str(job.status)
	)
	return DetectionJobResponse(
		job_id=job.job_id,
		project_id=job.project_id,
		deployment_id=job.deployment_id,
		target_artifact_id=job.target_artifact_id,
		model_version_id=job.model_version_id,
		job_name=job.job_name,
		input_path=job.input_path,
		output_path=job.output_path,
		score_threshold=job.score_threshold,
		use_rules=job.use_rules,
		status=status_str,
		total_records=job.total_records,
		fraud_records=job.fraud_records,
		fraud_rate=job.fraud_rate,
		summary_metrics=job.summary_metrics,
		execution_time_seconds=job.execution_time_seconds,
		error_message=job.error_message,
		created_by=job.created_by,
		created_at=job.created_at,
		started_at=job.started_at,
		completed_at=job.completed_at,
	)


def _to_case_response(case: InvestigationCase) -> InvestigationCaseResponse:
	status_str = (
		case.status.value
		if hasattr(case.status, "value")
		else str(case.status)
	)
	risk_str = (
		case.risk_level.value
		if hasattr(case.risk_level, "value")
		else str(case.risk_level)
	)
	return InvestigationCaseResponse(
		case_id=case.case_id,
		project_id=case.project_id,
		event_id=case.event_id,
		assigned_to=case.assigned_to,
		status=status_str,
		risk_level=risk_str,
		fraud_probability=case.fraud_probability,
		analyst_notes=case.analyst_notes,
		action_taken=case.action_taken,
		sar_narrative=case.sar_narrative,
		metadata=case.metadata or {},
		created_at=case.created_at,
		updated_at=case.updated_at,
		resolved_at=case.resolved_at,
	)


@router.get(
	"/jobs",
	response_model=ApiResponse[List[DetectionJobResponse]],
	summary="List batch detection jobs for a project (SUC-19)",
)
def list_detection_jobs(
	project_id: UUID = Query(..., description="Project ID to query detection jobs for"),
	job_status: Optional[str] = Query(None, alias="status", description="Optional status filter"),
	service: InferenceService = Depends(get_inference_service),
) -> ApiResponse[List[DetectionJobResponse]]:
	jobs = service.list_detection_jobs(project_id=project_id, status=job_status)
	return ApiResponse.ok(
		data=[_to_job_response(j) for j in jobs],
		message=f"Retrieved {len(jobs)} detection jobs",
	)


@router.post(
	"/jobs",
	response_model=ApiResponse[DetectionJobResponse],
	status_code=status.HTTP_201_CREATED,
	summary="Start a hybrid batch detection job on a RAW artifact or direct file path (SUC-15)",
)
def start_detection_job(
	request: StartDetectionJobRequest,
	service: InferenceService = Depends(get_inference_service),
) -> ApiResponse[DetectionJobResponse]:
	try:
		job = service.start_detection_job(
			project_id=request.project_id,
			target_artifact_id=request.target_artifact_id,
			input_file_path=request.input_file_path,
			model_version_id=request.model_version_id,
			use_rules=request.use_rules,
			score_threshold=request.score_threshold,
			job_name=request.job_name,
			user_name=request.created_by,
		)
		return ApiResponse.ok(
			data=_to_job_response(job),
			status_code=status.HTTP_201_CREATED,
			message=f"Detection job '{job.job_name}' completed with status {job.status}",
		)
	except FileNotFoundError as e:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
	except ValueError as e:
		err_msg = str(e)
		code = status.HTTP_404_NOT_FOUND if "not found" in err_msg.lower() else status.HTTP_400_BAD_REQUEST
		raise HTTPException(status_code=code, detail=err_msg)


@router.get(
	"/jobs/{job_id}",
	response_model=ApiResponse[DetectionJobResponse],
	summary="Get detection job details and summary metrics by ID (SUC-16, SUC-19)",
)
def get_detection_job(
	job_id: UUID,
	service: InferenceService = Depends(get_inference_service),
) -> ApiResponse[DetectionJobResponse]:
	try:
		job = service.get_detection_job(job_id)
		return ApiResponse.ok(
			data=_to_job_response(job),
			message="Detection job retrieved successfully",
		)
	except ValueError as e:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
	"/jobs/{job_id}/results",
	response_model=ApiResponse[DetectionJobResultsResponse],
	summary="Query transaction detection results, score distribution, and rule breakdown (SUC-16)",
)
def get_detection_job_results(
	job_id: UUID,
	action_filter: Optional[str] = Query(
		None,
		description="Filter by decision: FLAGGED | REJECT | REVIEW | ALLOW",
	),
	rule_code: Optional[str] = Query(None, description="Filter by triggered rule_code"),
	search: Optional[str] = Query(None, description="Search by event_id or user_id"),
	min_score: Optional[float] = Query(None, ge=0.0, le=1.0),
	max_score: Optional[float] = Query(None, ge=0.0, le=1.0),
	limit: int = Query(200, ge=1, le=2000),
	offset: int = Query(0, ge=0),
	service: InferenceService = Depends(get_inference_service),
) -> ApiResponse[DetectionJobResultsResponse]:
	try:
		res = service.get_detection_job_results(
			job_id=job_id,
			action_filter=action_filter,
			rule_code=rule_code,
			search=search,
			min_score=min_score,
			max_score=max_score,
			limit=limit,
			offset=offset,
		)
		tx_items = [
			DetectionTransactionRecordResponse(
				row_index=tx["row_index"],
				event_id=tx["event_id"],
				user_id=tx["user_id"],
				timestamp=tx["timestamp"],
				amount=tx["amount"],
				model_score=tx["model_score"],
				triggered_rules=tx.get("triggered_rules", []),
				triggered_rule_details=[
					TriggeredRuleDetailResponse(**d) for d in tx.get("triggered_rule_details", [])
				],
				rule_action=tx["rule_action"],
				final_action=tx["final_action"],
				is_flagged=tx["is_flagged"],
				case_id=tx.get("case_id"),
				features=tx.get("features", {}),
			)
			for tx in res["transactions"]
		]
		payload = DetectionJobResultsResponse(
			job=_to_job_response(res["job"]),
			total_filtered=res["total_filtered"],
			transactions=tx_items,
			summary_metrics=res.get("summary_metrics") or {},
		)
		return ApiResponse.ok(
			data=payload,
			message=f"Retrieved {len(tx_items)} detection records (of {res['total_filtered']} matching)",
		)
	except ValueError as e:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
	except FileNotFoundError as e:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
	"/jobs/{job_id}/export",
	summary="Export detection job results as CSV or Parquet (SUC-16)",
)
def export_detection_job_results(
	job_id: UUID,
	file_format: str = Query("csv", description="Export format: csv | parquet"),
	only_flagged: bool = Query(False, description="Export only flagged (REJECT + REVIEW) transactions"),
	service: InferenceService = Depends(get_inference_service),
) -> Response:
	try:
		file_bytes, filename, media_type = service.export_detection_job_results(
			job_id=job_id,
			file_format=file_format,
			only_flagged=only_flagged,
		)
		return Response(
			content=file_bytes,
			media_type=media_type,
			headers={"Content-Disposition": f'attachment; filename="{filename}"'},
		)
	except (ValueError, FileNotFoundError) as e:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
	"/jobs/{job_id}/send-to-investigation",
	response_model=ApiResponse[List[InvestigationCaseResponse]],
	status_code=status.HTTP_201_CREATED,
	summary="Dispatch selected transactions from a detection job to Investigation Cases (SUC-16)",
)
def send_to_investigation(
	job_id: UUID,
	request: SendToInvestigationRequest,
	service: InferenceService = Depends(get_inference_service),
) -> ApiResponse[List[InvestigationCaseResponse]]:
	try:
		cases = service.dispatch_cases_to_investigation(
			job_id=job_id,
			event_ids=request.event_ids,
			analyst_notes=request.analyst_notes,
		)
		return ApiResponse.ok(
			data=[_to_case_response(c) for c in cases],
			status_code=status.HTTP_201_CREATED,
			message=f"Created {len(cases)} investigation cases",
		)
	except ValueError as e:
		err_msg = str(e)
		code = status.HTTP_404_NOT_FOUND if "not found" in err_msg.lower() else status.HTTP_400_BAD_REQUEST
		raise HTTPException(status_code=code, detail=err_msg)


@router.get(
	"/cases",
	response_model=ApiResponse[List[InvestigationCaseResponse]],
	summary="List investigation cases created for a project",
)
def list_investigation_cases(
	project_id: UUID = Query(..., description="Project ID to query investigation cases for"),
	case_status: Optional[InvestigationStatus] = Query(None, alias="status"),
	limit: int = Query(100, ge=1, le=500),
	service: InferenceService = Depends(get_inference_service),
) -> ApiResponse[List[InvestigationCaseResponse]]:
	if not service.investigation_repo:
		return ApiResponse.ok(data=[], message="Retrieved 0 investigation cases")
	cases = service.investigation_repo.list_cases(
		project_id=project_id,
		status=case_status,
		limit=limit,
	)
	return ApiResponse.ok(
		data=[_to_case_response(c) for c in cases],
		message=f"Retrieved {len(cases)} investigation cases",
	)


__all__ = ["router"]
