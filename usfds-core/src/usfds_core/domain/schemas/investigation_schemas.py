"""Schemas and Data Transfer Objects for Fraud Case Investigation and Reporting."""

from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class CaseSummary(BaseModel):
    """Core transaction details merged with model inference score for triage."""
    event_id: int
    user_id: int
    amount: float
    avg_amount_user: Optional[float] = None
    total_transactions_user: Optional[int] = None
    account_age_days: Optional[int] = None
    country: Optional[str] = None
    bin_country: Optional[str] = None
    channel: Optional[str] = None
    merchant_category: Optional[str] = None
    promo_used: Optional[int] = None
    avs_match: Optional[int] = None
    cvv_result: Optional[int] = None
    three_ds_flag: Optional[int] = None
    shipping_distance_km: Optional[float] = None
    timestamp: Optional[str] = None
    y_prob: float = Field(..., description="Predicted fraud probability from ML model [0.0 - 1.0]")
    y_true: Optional[int] = Field(None, description="Actual historical ground truth label if known (0: normal, 1: fraud)")
    risk_level: str = Field(..., description="Severity band: LOW, MEDIUM, HIGH, CRITICAL")


class FeatureContribution(BaseModel):
    """Attribution score of an individual feature influencing the prediction."""
    feature_name: str
    display_name: str
    feature_value: Any
    importance_score: float = Field(..., description="Attribution value (e.g. SHAP score)")
    impact: str = Field(..., description="'INCREASES_RISK' or 'DECREASES_RISK'")
    description: Optional[str] = None


class FeatureExplanation(BaseModel):
    """Explainability output breaking down key drivers behind the model's score."""
    event_id: int
    base_value: float = Field(..., description="Baseline expected model value")
    prediction_score: float = Field(..., description="Final model probability output")
    top_risk_factors: List[FeatureContribution] = Field(
        default_factory=list, description="Top features pushing probability towards fraud"
    )
    top_mitigating_factors: List[FeatureContribution] = Field(
        default_factory=list, description="Top features pulling probability towards benign"
    )


class UserBaselineProfile(BaseModel):
    """Historical profile and behavioral baseline comparison for the cardholder."""
    user_id: int
    account_age_days: int
    total_transactions_history: int
    avg_amount_history: float
    max_amount_history: float
    frequent_merchant_categories: List[str] = Field(default_factory=list)
    known_countries: List[str] = Field(default_factory=list)
    amount_deviation_ratio: float = Field(
        1.0, description="Ratio of current transaction amount vs user's historical average"
    )
    is_new_country: bool = False
    is_new_merchant_category: bool = False


class RelatedCase(BaseModel):
    """A related or similar transaction identified during link analysis."""
    event_id: int
    user_id: int
    amount: float
    shipping_distance_km: Optional[float] = None
    country: Optional[str] = None
    bin_country: Optional[str] = None
    timestamp: Optional[str] = None
    y_prob: float
    y_true: Optional[int] = None
    similarity_reason: str = Field(
        ..., description="Description of the correlation (e.g., 'Same cardholder within 24h', 'Same unusual cross-border route')"
    )


class SARDraftPayload(BaseModel):
    """Structured draft of a Suspicious Activity Report (SAR)."""
    case_id: Optional[UUID] = None
    event_id: int
    subject_user_id: int
    suspicious_amount: float
    summary_narrative: str
    indicators_of_suspicion: List[str] = Field(default_factory=list)
    recommended_action: str = Field(
        ..., description="Recommended decision: 'APPROVE', 'STEP_UP_AUTH', 'DECLINE_HOLD', 'BLOCK_ACCOUNT'"
    )
    confidence_score: float = Field(
        ..., description="Agent's confidence score in the recommended conclusion [0.0 - 1.0]"
    )
