from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status

from usfds_core.domain.entities.model import Model, ModelVersion, TrainingRun
from usfds_core.domain.schemas.training_config import TrainingRunConfig
from usfds_core.services.training.training_service import TrainingOrchestrationService
from usfds_server.dependencies import get_training_service
from usfds_server.schemas.base_response import ApiResponse
from usfds_server.schemas.training_api_schemas import (
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


def _to_training_run_response(run: TrainingRun) -> TrainingRunResponse:
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
        model = service.register_plugged_model(
            model_artifact_path=request.model_artifact_path,
            user_id=request.user_id or "mock_user",
            project_id=request.project_id,
            manifest_override=request.manifest_override,
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
            hyperparameters=request.hyperparameters,
            compute_target=request.compute_target,
            run_name=request.run_name,
        )
        run = service.prepare_and_dispatch(config=config, user_name=request.created_by)
        # Re-fetch run so post-execution metrics & version_id are reflected for synchronous dispatch
        updated_run = service.get_training_run(run.run_id)
        return ApiResponse.ok(
            data=_to_training_run_response(updated_run),
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
    summary="List training runs with optional model_id filter",
)
def list_training_runs(
    model_id: Optional[UUID] = Query(None, description="Optional filter by Model ID"),
    service: TrainingOrchestrationService = Depends(get_training_service),
) -> ApiResponse[List[TrainingRunResponse]]:
    runs = service.list_training_runs(model_id=model_id)
    return ApiResponse.ok(
        data=[_to_training_run_response(r) for r in runs],
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
        return ApiResponse.ok(
            data=_to_training_run_response(run),
            message="Training run retrieved successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


__all__ = ["router"]
