import json
import math
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
import pandas as pd
from sqlalchemy.orm import Session

from usfds_core.domain.entities.detection import DetectionJob
from usfds_core.services.inference.inference_service import InferenceService
from usfds_infra.storage.local_storage import LocalFileStorage
from usfds_server.dependencies import get_db, get_storage, get_inference_service
from usfds_server.routers.investigation_router import _project, _source_frame, get_actor, ingest_request
from usfds_server.schemas.investigation_api_schemas import CaseIntakeRequest, TransactionSnapshot
from usfds_server.schemas.base_response import ApiResponse
from usfds_server.schemas.detection_api_schemas import (
	DetectionJobResponse,
	DetectionJobResultsResponse,
	DetectionTransactionRecordResponse,
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
	response_model=ApiResponse[dict],
	status_code=status.HTTP_201_CREATED,
	summary="Dispatch selected transactions from a detection job to Investigation Cases (SUC-16)",
)
def send_to_investigation(
	job_id: UUID,
	request: SendToInvestigationRequest,
	service: InferenceService = Depends(get_inference_service),
	session: Session = Depends(get_db),
	storage: LocalFileStorage = Depends(get_storage),
	actor: str = Depends(get_actor),
) -> ApiResponse[dict]:
	try:
		job = service.get_detection_job(job_id)
		project = _project(session, job.project_id, True)
		frame = _source_frame(session, storage, job.project_id, None, job_id)
		frame["event_id"] = frame["event_id"].astype(str)
		counts = frame["event_id"].value_counts()
		indexed = frame.set_index("event_id", drop=False)
		transactions = []
		for event_id in dict.fromkeys(request.event_ids):
			if counts.get(event_id, 0) != 1:
				raise HTTPException(400, f"Event {event_id} must exist exactly once in the job output")
			row = indexed.loc[event_id]
			if row.get("final_action") not in {"REVIEW", "REJECT"}:
				raise HTTPException(400, f"Event {event_id} is not flagged")
			details = row.get("triggered_rule_details", "[]")
			details = json.loads(details) if isinstance(details, str) else list(details)
			rules = []
			for detail in details:
				if detail["action"] not in {"REVIEW", "REJECT"}:
					continue
				copied = dict(detail)
				copied.setdefault("trigger_reason", " AND ".join(copied.get("matched_clauses", [])) or f"{copied['rule_code']} matched at detection time")
				rules.append(copied)
			attributes = row.get("raw_attributes")
			if isinstance(attributes, str):
				attributes = json.loads(attributes)
			if not isinstance(attributes, dict):
				attributes = {name: _snapshot_value(row[name]) for name in (project.raw_schema or {}).get("columns", {}) if name in row}
			contributions = row.get("feature_contributions", "[]")
			contributions = json.loads(contributions) if isinstance(contributions, str) else list(contributions)
			transactions.append(TransactionSnapshot.model_validate({
				"event_id": event_id, "user_id": str(row["user_id"]), "timestamp": pd.to_datetime(row["timestamp"], utc=True).isoformat(),
				"amount": float(row["amount"]), "model_score": float(row["model_score"]) if job.model_version_id else None,
				"final_action": row["final_action"], "triggered_rules": rules, "feature_contributions": contributions, "attributes": attributes,
			}))
		payload = CaseIntakeRequest(project_id=job.project_id, detection_job_id=job_id, model_version_id=job.model_version_id, transactions=transactions)
		result = ingest_request(payload, session, storage, actor, request.analyst_notes)
		return ApiResponse.ok(
			data=result,
			status_code=status.HTTP_201_CREATED,
			message=f"Created {result['accepted_count']} investigation cases",
		)
	except ValueError as e:
		err_msg = str(e)
		code = status.HTTP_404_NOT_FOUND if "not found" in err_msg.lower() else status.HTTP_400_BAD_REQUEST
		raise HTTPException(status_code=code, detail=err_msg)


def _snapshot_value(value):
	if isinstance(value, (dict, list)):
		return value
	if pd.isna(value):
		return None
	if hasattr(value, "isoformat"):
		return value.isoformat()
	if hasattr(value, "item"):
		value = value.item()
	if isinstance(value, float) and not math.isfinite(value):
		raise ValueError("Non-finite source value")
	return value


__all__ = ["router"]
