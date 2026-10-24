import base64
from email.parser import BytesParser
from email.policy import default as default_email_policy
import json
from typing import Dict, List, Optional, Tuple
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from usfds_core.domain.entities.model import Model, ModelVersion, TrainingRun
from usfds_core.domain.schemas.model_plugin import ModelPluginManifest
from usfds_core.domain.schemas.training_config import TrainingRunConfig
from usfds_core.services.training.training_service import TrainingOrchestrationService
from usfds_server.dependencies import get_training_service
from usfds_server.schemas.base_response import ApiResponse
from usfds_server.schemas.training_api_schemas import (
    ActivateModelVersionRequest,
    ModelResponse,
    ModelVersionResponse,
    RegisterPluggedModelRequest,
    StartTrainingRunRequest,
    TrainingRunResponse,
)

router = APIRouter(prefix="/api/v1/training", tags=["Model Training & Registry"])


def _to_model_response(model: Model) -> ModelResponse:
    exec_type_str = (
        model.execution_type.value
        if hasattr(model.execution_type, "value")
        else str(model.execution_type)
    )
    risk_str = (
        model.risk_level.value
        if hasattr(model.risk_level, "value")
        else str(model.risk_level) if model.risk_level else None
    )
    return ModelResponse(
        model_id=model.model_id,
        project_id=model.project_id,
        user_id=model.user_id,
        model_name=model.model_name,
        display_name=model.display_name,
        description=model.description,
        execution_type=exec_type_str,
        entrypoint_uri=model.entrypoint_uri,
        hyperparameter_schema=model.hyperparameter_schema,
        default_hyperparameters=model.default_hyperparameters,
        risk_level=risk_str,
        github_repo=model.github_repo,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_model_version_response(version: ModelVersion) -> ModelVersionResponse:
    status_str = (
        version.status.value
        if hasattr(version.status, "value")
        else str(version.status)
    )
    return ModelVersionResponse(
        version_id=version.version_id,
        model_id=version.model_id,
        project_id=version.project_id,
        run_id=version.run_id,
        semver=version.semver,
        artifact_uri=version.artifact_uri,
        description=version.description,
        artifact_size_mb=version.artifact_size_mb,
        checksum_sha256=version.checksum_sha256,
        framework=version.framework,
        decision_threshold=version.decision_threshold,
        status=status_str,
        registered_by=version.registered_by,
        registered_at=version.registered_at,
    )


def _to_training_run_response(
    run: TrainingRun,
    dataset_artifact_id: Optional[UUID] = None,
) -> TrainingRunResponse:
    status_str = (
        run.status.value
        if hasattr(run.status, "value")
        else str(run.status)
    )
    return TrainingRunResponse(
        run_id=run.run_id,
        project_id=run.project_id,
        model_id=run.model_id,
        version_id=run.version_id,
        dataset_artifact_id=dataset_artifact_id,
        run_name=run.run_name,
        status=status_str,
        accuracy=run.accuracy,
        precision_score=run.precision_score,
        recall_score=run.recall_score,
        f1_score=run.f1_score,
        loss=run.loss,
        default_threshold=run.default_threshold,
        recommended_threshold=run.recommended_threshold,
        hyperparameters=run.hyperparameters,
        custom_metrics=run.custom_metrics,
        compute_target=run.compute_target,
        error_message=run.error_message,
        created_by=run.created_by,
        started_at=run.started_at,
        completed_at=run.completed_at,
        duration_seconds=run.duration_seconds,
        logs_path=run.logs_path,
        metrics_path=run.metrics_path,
        eval_predictions_path=run.eval_predictions_path,
        created_at=run.created_at,
    )


# ==========================================
# Model Registry Endpoints
# ==========================================

def _parse_multipart_upload(
    content_type: str,
    raw_body: bytes,
) -> Tuple[Optional[bytes], Optional[str], Dict[str, str]]:
    """Parse multipart/form-data payload using Python stdlib email.parser (no python-multipart dependency)."""
    header_bytes = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
    msg = BytesParser(policy=default_email_policy).parsebytes(header_bytes + raw_body)
    file_bytes: Optional[bytes] = None
    filename: Optional[str] = None
    fields: Dict[str, str] = {}

    if msg.is_multipart():
        for part in msg.iter_parts():
            cd = part.get("Content-Disposition", "")
            name_param = part.get_param("name", header="Content-Disposition")
            fname_param = part.get_filename()
            payload = part.get_payload(decode=True) or b""
            if fname_param is not None or name_param == "file":
                file_bytes = payload
                filename = fname_param or "plugin.zip"
            elif name_param:
                fields[str(name_param)] = payload.decode("utf-8", errors="replace")
    return file_bytes, filename, fields


@router.post(
    "/models/plugins",
    response_model=ApiResponse[ModelResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Validate and register a custom user-imported model plugin",
)
def register_plugged_model(
    request: RegisterPluggedModelRequest,
    service: TrainingOrchestrationService = Depends(get_training_service),
) -> ApiResponse[ModelResponse]:
    try:
        zip_bytes: Optional[bytes] = None
        if request.zip_base64:
            b64_str = request.zip_base64.strip()
            if "," in b64_str and b64_str.startswith("data:"):
                b64_str = b64_str.split(",", 1)[1]
            zip_bytes = base64.b64decode(b64_str)

        model = service.register_plugged_model(
            model_artifact_path=request.model_artifact_path,
            user_id=request.user_id or "mock_user",
            project_id=request.project_id,
            manifest_override=request.manifest_override,
            zip_bytes=zip_bytes,
        )
        return ApiResponse.ok(
            data=_to_model_response(model),
            status_code=status.HTTP_201_CREATED,
            message=f"Model plugin '{model.model_name}' validated and registered successfully",
        )
    except ValueError as e:
        err_msg = str(e)
        code = status.HTTP_404_NOT_FOUND if "not found" in err_msg.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=err_msg)


@router.post(
    "/models/plugins/upload",
    response_model=ApiResponse[ModelResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload a .zip model plugin package, validate (AST + dry-run), and register in Model Registry",
)
async def upload_and_register_plugged_model(
    request: Request,
    service: TrainingOrchestrationService = Depends(get_training_service),
) -> ApiResponse[ModelResponse]:
    try:
        content_type = request.headers.get("content-type", "")
        raw_body = await request.body()
        if not raw_body:
            raise ValueError("Uploaded request body is empty.")

        zip_bytes: Optional[bytes] = None
        filename = "plugin.zip"
        fields: Dict[str, str] = {}

        if "multipart/form-data" in content_type.lower():
            zip_bytes, parsed_name, fields = _parse_multipart_upload(content_type, raw_body)
            if parsed_name:
                filename = parsed_name
        else:
            zip_bytes = raw_body

        if not filename.lower().endswith(".zip"):
            raise ValueError("Uploaded plugin package must be a .zip archive.")
        if not zip_bytes:
            raise ValueError("Uploaded .zip file is empty.")

        project_id_str = fields.get("project_id") or request.query_params.get("project_id")
        user_id_str = fields.get("user_id") or request.query_params.get("user_id")
        manifest_json_str = fields.get("manifest_override_json")

        parsed_project_id: Optional[UUID] = (
            UUID(project_id_str.strip()) if project_id_str and project_id_str.strip() else None
        )
        parsed_manifest: Optional[ModelPluginManifest] = None
        if manifest_json_str and manifest_json_str.strip():
            raw_manifest = json.loads(manifest_json_str)
            parsed_manifest = ModelPluginManifest(**raw_manifest)

        model = service.register_plugged_model(
            zip_bytes=zip_bytes,
            user_id=user_id_str or "mock_user",
            project_id=parsed_project_id,
            manifest_override=parsed_manifest,
        )
        return ApiResponse.ok(
            data=_to_model_response(model),
            status_code=status.HTTP_201_CREATED,
            message=f"Model plugin '{model.model_name}' validated and registered successfully",
        )
    except (ValueError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/models",
    response_model=ApiResponse[List[ModelResponse]],
    summary="List all registered models (built-in and custom plugins)",
)
def list_models(
    project_id: Optional[UUID] = Query(None, description="Optional filter by project ID"),
    service: TrainingOrchestrationService = Depends(get_training_service),
) -> ApiResponse[List[ModelResponse]]:
    models = service.list_models(project_id=project_id)
    return ApiResponse.ok(
        data=[_to_model_response(m) for m in models],
        message=f"Retrieved {len(models)} models",
    )


@router.get(
    "/models/{model_id}",
    response_model=ApiResponse[ModelResponse],
    summary="Get registered model details by ID",
)
def get_model(
    model_id: UUID,
    service: TrainingOrchestrationService = Depends(get_training_service),
) -> ApiResponse[ModelResponse]:
    try:
        model = service.get_model(model_id)
        return ApiResponse.ok(data=_to_model_response(model), message="Model retrieved successfully")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/models/{model_id}/versions",
    response_model=ApiResponse[List[ModelVersionResponse]],
    summary="List all trained versions for a model",
)
def list_model_versions(
    model_id: UUID,
    service: TrainingOrchestrationService = Depends(get_training_service),
) -> ApiResponse[List[ModelVersionResponse]]:
    try:
        versions = service.list_model_versions(model_id)
        return ApiResponse.ok(
            data=[_to_model_version_response(v) for v in versions],
            message=f"Retrieved {len(versions)} model versions",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/versions/{version_id}",
    response_model=ApiResponse[ModelVersionResponse],
    summary="Get a specific ModelVersion by ID",
)
def get_model_version(
    version_id: UUID,
    service: TrainingOrchestrationService = Depends(get_training_service),
) -> ApiResponse[ModelVersionResponse]:
    try:
        version = service.get_model_version(version_id)
        return ApiResponse.ok(
            data=_to_model_version_response(version),
            message="Model version retrieved successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/versions/{version_id}/activate",
    response_model=ApiResponse[ModelVersionResponse],
    summary="Verify artifact integrity and activate a ModelVersion (SUC-10)",
)
def activate_model_version(
    version_id: UUID,
    request: Optional[ActivateModelVersionRequest] = None,
    service: TrainingOrchestrationService = Depends(get_training_service),
) -> ApiResponse[ModelVersionResponse]:
    try:
        version = service.activate_model_version(
            version_id=version_id,
            decision_threshold=request.decision_threshold if request else None,
            description=request.description if request else None,
        )
        return ApiResponse.ok(
            data=_to_model_version_response(version),
            message=f"Model version '{version.semver}' activated successfully",
        )
    except ValueError as e:
        err_msg = str(e)
        code = status.HTTP_404_NOT_FOUND if "not found" in err_msg.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=err_msg)


