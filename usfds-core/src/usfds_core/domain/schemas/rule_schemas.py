from dataclasses import dataclass
from usfds_core.domain.entities.enums import RuleAction
from typing import Dict, Any

@dataclass
class RuleExecutionContext:
    transaction_id: str
    mapped_features: Dict[str, Any]
    enriched_features: Dict[str, Any]

@dataclass
class RuleExecutionResult:
    rule_id: str
    rule_version_id: str
    version_number: int
    rule_code: str
    rule_name: str
    is_triggered: bool
    action: RuleAction
    trigger_reason: str
    execution_time_ms: float