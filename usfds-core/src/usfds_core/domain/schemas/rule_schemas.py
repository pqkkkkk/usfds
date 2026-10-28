from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from usfds_core.domain.entities.enums import RuleAction


@dataclass
class RuleExecutionContext:
    transaction_id: str
    raw_features: Optional[Dict[str, Any]] = None
    mapped_features: Optional[Dict[str, Any]] = None
    enriched_features: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.raw_features is None and self.mapped_features is not None:
            self.raw_features = dict(self.mapped_features)
        elif self.mapped_features is None and self.raw_features is not None:
            self.mapped_features = dict(self.raw_features)
        elif self.raw_features is None and self.mapped_features is None:
            self.raw_features = {}
            self.mapped_features = {}
        elif self.raw_features is not None and self.mapped_features is not None:
            merged = {**self.mapped_features, **self.raw_features}
            self.raw_features = dict(merged)
            self.mapped_features = dict(merged)
        if self.enriched_features is None:
            self.enriched_features = {}


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


@dataclass
class RuleBacktestSampleHit:
    event_id: str
    timestamp: str
    amount: float
    user_id: str
    ground_truth: Optional[int]
    matched_clauses: List[str]
    features: Dict[str, Any]


@dataclass
class RuleBacktestResult:
    rule_id: Optional[str]
    rule_version_id: Optional[str]
    version_number: int
    rule_code: str
    rule_name: str
    action: RuleAction
    dataset_artifact_id: str
    total_transactions: int
    total_hits: int
    hit_rate: float
    has_ground_truth: bool
    target_column: Optional[str]
    tp: int
    fp: int
    tn: int
    fn: int
    precision: float
    recall: float
    fpr: float
    fraud_amount_caught: float
    execution_time_ms: float
    avg_execution_time_ms: float
    sample_hits: List[RuleBacktestSampleHit] = field(default_factory=list)
