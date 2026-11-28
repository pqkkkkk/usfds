import base64
from email.parser import BytesParser
from email.policy import default as default_email_policy
import json
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.concurrency import run_in_threadpool

from usfds_core.domain.entities.auth import ActorContext
from usfds_core.domain.entities.enums import TrainingRunStatus
from usfds_core.domain.entities.model import Model, ModelVersion, TrainingRun
from usfds_core.domain.schemas.model_plugin import ModelPluginManifest
from usfds_core.domain.schemas.training_config import TrainingRunConfig
from usfds_core.repositories.base_user_repo import IUserRepository
from usfds_core.services.auth.access_logic import effective_scope
from usfds_core.services.auth.authz_service import AuthzService
from usfds_core.services.training.compute_policy import ComputeSelectionPolicy
from usfds_core.services.training.providers.base_provider import RemoteProviderRegistry
from usfds_core.services.training.training_service import (
    ModelLineageGraph,
    TrainingOrchestrationService,
)
from usfds_core.storage.base_storage import IFileStorage
from usfds_infra.database import session_scope
from usfds_infra.database.repos.auth import (
    SqlPermissionRepository,
    SqlProjectMemberRepository,
    SqlRoleRepository,
    SqlUserRepository,
    SqlUserSessionRepository,
)
from usfds_infra.job_queue import JOB_PLUGIN_DRY_RUN, QUEUE_TRAINING
from usfds_server import dependencies as _server_deps
from usfds_server.config import settings
from usfds_server.dependencies import (
    get_actor_context,
    get_authz_service,
    get_job_queue,
    get_storage,
    get_training_service,
)
from usfds_server.providers.auth import (
    get_auth_service,
    get_authz_service as build_authz_service,
    get_current_user,
    get_password_hasher,
    get_token_provider,
    get_user_repo,
)
from usfds_server.providers.training import (
    build_training_service_for_session,
    get_compute_selection_policy,
    get_remote_provider_registry,
)
from usfds_server.schemas.base_response import ApiResponse, CursorPage, ResourceOwnerDto
from usfds_server.schemas.pagination import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
    paginate_cursor,
    resolve_owners,
)
from usfds_server.schemas.training_api_schemas import (
    ActivateModelVersionRequest,
    ComputeRecommendationResponse,
    ComputeTargetOptionResponse,
    ComputeTargetsResponse,
    ModelLineageEdgeResponse,
    ModelLineageNodeResponse,
    ModelLineageResponse,
    ModelResponse,
    ModelVersionResponse,
    RegisterPluggedModelRequest,
    StartTrainingRunRequest,
    TrainingRunResponse,
)

router = APIRouter(prefix="/api/v1/training", tags=["Model Training & Registry"])


def _to_model_response(
    model: Model,
    owner: Optional[ResourceOwnerDto] = None,
) -> ModelResponse:
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
        owner=owner,
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


