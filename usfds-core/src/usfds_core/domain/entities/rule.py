from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from .enums import RuleAction, RuleStatus


@dataclass(frozen=True)
class RuleVersion:
    """Represents an immutable version snapshot of a fraud detection business rule."""
    rule_id: UUID
    version_number: int
    condition: Dict[str, Any]  # JsonLogic expression
    action: RuleAction
    rule_version_id: UUID = field(default_factory=uuid4)
    change_summary: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Rule:
    """Represents a business rule container for fraud detection within a project."""
    project_id: UUID
    rule_code: str
    name: str
    description: str
    rule_id: UUID = field(default_factory=uuid4)
    status: RuleStatus = RuleStatus.ACTIVE
    current_version_id: Optional[UUID] = None
    created_by: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))