# ==========================================
# Training Run Execution & Query Endpoints
# ==========================================

@router.post(
    "/runs",
    response_model=ApiResponse[TrainingRunResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Prepare and dispatch a model training run on a FEATURE_ENGINEERED dataset artifact",
)
def start_training_run(
    request: StartTrainingRunRequest,
    service: TrainingOrchestrationService = Depends(get_training_service),
) -> ApiResponse[TrainingRunResponse]:
    try:
        config = TrainingRunConfig(
            model_id=request.model_id,
            dataset_artifact_id=request.dataset_artifact_id,
            project_id=request.project_id,
            hyperparameters=request.hyperparameters,
            compute_target=request.compute_target,
            run_name=request.run_name,
        )
        run = service.prepare_and_dispatch(config=config, user_name=request.created_by)
        # Re-fetch run so post-execution metrics & version_id are reflected for synchronous dispatch
        updated_run = service.get_training_run(run.run_id)
        artifact_id = service.get_run_dataset_artifact_id(updated_run.run_id)
        return ApiResponse.ok(
            data=_to_training_run_response(updated_run, dataset_artifact_id=artifact_id),
            status_code=status.HTTP_201_CREATED,
            message=f"Training run '{updated_run.run_name}' completed with status {updated_run.status}",
        )
    except ValueError as e:
        err_msg = str(e)
        code = status.HTTP_404_NOT_FOUND if "not found" in err_msg.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=err_msg)


