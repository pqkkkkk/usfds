from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4

from usfds_core.domain.entities.enums import ProjectStatus, RuleAction, RuleStatus
from usfds_core.domain.entities.rule import Rule, RuleVersion
from usfds_core.repositories.base_project_repo import IProjectRepository
from usfds_core.repositories.base_rule_repo import IRuleRepository, IRuleVersionRepository
from usfds_core.repositories.in_memory_repos import InMemoryRuleRepository, InMemoryRuleVersionRepository
from usfds_core.services.project_management.schema_validator import ProjectSchemaValidator


class RuleManager:
    """
    Manages the lifecycle and versioning of fraud detection business rules.
    Encapsulates rule creation, updates (with automatic immutable version incrementing),
    status toggles, project RAW schema validation (BR-PM-04, BR-PM-05), and retrieval of active rule-version pairs.
    """

    def __init__(
        self,
        rule_repo: Optional[IRuleRepository] = None,
        version_repo: Optional[IRuleVersionRepository] = None,
        project_repo: Optional[IProjectRepository] = None,
    ):
        self._rule_repo = rule_repo or InMemoryRuleRepository()
        self._version_repo = version_repo or InMemoryRuleVersionRepository()
        self._project_repo = project_repo

    def _validate_against_project_schema(
        self,
        project_id: UUID,
        condition: Optional[Dict[str, Any]],
        target_status: RuleStatus,
    ) -> None:
        """Enforces BR-PM-04 and BR-PM-05 when the rule belongs to a registered Project."""
        if self._project_repo is None:
            return
        project = self._project_repo.get_by_id(project_id)
        if project is None:
            return

        proj_status = (
            project.status.value
            if hasattr(project.status, "value")
            else str(project.status)
        )
        if proj_status == ProjectStatus.ARCHIVED.value:
            raise ValueError(
                f"Không thể chỉnh sửa Rule trong dự án '{project.project_name}' vì dự án đang ở trạng thái ARCHIVED."
            )

        status_val = (
            target_status.value
            if hasattr(target_status, "value")
            else str(target_status)
        )
        if not project.is_schema_locked:
            if status_val == RuleStatus.ACTIVE.value:
                raise ValueError(
                    "Dự án chưa có RAW schema (chưa tải lên tập dữ liệu đầu tiên). "
                    "Không thể tạo hoặc kích hoạt Rule ở trạng thái ACTIVE (BR-PM-04)."
                )
        else:
            if condition is not None:
                errors = ProjectSchemaValidator.validate_rule_condition(
                    condition, project.raw_schema
                )
                if errors:
                    raise ValueError(" ".join(errors))

    def create_rule(
        self,
        project_id: Union[UUID, str],
        rule_code: str,
        name: str,
        description: str,
        condition: Dict[str, Any],
        action: RuleAction,
        created_by: Optional[str] = None,
        change_summary: Optional[str] = "Initial rule creation",
        status: RuleStatus = RuleStatus.ACTIVE,
    ) -> Tuple[Rule, RuleVersion]:
        """
        Create a new business rule along with its initial version (version 1).
        Ensures rule_code uniqueness within the project.
        """
        proj_uuid = UUID(str(project_id))

        # Check unique rule code in project
        existing = self._rule_repo.get_by_code(proj_uuid, rule_code)
        if existing:
            raise ValueError(f"Rule with code '{rule_code}' already exists in project {proj_uuid}")

        # Validate condition and status against project's RAW schema (BR-PM-04 & BR-PM-05)
        self._validate_against_project_schema(proj_uuid, condition, status)

        rule_id = uuid4()
        now = datetime.now(timezone.utc)

        # 1. Save Rule container first (so rule_id exists for foreign key constraint)
        rule = Rule(
            rule_id=rule_id,
            project_id=proj_uuid,
            rule_code=rule_code,
            name=name,
            description=description,
            status=status,
            current_version_id=None,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        saved_rule = self._rule_repo.save(rule)

        # 2. Save initial version (Version 1) referencing saved rule_id
        initial_version = RuleVersion(
            rule_id=rule_id,
            version_number=1,
            condition=condition,
            action=action,
            change_summary=change_summary,
            created_by=created_by,
            created_at=now,
        )
        saved_version = self._version_repo.save(initial_version)

        # 3. Update Rule container pointing to initial version
        saved_rule.current_version_id = saved_version.rule_version_id
        saved_rule = self._rule_repo.save(saved_rule)

        return saved_rule, saved_version

    def update_rule(
        self,
        rule_id: Union[UUID, str],
        name: Optional[str] = None,
        description: Optional[str] = None,
        condition: Optional[Dict[str, Any]] = None,
        action: Optional[RuleAction] = None,
        change_summary: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> Tuple[Rule, Optional[RuleVersion]]:
        """
        Update a rule. If condition or action is changed, a new immutable RuleVersion (N+1)
        is created and current_version_id is updated.
        If only metadata (name, description) is changed, only the Rule container is updated.
        """
        r_uuid = UUID(str(rule_id))
        rule = self._rule_repo.get_by_id(r_uuid)
        if not rule:
            raise ValueError(f"Rule not found with ID {r_uuid}")

        new_version: Optional[RuleVersion] = None
        now = datetime.now(timezone.utc)

        # Check if logic has changed -> requires a new RuleVersion
        if condition is not None or action is not None:
            latest_version = self._version_repo.get_latest_version(r_uuid)
            next_version_num = (latest_version.version_number + 1) if latest_version else 1

            new_condition = condition if condition is not None else (latest_version.condition if latest_version else {})
            new_action = action if action is not None else (latest_version.action if latest_version else RuleAction.REVIEW)

            # Validate updated condition against project's RAW schema (BR-PM-05)
            self._validate_against_project_schema(rule.project_id, new_condition, rule.status)

            new_version = RuleVersion(
                rule_id=r_uuid,
                version_number=next_version_num,
                condition=new_condition,
                action=new_action,
                change_summary=change_summary or f"Updated to version {next_version_num}",
                created_by=created_by,
                created_at=now,
            )
            saved_version = self._version_repo.save(new_version)
            rule.current_version_id = saved_version.rule_version_id

        if name is not None:
            rule.name = name
        if description is not None:
            rule.description = description
        rule.updated_at = now

        saved_rule = self._rule_repo.save(rule)
        return saved_rule, new_version

    def set_rule_status(
        self,
        rule_id: Union[UUID, str],
        status: RuleStatus,
    ) -> Rule:
        """
        Change status of a rule (e.g. ACTIVE <-> INACTIVE).
        """
        r_uuid = UUID(str(rule_id))
        rule = self._rule_repo.get_by_id(r_uuid)
        if not rule:
            raise ValueError(f"Rule not found with ID {r_uuid}")

        latest_version = self._version_repo.get_latest_version(r_uuid)
        current_cond = latest_version.condition if latest_version else None
        self._validate_against_project_schema(rule.project_id, current_cond, status)

        rule.status = status
        rule.updated_at = datetime.now(timezone.utc)
        return self._rule_repo.save(rule)

    def get_rule(self, rule_id: Union[UUID, str]) -> Optional[Rule]:
        """
        Retrieve a Rule container by ID.
        """
        return self._rule_repo.get_by_id(UUID(str(rule_id)))

    def get_rule_with_current_version(
        self,
        rule_id: Union[UUID, str],
    ) -> Optional[Tuple[Rule, Optional[RuleVersion]]]:
        """
        Retrieve a Rule along with its current active RuleVersion.
        """
        rule = self.get_rule(rule_id)
        if not rule:
            return None
        version = self._version_repo.get_by_id(rule.current_version_id) if rule.current_version_id else None
        return rule, version

    def get_rules_by_project(
        self,
        project_id: Union[UUID, str],
        status: Optional[RuleStatus] = None,
    ) -> List[Rule]:
        """
        List all rules within a project, optionally filtered by status.
        """
        rules = self._rule_repo.list_by_project(UUID(str(project_id)))
        if status:
            rules = [r for r in rules if r.status == status]
        return rules

    def get_active_rules_with_versions(
        self,
        project_id: Union[UUID, str],
    ) -> List[Tuple[Rule, RuleVersion]]:
        """
        Retrieve all ACTIVE rules paired with their current RuleVersion.
        Ready to be passed directly to RuleExecutor.evaluate_rules().
        """
        active_rules = self.get_rules_by_project(project_id, status=RuleStatus.ACTIVE)
        pairs: List[Tuple[Rule, RuleVersion]] = []

        for rule in active_rules:
            if rule.current_version_id:
                version = self._version_repo.get_by_id(rule.current_version_id)
                if version:
                    pairs.append((rule, version))
        return pairs

    def get_rule_versions(
        self,
        rule_id: Union[UUID, str],
    ) -> List[RuleVersion]:
        """
        Retrieve complete version history for a given rule.
        """
        return self._version_repo.list_by_rule(UUID(str(rule_id)))

    def delete_rule(self, rule_id: Union[UUID, str]) -> bool:
        """
        Delete a rule.
        """
        return self._rule_repo.delete(UUID(str(rule_id)))
