from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from usfds_core.domain.entities.rule import Rule, RuleVersion


class IRuleRepository(ABC):
    """Abstract interface for Rule entity persistence."""

    @abstractmethod
    def save(self, rule: Rule) -> Rule:
        """Persist or update a Rule."""
        pass

    @abstractmethod
    def get_by_id(self, rule_id: UUID) -> Optional[Rule]:
        """Retrieve a Rule by its ID."""
        pass

    @abstractmethod
    def get_by_code(self, project_id: UUID, rule_code: str) -> Optional[Rule]:
        """Retrieve a Rule by project ID and rule code."""
        pass

    @abstractmethod
    def list_by_project(self, project_id: UUID) -> List[Rule]:
        """List all rules for a given project."""
        pass

    @abstractmethod
    def delete(self, rule_id: UUID) -> bool:
        """Delete a Rule by its ID."""
        pass


class IRuleVersionRepository(ABC):
    """Abstract interface for RuleVersion persistence."""

    @abstractmethod
    def save(self, version: RuleVersion) -> RuleVersion:
        """Persist a RuleVersion snapshot."""
        pass

    @abstractmethod
    def get_by_id(self, rule_version_id: UUID) -> Optional[RuleVersion]:
        """Retrieve a RuleVersion by its ID."""
        pass

    @abstractmethod
    def get_latest_version(self, rule_id: UUID) -> Optional[RuleVersion]:
        """Retrieve the latest RuleVersion for a given rule."""
        pass

    @abstractmethod
    def list_by_rule(self, rule_id: UUID) -> List[RuleVersion]:
        """List all historical versions of a rule, ordered by version_number."""
        pass