@router.get(
    "/runs",
    response_model=ApiResponse[List[TrainingRunResponse]],
    summary="List training runs with optional model_id and project_id filters",
)
def list_training_runs(
    model_id: Optional[UUID] = Query(None, description="Optional filter by Model ID"),
    project_id: Optional[UUID] = Query(None, description="Optional filter by Project ID"),
    service: TrainingOrchestrationService = Depends(get_training_service),
) -> ApiResponse[List[TrainingRunResponse]]:
    runs = service.list_training_runs(model_id=model_id, project_id=project_id)
    return ApiResponse.ok(
        data=[
            _to_training_run_response(
                r,
                dataset_artifact_id=service.get_run_dataset_artifact_id(r.run_id),
            )
            for r in runs
        ],
        message=f"Retrieved {len(runs)} training runs",
    )


@router.get(
    "/runs/{run_id}",
    response_model=ApiResponse[TrainingRunResponse],
    summary="Get training run details and evaluation metrics by ID",
)
def get_training_run(
    run_id: UUID,
    service: TrainingOrchestrationService = Depends(get_training_service),
) -> ApiResponse[TrainingRunResponse]:
    try:
        run = service.get_training_run(run_id)
        artifact_id = service.get_run_dataset_artifact_id(run.run_id)
        return ApiResponse.ok(
            data=_to_training_run_response(run, dataset_artifact_id=artifact_id),
            message="Training run retrieved successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


__all__ = ["router"]