def _to_model_version_response(
    version: ModelVersion,
    owner: Optional[ResourceOwnerDto] = None,
) -> ModelVersionResponse:
    status_str = (
        version.status.value
        if hasattr(version.status, "value")
        else str(version.status)
    )
    return ModelVersionResponse(
        version_id=version.version_id,
        model_id=version.model_id,
        project_id=version.project_id,
        user_id=version.user_id,
        owner=owner,
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
    owner: Optional[ResourceOwnerDto] = None,
) -> TrainingRunResponse:
    status_str = (
        run.status.value
        if hasattr(run.status, "value")
        else str(run.status)
    )
    return TrainingRunResponse(
        run_id=run.run_id,
        project_id=run.project_id,
        user_id=run.user_id,
        owner=owner,
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
        external_job_id=run.external_job_id,
        compute_metadata=run.compute_metadata,
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
    actor: ActorContext = Depends(get_actor_context),
    authz: AuthzService = Depends(get_authz_service),
    service: TrainingOrchestrationService = Depends(get_training_service),
    user_repo: IUserRepository = Depends(get_user_repo),
) -> ApiResponse[ModelResponse]:
    if request.project_id is not None:
        authz.require_project_permission(actor, "model:create", request.project_id, action="create")
    else:
        authz.require_system_permission(actor, "model_builtin:manage")
    try:
        zip_bytes: Optional[bytes] = None
        if request.zip_base64:
            b64_str = request.zip_base64.strip()
            if "," in b64_str and b64_str.startswith("data:"):
                b64_str = b64_str.split(",", 1)[1]
            zip_bytes = base64.b64decode(b64_str)

        if settings.dispatch_backend == "queue":
            res = get_job_queue().enqueue_and_wait(
                QUEUE_TRAINING,
                JOB_PLUGIN_DRY_RUN,
                {
                    "model_artifact_path": request.model_artifact_path,
                    "user_id": str(actor.user_id),
                    "project_id": str(request.project_id) if request.project_id else None,
                    "manifest_override": (
                        request.manifest_override.model_dump(mode="json")
                        if request.manifest_override
                        else None
                    ),
                    "zip_base64": request.zip_base64,
                },
                job_id=f"plugin-{uuid4()}",
                timeout_seconds=settings.queue_wait_timeout_seconds,
            )
            model = service.get_model(UUID(str(res["model_id"])))
        else:
            model = service.register_plugged_model(
                model_artifact_path=request.model_artifact_path,
                user_id=str(actor.user_id),
                project_id=request.project_id,
                manifest_override=request.manifest_override,
                zip_bytes=zip_bytes,
            )
        owner = resolve_owners(user_repo, [model.user_id]).get(model.user_id)
        return ApiResponse.ok(
            data=_to_model_response(model, owner=owner),
            status_code=status.HTTP_201_CREATED,
            message=f"Model plugin '{model.model_name}' validated and registered successfully",
        )
    except ValueError as e:
        err_msg = str(e)
        code = status.HTTP_404_NOT_FOUND if "not found" in err_msg.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=err_msg)


async def _read_bounded_body(request: Request, max_bytes: int, max_mb: int) -> bytes:
    """Read request body incrementally without exceeding `max_bytes` in memory (ISS-016)."""
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"Uploaded plugin exceeds maximum allowed size of {max_mb} MB.",
                )
        except ValueError:
            pass

    buffer = bytearray()
    async for chunk in request.stream():
        if not chunk:
            continue
        if len(buffer) + len(chunk) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Uploaded plugin exceeds maximum allowed size of {max_mb} MB.",
            )
        buffer.extend(chunk)
    return bytes(buffer)


def _register_uploaded_plugin_sync(
    *,
    raw_body: bytes,
    content_type: str,
    query_params: Dict[str, str],
    actor: ActorContext,
    authz: AuthzService,
    service: TrainingOrchestrationService,
) -> Model:
    """Synchronous plugin parsing, authz, and registration/queue-wait executed off the event loop (ISS-019)."""
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

    project_id_str = fields.get("project_id") or query_params.get("project_id")
    manifest_json_str = fields.get("manifest_override_json")

    parsed_project_id: Optional[UUID] = (
        UUID(project_id_str.strip()) if project_id_str and project_id_str.strip() else None
    )
    if parsed_project_id is not None:
        authz.require_project_permission(actor, "model:create", parsed_project_id, action="create")
    else:
        authz.require_system_permission(actor, "model_builtin:manage")

    parsed_manifest: Optional[ModelPluginManifest] = None
    if manifest_json_str and manifest_json_str.strip():
        raw_manifest = json.loads(manifest_json_str)
        parsed_manifest = ModelPluginManifest(**raw_manifest)

    if settings.dispatch_backend == "queue":
        res = get_job_queue().enqueue_and_wait(
            QUEUE_TRAINING,
            JOB_PLUGIN_DRY_RUN,
            {
                "zip_base64": base64.b64encode(zip_bytes).decode("ascii"),
                "user_id": str(actor.user_id),
                "project_id": str(parsed_project_id) if parsed_project_id else None,
                "manifest_override": (
                    parsed_manifest.model_dump(mode="json")
                    if parsed_manifest
                    else None
                ),
            },
            job_id=f"plugin-upload-{uuid4()}",
            timeout_seconds=settings.queue_wait_timeout_seconds,
        )
        return service.get_model(UUID(str(res["model_id"])))

    return service.register_plugged_model(
        zip_bytes=zip_bytes,
        user_id=str(actor.user_id),
        project_id=parsed_project_id,
        manifest_override=parsed_manifest,
    )


