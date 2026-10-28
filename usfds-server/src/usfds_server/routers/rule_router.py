import io
from pathlib import Path
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
import pandas as pd

from usfds_core.domain.entities.enums import RuleAction, RuleStatus
from usfds_core.domain.entities.rule import Rule, RuleVersion
from usfds_core.domain.schemas.rule_schemas import RuleExecutionContext
from usfds_core.services.rule_engine.executor import RuleExecutor
from usfds_core.services.rule_engine.manager import RuleManager
from usfds_infra.database import SqliteDatasetArtifactRepository, SqliteDatasetRepository
from usfds_infra.storage.local_storage import LocalFileStorage
from usfds_server.dependencies import (
    get_artifact_repo,
    get_dataset_repo,
    get_rule_executor,
    get_rule_manager,
    get_storage,
)
from usfds_server.schemas.base_response import ApiResponse
from usfds_server.schemas.rule_api_schemas import (
    BacktestRuleRequest,
    CreateRuleRequest,
    EvaluateRuleRequest,
    EvaluateRulesRequest,
    RuleBacktestResultResponse,
    RuleBacktestSampleHitResponse,
    RuleExecutionResultResponse,
    RuleResponse,
    RuleVersionResponse,
    SetRuleStatusRequest,
    UpdateRuleRequest,
)

router = APIRouter(prefix="/api/v1/rules", tags=["Rule Engine"])


def _to_rule_version_response(version: RuleVersion) -> RuleVersionResponse:
    return RuleVersionResponse(
        rule_version_id=version.rule_version_id,
        rule_id=version.rule_id,
        version_number=version.version_number,
        condition=version.condition,
        action=version.action,
        change_summary=version.change_summary,
        created_by=version.created_by,
        created_at=version.created_at,
    )


def _to_rule_response(rule: Rule, current_version: Optional[RuleVersion] = None) -> RuleResponse:
    version_resp = _to_rule_version_response(current_version) if current_version else None
    return RuleResponse(
        rule_id=rule.rule_id,
        project_id=rule.project_id,
        rule_code=rule.rule_code,
        name=rule.name,
        description=rule.description,
        status=rule.status,
        current_version_id=rule.current_version_id,
        current_version=version_resp,
        created_by=rule.created_by,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


# ==========================================
# Rule Lifecycle Endpoints
# ==========================================

@router.post(
    "",
    response_model=ApiResponse[RuleResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new business rule with initial version (v1)",
)
def create_rule(
    request: CreateRuleRequest,
    manager: RuleManager = Depends(get_rule_manager),
) -> ApiResponse[RuleResponse]:
    try:
        rule, version = manager.create_rule(
            project_id=request.project_id,
            rule_code=request.rule_code,
            name=request.name,
            description=request.description or "",
            condition=request.condition,
            action=request.action,
            created_by=request.created_by,
            change_summary=request.change_summary,
            status=request.status,
        )
        return ApiResponse.ok(
            data=_to_rule_response(rule, version),
            message=f"Rule '{rule.rule_code}' successfully created",
            status_code=status.HTTP_201_CREATED,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "",
    response_model=ApiResponse[List[RuleResponse]],
    summary="List rules by project with optional status filter",
)
def list_rules(
    project_id: UUID = Query(..., description="Project ID to query rules for"),
    rule_status: Optional[RuleStatus] = Query(None, alias="status", description="Filter by ACTIVE / INACTIVE / DRAFT"),
    manager: RuleManager = Depends(get_rule_manager),
) -> ApiResponse[List[RuleResponse]]:
    rules = manager.get_rules_by_project(project_id, status=rule_status)
    rule_responses = []
    for r in rules:
        _, current_ver = manager.get_rule_with_current_version(r.rule_id)
        rule_responses.append(_to_rule_response(r, current_ver))

    return ApiResponse.ok(data=rule_responses, message=f"Retrieved {len(rule_responses)} rules")


@router.get(
    "/{rule_id}",
    response_model=ApiResponse[RuleResponse],
    summary="Get rule details and current active version by ID",
)
def get_rule(
    rule_id: UUID,
    manager: RuleManager = Depends(get_rule_manager),
) -> ApiResponse[RuleResponse]:
    pair = manager.get_rule_with_current_version(rule_id)
    if not pair:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rule not found with ID {rule_id}")
    rule, version = pair
    return ApiResponse.ok(data=_to_rule_response(rule, version))


@router.put(
    "/{rule_id}",
    response_model=ApiResponse[RuleResponse],
    summary="Update rule metadata or conditions (auto-increments version if logic changed)",
)
def update_rule(
    rule_id: UUID,
    request: UpdateRuleRequest,
    manager: RuleManager = Depends(get_rule_manager),
) -> ApiResponse[RuleResponse]:
    try:
        rule, version = manager.update_rule(
            rule_id=rule_id,
            name=request.name,
            description=request.description,
            condition=request.condition,
            action=request.action,
            change_summary=request.change_summary,
            created_by=request.created_by,
        )
        # Fetch current version if logic was not changed
        if not version and rule.current_version_id:
            _, version = manager.get_rule_with_current_version(rule.rule_id)

        return ApiResponse.ok(
            data=_to_rule_response(rule, version),
            message=f"Rule '{rule.rule_code}' successfully updated",
        )
    except ValueError as e:
        err_msg = str(e)
        code = status.HTTP_404_NOT_FOUND if "not found" in err_msg.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=err_msg)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.patch(
    "/{rule_id}/status",
    response_model=ApiResponse[RuleResponse],
    summary="Set rule status (e.g. ACTIVE <-> INACTIVE)",
)
def set_rule_status(
    rule_id: UUID,
    request: SetRuleStatusRequest,
    manager: RuleManager = Depends(get_rule_manager),
) -> ApiResponse[RuleResponse]:
    try:
        rule = manager.set_rule_status(rule_id, request.status)
        _, current_ver = manager.get_rule_with_current_version(rule.rule_id)
        return ApiResponse.ok(
            data=_to_rule_response(rule, current_ver),
            message=f"Rule status updated to {request.status}",
        )
    except ValueError as e:
        err_msg = str(e)
        code = status.HTTP_404_NOT_FOUND if "not found" in err_msg.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=err_msg)


