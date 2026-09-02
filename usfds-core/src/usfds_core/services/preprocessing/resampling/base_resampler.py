from abc import ABC, abstractmethod
from typing import Any, Tuple


class BaseResampler(ABC):
    """Abstract interface for imbalanced-learn compatible resamplers."""

    @abstractmethod
    def fit_resample(self, X: Any, y: Any) -> Tuple[Any, Any]:
        """Resample dataset to balance minority and majority classes."""
        pass