@router.post(
    "/models/plugins/upload",
    response_model=ApiResponse[ModelResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload a .zip model plugin package, validate (AST + dry-run), and register in Model Registry",
)
async def upload_and_register_plugged_model(
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
    authz: AuthzService = Depends(get_authz_service),
    service: TrainingOrchestrationService = Depends(get_training_service),
    user_repo: IUserRepository = Depends(get_user_repo),
) -> ApiResponse[ModelResponse]:
    try:
        content_type = request.headers.get("content-type", "")
        max_mb = max(1, settings.max_plugin_upload_mb)
        raw_body = await _read_bounded_body(request, max_bytes=max_mb * 1024 * 1024, max_mb=max_mb)
        if not raw_body:
            raise ValueError("Uploaded request body is empty.")

        model = await run_in_threadpool(
            _register_uploaded_plugin_sync,
            raw_body=raw_body,
            content_type=content_type,
            query_params=dict(request.query_params),
            actor=actor,
            authz=authz,
            service=service,
        )
        owner = resolve_owners(user_repo, [model.user_id]).get(model.user_id)
        return ApiResponse.ok(
            data=_to_model_response(model, owner=owner),
            status_code=status.HTTP_201_CREATED,
            message=f"Model plugin '{model.model_name}' validated and registered successfully",
        )
    except (ValueError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/models",
    response_model=ApiResponse[CursorPage[ModelResponse]],
    summary="List registered models (built-in and project custom plugins) with cursor pagination",
)
def list_models(
    project_id: UUID = Query(..., description="Project ID"),
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: Optional[str] = Query(None, description="Opaque pagination cursor"),
    actor: ActorContext = Depends(get_actor_context),
    authz: AuthzService = Depends(get_authz_service),
    service: TrainingOrchestrationService = Depends(get_training_service),
    user_repo: IUserRepository = Depends(get_user_repo),
) -> ApiResponse[CursorPage[ModelResponse]]:
    owner_filter = authz.resolve_project_list_owner(actor, "model:read", project_id)
    models = [
        m
        for m in service.list_models(project_id=project_id)
        if m.project_id is None or owner_filter is None or m.user_id == owner_filter
    ]
    page_items, next_cursor = paginate_cursor(
        models,
        limit=limit,
        cursor=cursor,
        key_fn=lambda m: m.model_id,
    )
    owners = resolve_owners(user_repo, (m.user_id for m in page_items))
    return ApiResponse.ok(
        data=CursorPage(
            items=[_to_model_response(m, owner=owners.get(m.user_id) if m.user_id else None) for m in page_items],
            nextCursor=next_cursor,
        ),
        message=f"Retrieved {len(page_items)} models",
    )


@router.get(
    "/models/{model_id}",
    response_model=ApiResponse[ModelResponse],
    summary="Get registered model details by ID",
)
def get_model(
    model_id: UUID,
    project_id: UUID = Query(..., description="Project ID"),
    actor: ActorContext = Depends(get_actor_context),
    authz: AuthzService = Depends(get_authz_service),
    service: TrainingOrchestrationService = Depends(get_training_service),
    user_repo: IUserRepository = Depends(get_user_repo),
) -> ApiResponse[ModelResponse]:
    authz.require_project_scope(actor, "model:read", project_id)
    try:
        model = service.get_model(model_id)
        if model.project_id is not None and model.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model '{model_id}' not found in project '{project_id}'.",
            )
        if model.project_id is not None:
            authz.require_project_permission(actor, "model:read", project_id, owner_id=model.user_id)
        owner = resolve_owners(user_repo, [model.user_id]).get(model.user_id) if model.user_id else None
        return ApiResponse.ok(data=_to_model_response(model, owner=owner), message="Model retrieved successfully")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/models/{model_id}/versions",
    response_model=ApiResponse[CursorPage[ModelVersionResponse]],
    summary="List all trained versions for a model with cursor pagination",
)
def list_model_versions(
    model_id: UUID,
    project_id: UUID = Query(..., description="Project ID"),
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: Optional[str] = Query(None, description="Opaque pagination cursor"),
    actor: ActorContext = Depends(get_actor_context),
    authz: AuthzService = Depends(get_authz_service),
    service: TrainingOrchestrationService = Depends(get_training_service),
    user_repo: IUserRepository = Depends(get_user_repo),
) -> ApiResponse[CursorPage[ModelVersionResponse]]:
    owner_filter = authz.resolve_project_list_owner(actor, "model:read", project_id)
    try:
        model = service.get_model(model_id)
        if model.project_id is not None and model.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model '{model_id}' not found in project '{project_id}'.",
            )
        if model.project_id is not None:
            authz.require_project_permission(actor, "model:read", project_id, owner_id=model.user_id)
        versions = [
            v
            for v in service.list_model_versions(model_id, project_id=project_id)
            if v.project_id == project_id and (owner_filter is None or v.user_id == owner_filter)
        ]
        page_items, next_cursor = paginate_cursor(
            versions,
            limit=limit,
            cursor=cursor,
            key_fn=lambda v: v.version_id,
        )
        owners = resolve_owners(user_repo, (v.user_id for v in page_items))
        return ApiResponse.ok(
            data=CursorPage(
                items=[_to_model_version_response(v, owner=owners.get(v.user_id)) for v in page_items],
                nextCursor=next_cursor,
            ),
            message=f"Retrieved {len(page_items)} model versions",
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
    project_id: UUID = Query(..., description="Project ID"),
    actor: ActorContext = Depends(get_actor_context),
    authz: AuthzService = Depends(get_authz_service),
    service: TrainingOrchestrationService = Depends(get_training_service),
    user_repo: IUserRepository = Depends(get_user_repo),
) -> ApiResponse[ModelVersionResponse]:
    authz.require_project_scope(actor, "model:read", project_id)
    try:
        version = service.get_model_version(version_id)
        if version.project_id is None or version.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ModelVersion '{version_id}' not found in project '{project_id}'.",
            )
        authz.require_project_permission(actor, "model:read", project_id, owner_id=version.user_id)
        owner = resolve_owners(user_repo, [version.user_id]).get(version.user_id)
        return ApiResponse.ok(
            data=_to_model_version_response(version, owner=owner),
            message="Model version retrieved successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


def _to_model_lineage_response(graph: ModelLineageGraph) -> ModelLineageResponse:
    return ModelLineageResponse(
        root_version_id=graph.root_version_id,
        root_run_id=graph.root_run_id,
        nodes=[
            ModelLineageNodeResponse(
                id=n.id,
                node_type=n.node_type,
                stage=n.stage,
                label=n.label,
                created_at=n.created_at,
                parent_id=n.parent_id,
                dataset_id=n.dataset_id,
                metadata=n.metadata,
            )
            for n in graph.nodes
        ],
        edges=[ModelLineageEdgeResponse(source=e.source, target=e.target) for e in graph.edges],
    )


@router.get(
    "/versions/{version_id}/lineage",
    response_model=ApiResponse[ModelLineageResponse],
    summary="Get upstream data and training lineage DAG for a ModelVersion",
)
def get_model_version_lineage(
    version_id: UUID,
    project_id: UUID = Query(..., description="Project ID"),
    actor: ActorContext = Depends(get_actor_context),
    authz: AuthzService = Depends(get_authz_service),
    service: TrainingOrchestrationService = Depends(get_training_service),
) -> ApiResponse[ModelLineageResponse]:
    authz.require_project_scope(actor, "model:read", project_id)
    try:
        version = service.get_model_version(version_id)
        if version.project_id is None or version.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ModelVersion '{version_id}' not found in project '{project_id}'.",
            )
        authz.require_project_permission(actor, "model:read", project_id, owner_id=version.user_id)
        graph = service.get_model_version_lineage(version_id)
        return ApiResponse.ok(
            data=_to_model_lineage_response(graph),
            message="Model version lineage retrieved successfully",
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
    actor: ActorContext = Depends(get_actor_context),
    authz: AuthzService = Depends(get_authz_service),
    service: TrainingOrchestrationService = Depends(get_training_service),
    user_repo: IUserRepository = Depends(get_user_repo),
) -> ApiResponse[ModelVersionResponse]:
    try:
        existing = service.get_model_version(version_id)
        if existing.project_id is not None:
            authz.require_project_permission(
                actor, "deployment:deploy", existing.project_id, owner_id=existing.user_id, action="mutate"
            )
        else:
            authz.require_system_permission(actor, "model_builtin:manage")
        version = service.activate_model_version(
            version_id=version_id,
            decision_threshold=request.decision_threshold if request else None,
            description=request.description if request else None,
        )
        owner = resolve_owners(user_repo, [version.user_id]).get(version.user_id)
        return ApiResponse.ok(
            data=_to_model_version_response(version, owner=owner),
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
    actor: ActorContext = Depends(get_actor_context),
    authz: AuthzService = Depends(get_authz_service),
    service: TrainingOrchestrationService = Depends(get_training_service),
    user_repo: IUserRepository = Depends(get_user_repo),
) -> ApiResponse[TrainingRunResponse]:
    authz.require_project_permission(actor, "training:create", request.project_id, action="create")
    try:
        config = TrainingRunConfig(
            model_id=request.model_id,
            dataset_artifact_id=request.dataset_artifact_id,
            project_id=request.project_id,
            hyperparameters=request.hyperparameters,
            compute_target=request.compute_target,
            run_name=request.run_name,
        )
        run = service.prepare_and_dispatch(config=config, user_name=actor.username, user_id=actor.user_id)
        # Re-fetch run so post-execution metrics & version_id are reflected for synchronous dispatch
        updated_run = service.get_training_run(run.run_id)
        artifact_id = service.get_run_dataset_artifact_id(updated_run.run_id)
        owner = resolve_owners(user_repo, [updated_run.user_id]).get(updated_run.user_id)
        return ApiResponse.ok(
            data=_to_training_run_response(updated_run, dataset_artifact_id=artifact_id, owner=owner),
            status_code=status.HTTP_201_CREATED,
            message=f"Training run '{updated_run.run_name}' completed with status {updated_run.status}",
        )
    except ValueError as e:
        err_msg = str(e)
        code = status.HTTP_404_NOT_FOUND if "not found" in err_msg.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=err_msg)


