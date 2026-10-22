from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status

from usfds_core.domain.entities.enums import RuleStatus
from usfds_core.domain.entities.rule import Rule, RuleVersion
from usfds_core.domain.schemas.rule_schemas import RuleExecutionContext
from usfds_core.services.rule_engine.executor import RuleExecutor
from usfds_core.services.rule_engine.manager import RuleManager
from usfds_server.dependencies import get_rule_executor, get_rule_manager
from usfds_server.schemas.base_response import ApiResponse
from usfds_server.schemas.rule_api_schemas import (
    CreateRuleRequest,
    EvaluateRuleRequest,
    EvaluateRulesRequest,
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