@router.get(
    "/{rule_id}/versions",
    response_model=ApiResponse[List[RuleVersionResponse]],
    summary="Get complete historical audit trail of rule versions",
)
def get_rule_versions(
    rule_id: UUID,
    manager: RuleManager = Depends(get_rule_manager),
) -> ApiResponse[List[RuleVersionResponse]]:
    rule = manager.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rule not found with ID {rule_id}")

    versions = manager.get_rule_versions(rule_id)
    data = [_to_rule_version_response(v) for v in versions]
    return ApiResponse.ok(data=data, message=f"Retrieved {len(data)} versions")


@router.delete(
    "/{rule_id}",
    response_model=ApiResponse[bool],
    summary="Delete a rule and all its versions",
)
def delete_rule(
    rule_id: UUID,
    manager: RuleManager = Depends(get_rule_manager),
) -> ApiResponse[bool]:
    deleted = manager.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rule not found with ID {rule_id}")
    return ApiResponse.ok(data=True, message=f"Rule {rule_id} deleted successfully")


# ==========================================
# Rule Execution / Evaluation Endpoints
# ==========================================

@router.post(
    "/{rule_id}/evaluate",
    response_model=ApiResponse[RuleExecutionResultResponse],
    summary="Evaluate a single rule against a transaction context",
)
def evaluate_single_rule(
    rule_id: UUID,
    request: EvaluateRuleRequest,
    version_id: Optional[UUID] = Query(None, description="Optional specific RuleVersion ID to evaluate. Defaults to current active version."),
    manager: RuleManager = Depends(get_rule_manager),
    executor: RuleExecutor = Depends(get_rule_executor),
) -> ApiResponse[RuleExecutionResultResponse]:
    rule = manager.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rule not found with ID {rule_id}")

    target_version = None
    if version_id:
        target_version = manager._version_repo.get_by_id(version_id)
    elif rule.current_version_id:
        target_version = manager._version_repo.get_by_id(rule.current_version_id)

    if not target_version:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid rule version found to evaluate")

    ctx = RuleExecutionContext(
        transaction_id=request.transaction_id,
        raw_features=request.raw_features,
        mapped_features=request.mapped_features,
        enriched_features=request.enriched_features,
    )

    result = executor.evaluate_rule(rule, target_version, ctx)

    response_data = RuleExecutionResultResponse(
        rule_id=result.rule_id,
        rule_version_id=result.rule_version_id,
        version_number=result.version_number,
        rule_code=result.rule_code,
        rule_name=result.rule_name,
        is_triggered=result.is_triggered,
        action=result.action,
        trigger_reason=result.trigger_reason,
        execution_time_ms=result.execution_time_ms,
    )
    return ApiResponse.ok(data=response_data, message="Evaluation completed")