@router.get(
    "/runs",
    response_model=ApiResponse[CursorPage[TrainingRunResponse]],
    summary="List training runs for a project with optional model_id filter and cursor pagination",
)
def list_training_runs(
    project_id: UUID = Query(..., description="Project ID"),
    model_id: Optional[UUID] = Query(None, description="Optional filter by Model ID"),
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: Optional[str] = Query(None, description="Opaque pagination cursor"),
    actor: ActorContext = Depends(get_actor_context),
    authz: AuthzService = Depends(get_authz_service),
    service: TrainingOrchestrationService = Depends(get_training_service),
    user_repo: IUserRepository = Depends(get_user_repo),
) -> ApiResponse[CursorPage[TrainingRunResponse]]:
    owner_filter = authz.resolve_project_list_owner(actor, "training:read", project_id)
    runs = [
        r
        for r in service.list_training_runs(model_id=model_id, project_id=project_id)
        if owner_filter is None or r.user_id == owner_filter
    ]
    page_items, next_cursor = paginate_cursor(
        runs,
        limit=limit,
        cursor=cursor,
        key_fn=lambda r: r.run_id,
    )
    owners = resolve_owners(user_repo, (r.user_id for r in page_items))
    return ApiResponse.ok(
        data=CursorPage(
            items=[
                _to_training_run_response(
                    r,
                    dataset_artifact_id=service.get_run_dataset_artifact_id(r.run_id),
                    owner=owners.get(r.user_id),
                )
                for r in page_items
            ],
            nextCursor=next_cursor,
        ),
        message=f"Retrieved {len(page_items)} training runs",
    )


