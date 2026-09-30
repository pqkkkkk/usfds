"""Core Investigation Service implementation for USFDS.
Provides Dual-Use methods used by both REST API endpoints and AI Agent tools.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from uuid import UUID, uuid4

from usfds_core.domain.entities.enums import InvestigationStatus, RiskLevel
from usfds_core.domain.entities.investigation import InvestigationCase
from usfds_core.domain.schemas.investigation_schemas import (
    CaseSummary,
    FeatureExplanation,
    RelatedCase,
    SARDraftPayload,
    UserBaselineProfile,
)
from usfds_core.repositories.base_investigation_repo import IInvestigationRepository
from usfds_core.services.investigation.duckdb_engine import DuckDBInvestigationEngine
from usfds_core.services.investigation.explainability import ModelExplainabilityService


class IInvestigationService(ABC):
    """Abstract interface for Investigation Service."""

    @abstractmethod
    def get_case_summary(self, event_id: int) -> CaseSummary:
        """Retrieves full transaction context merged with model prediction score."""
        pass

    @abstractmethod
    def explain_prediction(self, event_id: int, top_k: int = 5) -> FeatureExplanation:
        """Computes feature attribution (SHAP values) explaining why the model flagged this transaction."""
        pass

    @abstractmethod
    def get_user_baseline(self, user_id: int, current_event_id: Optional[int] = None) -> UserBaselineProfile:
        """Retrieves cardholder historical spending patterns and computes behavioral deviation metrics."""
        pass

    @abstractmethod
    def search_related_cases(self, event_id: int, limit: int = 5) -> List[RelatedCase]:
        """Performs link analysis to identify correlated transactions."""
        pass

    @abstractmethod
    def save_case_decision(
        self,
        event_id: int,
        status: InvestigationStatus,
        analyst_notes: Optional[str] = None,
        action_taken: Optional[str] = None,
        sar_draft: Optional[SARDraftPayload] = None,
    ) -> InvestigationCase:
        """Persists the final investigation decision and SAR narrative."""
        pass


class InvestigationService(IInvestigationService):
    """Concrete implementation of InvestigationService.
    Integrates DuckDB for zero-copy Parquet analytics and SHAP for model explainability.
    """

    def __init__(
        self,
        test_enriched_path: str,
        eval_predictions_path: str,
        test_processed_path: str,
        model_artifact_path: str,
        pipeline_artifact_path: str,
        train_enriched_path: Optional[str] = None,
        repository: Optional[IInvestigationRepository] = None,
    ):
        self.repository = repository
        self.duckdb_engine = DuckDBInvestigationEngine(
            test_enriched_path=test_enriched_path,
            eval_predictions_path=eval_predictions_path,
            train_enriched_path=train_enriched_path,
        )
        self.explainability_service = ModelExplainabilityService(
            model_artifact_path=model_artifact_path,
            pipeline_artifact_path=pipeline_artifact_path,
            test_processed_path=test_processed_path,
        )

    def get_case_summary(self, event_id: int) -> CaseSummary:
        """Retrieves transaction details and model score for the case."""
        case = self.duckdb_engine.get_case_summary(event_id)
        if not case:
            raise ValueError(f"Transaction with event_id {event_id} not found in evaluation dataset.")
        return case

    def explain_prediction(self, event_id: int, top_k: int = 5) -> FeatureExplanation:
        """Computes feature attribution explaining model score."""
        case = self.get_case_summary(event_id)
        row_idx = self.duckdb_engine.get_row_index_by_event_id(event_id)
        if row_idx is None:
            raise ValueError(f"Row index for event_id {event_id} not found.")

        return self.explainability_service.explain_prediction(
            event_id=event_id,
            row_index=row_idx,
            y_prob=case.y_prob,
            top_k=top_k,
        )

    def get_user_baseline(self, user_id: int, current_event_id: Optional[int] = None) -> UserBaselineProfile:
        """Extracts customer behavioral baseline and deviation metrics."""
        return self.duckdb_engine.get_user_baseline(
            user_id=user_id, current_event_id=current_event_id
        )

    def search_related_cases(self, event_id: int, limit: int = 5) -> List[RelatedCase]:
        """Searches correlated transactions for link analysis."""
        return self.duckdb_engine.search_related_cases(event_id=event_id, limit=limit)

    def save_case_decision(
        self,
        event_id: int,
        status: InvestigationStatus,
        analyst_notes: Optional[str] = None,
        action_taken: Optional[str] = None,
        sar_draft: Optional[SARDraftPayload] = None,
    ) -> InvestigationCase:
        """Persists the investigation outcome and audit log."""
        case_summary = self.get_case_summary(event_id)
        risk_level = RiskLevel(case_summary.risk_level) if hasattr(RiskLevel, case_summary.risk_level) else RiskLevel.MEDIUM

        case_entity = InvestigationCase(
            project_id=uuid4(),  # default project context
            event_id=event_id,
            status=status,
            risk_level=risk_level,
            fraud_probability=case_summary.y_prob,
            analyst_notes=analyst_notes,
            action_taken=action_taken,
            sar_narrative=sar_draft.summary_narrative if sar_draft else None,
            resolved_at=datetime.now(timezone.utc),
        )

        if self.repository:
            return self.repository.save_case(case_entity)

        return case_entity
