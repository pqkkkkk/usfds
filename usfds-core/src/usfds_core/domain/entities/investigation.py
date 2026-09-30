from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union
from uuid import UUID, uuid4

from usfds_core.domain.entities.enums import InvestigationStatus, RiskLevel


@dataclass
class InvestigationCase:
    """Represents a fraud alert investigation case tracked by the system."""
    project_id: UUID
    event_id: int
    case_id: UUID = field(default_factory=uuid4)
    assigned_to: Optional[UUID] = None
    status: Union[InvestigationStatus, str] = InvestigationStatus.PENDING
    risk_level: Union[RiskLevel, str] = RiskLevel.MEDIUM
    fraud_probability: Optional[float] = None
    
    # Audit & human-in-the-loop fields
    analyst_notes: Optional[str] = None
    action_taken: Optional[str] = None  # e.g., "APPROVE", "STEP_UP_AUTH", "BLOCK", "REFUND"
    sar_narrative: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