@router.post(
    "/evaluate-batch",
    response_model=ApiResponse[List[RuleExecutionResultResponse]],
    summary="Evaluate all active rules of a project against a transaction context",
)
def evaluate_project_rules(
    request: EvaluateRulesRequest,
    manager: RuleManager = Depends(get_rule_manager),
    executor: RuleExecutor = Depends(get_rule_executor),
) -> ApiResponse[List[RuleExecutionResultResponse]]:
    active_pairs = manager.get_active_rules_with_versions(request.project_id)
    if not active_pairs:
        return ApiResponse.ok(data=[], message="No active rules configured for this project")

    ctx = RuleExecutionContext(
        transaction_id=request.transaction_id,
        raw_features=request.raw_features,
        mapped_features=request.mapped_features,
        enriched_features=request.enriched_features,
    )

    results = executor.evaluate_rules(active_pairs, ctx)

    responses = [
        RuleExecutionResultResponse(
            rule_id=r.rule_id,
            rule_version_id=r.rule_version_id,
            version_number=r.version_number,
            rule_code=r.rule_code,
            rule_name=r.rule_name,
            is_triggered=r.is_triggered,
            action=r.action,
            trigger_reason=r.trigger_reason,
            execution_time_ms=r.execution_time_ms,
        )
        for r in results
    ]
    return ApiResponse.ok(data=responses, message=f"Evaluated {len(responses)} active rules")


def _load_artifact_dataframe(
    artifact_path: str,
    storage: LocalFileStorage,
) -> pd.DataFrame:
    """Loads a DataFrame (Parquet or CSV) from LocalFileStorage or local filesystem."""
    raw_bytes: Optional[bytes] = None
    if storage.exists(artifact_path):
        raw_bytes = storage.read_bytes(artifact_path)
    else:
        local_p = Path(artifact_path)
        if local_p.is_file():
            raw_bytes = local_p.read_bytes()

    if raw_bytes is None:
        raise FileNotFoundError(f"Dataset artifact file not found at '{artifact_path}'")

    lower_path = artifact_path.lower()
    if lower_path.endswith(".csv"):
        return pd.read_csv(io.BytesIO(raw_bytes))
    return pd.read_parquet(io.BytesIO(raw_bytes))


