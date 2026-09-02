from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union
from uuid import UUID, uuid4

from usfds_core.domain.entities.enums import DeploymentEnvironment, DeploymentStatus, RuleType


@dataclass
class Deployment:
    """Represents the deployment configuration for serving model inference."""
    version_id: UUID
    deployment_name: str
    environment: Union[DeploymentEnvironment, str]
    deployment_id: UUID = field(default_factory=uuid4)
    endpoint_url: Optional[str] = None
    serving_framework: Optional[str] = None
    replicas: int = 1
    status: Union[DeploymentStatus, str] = DeploymentStatus.PENDING
    traffic_percentage: int = 100
    deployed_by: Optional[str] = None
    deployed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Rule:
    """Represents a business rule for fraud detection within a project."""
    project_id: UUID
    rule_name: str
    rule_type: Union[RuleType, str]
    rule_id: UUID = field(default_factory=uuid4)
    rule_condition: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