@router.get(
    "/compute-targets",
    response_model=ApiResponse[ComputeTargetsResponse],
    summary="List available training compute targets and get an automatic recommendation (ISS-009)",
)
def get_compute_targets(
    project_id: UUID = Query(..., description="Project ID"),
    model_id: Optional[UUID] = Query(None, description="Optional target Model ID for recommendation"),
    dataset_artifact_id: Optional[UUID] = Query(
        None,
        description="Optional dataset artifact ID for recommendation",
    ),
    actor: ActorContext = Depends(get_actor_context),
    authz: AuthzService = Depends(get_authz_service),
    service: TrainingOrchestrationService = Depends(get_training_service),
) -> ApiResponse[ComputeTargetsResponse]:
    authz.require_project_permission(actor, "training:create", project_id, action="create")
    try:
        if model_id is not None:
            model = service.get_model(model_id)
            if model.project_id is not None and model.project_id != project_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Model '{model_id}' not found in project '{project_id}'.",
                )
            if model.project_id is not None:
                authz.require_project_permission(actor, "model:read", project_id, owner_id=model.user_id)

        if dataset_artifact_id is not None:
            artifact = service.dataset_artifact_repo.get_by_id(dataset_artifact_id)
            if artifact is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"DatasetArtifact '{dataset_artifact_id}' not found.",
                )
            if service.dataset_repo is not None:
                dataset = service.dataset_repo.get_by_id(artifact.dataset_id)
                if dataset is None or dataset.project_id != project_id:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"DatasetArtifact '{dataset_artifact_id}' not found in project '{project_id}'.",
                    )
                authz.require_project_permission(
                    actor,
                    "dataset:read",
                    project_id,
                    owner_id=dataset.user_id,
                )

        targets, recommendation = service.recommend_compute_target(
            model_id=model_id,
            dataset_artifact_id=dataset_artifact_id,
            requested_target="auto",
        )
        return ApiResponse.ok(
            data=ComputeTargetsResponse(
                targets=[
                    ComputeTargetOptionResponse(
                        target_id=t.target_id,
                        display_name=t.display_name,
                        provider_type=t.provider_type,
                        available=t.available,
                        reason=t.reason,
                        resource_tiers=t.resource_tiers,
                    )
                    for t in targets
                ],
                recommendation=ComputeRecommendationResponse(
                    requested_target=recommendation.requested_target,
                    resolved_target=recommendation.resolved_target,
                    resource_tier=recommendation.resource_tier,
                    provider=recommendation.provider,
                    selection_reason=recommendation.selection_reason,
                ),
            ),
            message="Compute targets retrieved successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


def _resolve_authz_in_session(
    session,
    authorization: Optional[str],
) -> tuple[ActorContext, AuthzService]:
    user_repo = SqlUserRepository(session)
    auth_service = get_auth_service(
        user_repo=user_repo,
        session_repo=SqlUserSessionRepository(session),
        role_repo=SqlRoleRepository(session),
        password_hasher=get_password_hasher(),
        token_provider=get_token_provider(),
    )
    current_user = get_current_user(
        authorization=authorization,
        auth_service=auth_service,
        user_repo=user_repo,
    )
    authz = build_authz_service(
        user_repo=user_repo,
        role_repo=SqlRoleRepository(session),
        permission_repo=SqlPermissionRepository(session),
        member_repo=SqlProjectMemberRepository(session),
    )
    actor = authz.get_actor_context(current_user.user_id)
    return actor, authz


def _get_training_run_with_session_poll(
    run_id: UUID,
    project_id: UUID,
    actor: ActorContext,
    authz: AuthzService,
    service: TrainingOrchestrationService,
    user_repo: IUserRepository,
) -> ApiResponse[TrainingRunResponse]:
    authz.require_project_scope(actor, "training:read", project_id)
    run = service.get_training_run(run_id)
    if run.project_id is None or run.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TrainingRun '{run_id}' not found in project '{project_id}'.",
        )
    authz.require_project_permission(actor, "training:read", project_id, owner_id=run.user_id)
    if run.status == TrainingRunStatus.RUNNING and run.external_job_id:
        try:
            run = service.sync_remote_run(run.run_id)
        except Exception:
            pass
    artifact_id = service.get_run_dataset_artifact_id(run.run_id)
    owner = resolve_owners(user_repo, [run.user_id]).get(run.user_id)
    return ApiResponse.ok(
        data=_to_training_run_response(run, dataset_artifact_id=artifact_id, owner=owner),
        message="Training run retrieved successfully",
    )