@router.post(
    "/backtest",
    response_model=ApiResponse[RuleBacktestResultResponse],
    summary="Run historical dry-run/backtest of a rule or ad-hoc condition on a DatasetArtifact (SUC-12)",
)
def backtest_rule_on_dataset(
    request: BacktestRuleRequest,
    manager: RuleManager = Depends(get_rule_manager),
    executor: RuleExecutor = Depends(get_rule_executor),
    dataset_repo: SqliteDatasetRepository = Depends(get_dataset_repo),
    artifact_repo: SqliteDatasetArtifactRepository = Depends(get_artifact_repo),
    storage: LocalFileStorage = Depends(get_storage),
) -> ApiResponse[RuleBacktestResultResponse]:
    # 1. Verify DatasetArtifact & project ownership (BR-PM-06)
    artifact = artifact_repo.get_by_id(request.dataset_artifact_id)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DatasetArtifact '{request.dataset_artifact_id}' not found",
        )

    dataset = dataset_repo.get_by_id(artifact.dataset_id)
    if dataset and str(dataset.project_id) != str(request.project_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="DatasetArtifact does not belong to the specified project (BR-PM-06)",
        )

    # 2. Resolve Rule & RuleVersion or ad-hoc condition
    rule_id_str: Optional[str] = None
    rule_version_id_str: Optional[str] = None
    version_number: int = 1
    rule_code = request.rule_code or "AD_HOC"
    rule_name = request.rule_name or "Ad-hoc Rule"
    condition = request.condition
    action = request.action or RuleAction.REVIEW

    if request.rule_id:
        rule = manager.get_rule(request.rule_id)
        if not rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Rule not found with ID {request.rule_id}",
            )
        if str(rule.project_id) != str(request.project_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rule does not belong to the specified project (BR-PM-06)",
            )
        rule_id_str = str(rule.rule_id)
        rule_code = request.rule_code or rule.rule_code
        rule_name = request.rule_name or rule.name

        target_ver: Optional[RuleVersion] = None
        if request.version_id:
            target_ver = manager._version_repo.get_by_id(request.version_id)
        elif rule.current_version_id:
            target_ver = manager._version_repo.get_by_id(rule.current_version_id)

        if target_ver:
            rule_version_id_str = str(target_ver.rule_version_id)
            version_number = target_ver.version_number
            if condition is None:
                condition = target_ver.condition
            if request.action is None:
                action = target_ver.action

    if not condition or not isinstance(condition, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid JsonLogic condition (or saved rule_id with a condition) is required for backtesting",
        )

    # 3. Resolve physical path from DatasetArtifact (handle single file or train+test split)
    output_paths = artifact.output_paths or {}
    dfs: List[pd.DataFrame] = []
    try:
        if output_paths.get("train") and output_paths.get("test"):
            dfs.append(_load_artifact_dataframe(output_paths["train"], storage))
            dfs.append(_load_artifact_dataframe(output_paths["test"], storage))
        else:
            primary_path = (
                output_paths.get("mapped")
                or output_paths.get("raw")
                or output_paths.get("train")
                or artifact.storage_path
            )
            dfs.append(_load_artifact_dataframe(primary_path, storage))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read dataset artifact data: {e}",
        )

    df = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]

    # 4. Run backtest
    bt_result = executor.backtest_dataframe(
        df=df,
        condition=condition,
        action=action,
        dataset_artifact_id=str(request.dataset_artifact_id),
        rule_id=rule_id_str,
        rule_version_id=rule_version_id_str,
        version_number=version_number,
        rule_code=rule_code,
        rule_name=rule_name,
        target_column=request.target_column,
        amount_column=request.amount_column,
        max_samples=request.max_samples,
    )

    resp = RuleBacktestResultResponse(
        rule_id=bt_result.rule_id,
        rule_version_id=bt_result.rule_version_id,
        version_number=bt_result.version_number,
        rule_code=bt_result.rule_code,
        rule_name=bt_result.rule_name,
        action=bt_result.action,
        dataset_artifact_id=bt_result.dataset_artifact_id,
        total_transactions=bt_result.total_transactions,
        total_hits=bt_result.total_hits,
        hit_rate=bt_result.hit_rate,
        has_ground_truth=bt_result.has_ground_truth,
        target_column=bt_result.target_column,
        tp=bt_result.tp,
        fp=bt_result.fp,
        tn=bt_result.tn,
        fn=bt_result.fn,
        precision=bt_result.precision,
        recall=bt_result.recall,
        fpr=bt_result.fpr,
        fraud_amount_caught=bt_result.fraud_amount_caught,
        execution_time_ms=bt_result.execution_time_ms,
        avg_execution_time_ms=bt_result.avg_execution_time_ms,
        sample_hits=[
            RuleBacktestSampleHitResponse(
                event_id=s.event_id,
                timestamp=s.timestamp,
                amount=s.amount,
                user_id=s.user_id,
                ground_truth=s.ground_truth,
                matched_clauses=s.matched_clauses,
                features=s.features,
            )
            for s in bt_result.sample_hits
        ],
    )
    return ApiResponse.ok(data=resp, message="Rule backtest simulation completed")

