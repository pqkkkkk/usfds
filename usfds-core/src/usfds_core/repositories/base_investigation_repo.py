from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from uuid import UUID

from usfds_core.domain.entities.enums import InvestigationStatus
from usfds_core.domain.entities.investigation import InvestigationCase


class IInvestigationRepository(ABC):
    """Abstract interface for Investigation case persistence and analytical queries."""

    @abstractmethod
    def save_case(self, case: InvestigationCase) -> InvestigationCase:
        """Persist or update an investigation case."""
        pass

    @abstractmethod
    def get_case_by_id(self, case_id: UUID) -> Optional[InvestigationCase]:
        """Retrieve an investigation case by its unique case UUID."""
        pass

    @abstractmethod
    def get_case_by_event_id(self, event_id: int) -> Optional[InvestigationCase]:
        """Retrieve an investigation case by the transaction event ID."""
        pass

    @abstractmethod
    def list_cases(
        self,
        project_id: Optional[UUID] = None,
        status: Optional[InvestigationStatus] = None,
        limit: int = 50,
    ) -> List[InvestigationCase]:
        """List investigation cases filtered by project and/or status."""
        pass

    @abstractmethod
    def get_transaction_record(self, event_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve the raw transaction record along with its prediction score."""
        pass

    @abstractmethod
    def get_user_transaction_history(self, user_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve past transaction history for a specific user."""
        pass

    @abstractmethod
    def search_correlated_transactions(
        self, criteria: Dict[str, Any], limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search transactions matching specific correlation criteria (e.g. location, channel)."""
        pass