@router.get(
    "/runs/{run_id}",
    response_model=ApiResponse[TrainingRunResponse],
    summary="Get training run details and evaluation metrics by ID",
)
def get_training_run(
    run_id: UUID,
    project_id: UUID = Query(..., description="Project ID"),
    request: Request = None,
    authorization: Optional[str] = Header(default=None),
    storage: IFileStorage = Depends(get_storage),
    provider_registry: RemoteProviderRegistry = Depends(get_remote_provider_registry),
    compute_policy: ComputeSelectionPolicy = Depends(get_compute_selection_policy),
) -> ApiResponse[TrainingRunResponse]:
    overrides = getattr(getattr(request, "app", None), "dependency_overrides", {}) if request else {}
    session_factory = _server_deps._session_factory

    if session_factory is None or any(
        dep in overrides
        for dep in (get_training_service, get_actor_context, get_authz_service, get_user_repo)
    ):
        # Fallback for unit tests overriding service/auth dependencies without a real DB session factory
        try:
            if session_factory is not None:
                with session_scope(session_factory) as session:
                    actor, authz = _resolve_authz_in_session(session, authorization)
                    if get_actor_context in overrides:
                        actor = overrides[get_actor_context]()
                    if get_authz_service in overrides:
                        authz = overrides[get_authz_service]()
                    service = (
                        overrides[get_training_service]()
                        if get_training_service in overrides
                        else build_training_service_for_session(
                            session, storage, provider_registry, compute_policy
                        )
                    )
                    user_repo = (
                        overrides[get_user_repo]()
                        if get_user_repo in overrides
                        else SqlUserRepository(session)
                    )
                    return _get_training_run_with_session_poll(
                        run_id, project_id, actor, authz, service, user_repo
                    )
            service = overrides[get_training_service]()
            actor = overrides[get_actor_context]()
            authz = overrides[get_authz_service]()
            user_repo = overrides[get_user_repo]()
            return _get_training_run_with_session_poll(
                run_id, project_id, actor, authz, service, user_repo
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    try:
        # Phase 1: short DB session for authz + run snapshot; closes before network I/O
        poll_provider = None
        external_job_id: Optional[str] = None
        with session_scope(session_factory) as session:
            actor, authz = _resolve_authz_in_session(session, authorization)
            authz.require_project_scope(actor, "training:read", project_id)
            service = build_training_service_for_session(
                session, storage, provider_registry, compute_policy
            )
            run = service.get_training_run(run_id)
            if run.project_id is None or run.project_id != project_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"TrainingRun '{run_id}' not found in project '{project_id}'.",
                )
            authz.require_project_permission(actor, "training:read", project_id, owner_id=run.user_id)

            if run.status == TrainingRunStatus.RUNNING and run.external_job_id:
                provider_id = (
                    run.compute_metadata.get("provider")
                    if isinstance(run.compute_metadata, dict)
                    else None
                ) or run.compute_target
                if provider_id:
                    poll_provider = provider_registry.get(str(provider_id))
                    if poll_provider is not None:
                        external_job_id = run.external_job_id

            if poll_provider is None or external_job_id is None:
                artifact_id = service.get_run_dataset_artifact_id(run.run_id)
                owner = resolve_owners(SqlUserRepository(session), [run.user_id]).get(run.user_id)
                return ApiResponse.ok(
                    data=_to_training_run_response(run, dataset_artifact_id=artifact_id, owner=owner),
                    message="Training run retrieved successfully",
                )

        # Phase 2: network poll with NO DB session held open
        remote_status = None
        try:
            remote_status = poll_provider.poll(external_job_id)
        except Exception:
            # Best-effort on-demand sync; background RemoteTrainingPoller retries on transient failures.
            remote_status = None

        # Phase 3: short DB session to persist terminal state (if any) and read final DTO
        with session_scope(session_factory) as session:
            service = build_training_service_for_session(
                session, storage, provider_registry, compute_policy
            )
            if remote_status is not None and remote_status.state not in ("PENDING", "RUNNING"):
                run = service.apply_remote_status(run_id, remote_status)
            else:
                run = service.get_training_run(run_id)
            artifact_id = service.get_run_dataset_artifact_id(run.run_id)
            owner = resolve_owners(SqlUserRepository(session), [run.user_id]).get(run.user_id)
            return ApiResponse.ok(
                data=_to_training_run_response(run, dataset_artifact_id=artifact_id, owner=owner),
                message="Training run retrieved successfully",
            )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/runs/{run_id}/lineage",
    response_model=ApiResponse[ModelLineageResponse],
    summary="Get upstream data and training lineage DAG for a TrainingRun",
)
def get_training_run_lineage(
    run_id: UUID,
    project_id: UUID = Query(..., description="Project ID"),
    actor: ActorContext = Depends(get_actor_context),
    authz: AuthzService = Depends(get_authz_service),
    service: TrainingOrchestrationService = Depends(get_training_service),
) -> ApiResponse[ModelLineageResponse]:
    authz.require_project_scope(actor, "training:read", project_id)
    try:
        run = service.get_training_run(run_id)
        if run.project_id is None or run.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"TrainingRun '{run_id}' not found in project '{project_id}'.",
            )
        authz.require_project_permission(actor, "training:read", project_id, owner_id=run.user_id)
        graph = service.get_training_run_lineage(run_id)
        return ApiResponse.ok(
            data=_to_model_lineage_response(graph),
            message="Training run lineage retrieved successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


__all__ = ["router"]
