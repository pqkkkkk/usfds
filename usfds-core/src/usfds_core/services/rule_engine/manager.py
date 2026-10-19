from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4

from usfds_core.domain.entities.enums import RuleAction, RuleStatus
from usfds_core.domain.entities.rule import Rule, RuleVersion
from usfds_core.repositories.base_rule_repo import IRuleRepository, IRuleVersionRepository
from usfds_core.repositories.in_memory_repos import InMemoryRuleRepository, InMemoryRuleVersionRepository


class RuleManager:
    """
    Manages the lifecycle and versioning of fraud detection business rules.
    Encapsulates rule creation, updates (with automatic immutable version incrementing),
    status toggles, and retrieval of active rule-version pairs.
    """

    def __init__(
        self,
        rule_repo: Optional[IRuleRepository] = None,
        version_repo: Optional[IRuleVersionRepository] = None,
    ):
        self._rule_repo = rule_repo or InMemoryRuleRepository()
        self._version_repo = version_repo or InMemoryRuleVersionRepository()

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
