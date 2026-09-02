from abc import ABC, abstractmethod
from typing import Any, Optional
from sklearn.base import BaseEstimator, TransformerMixin


class BaseDimReducer(BaseEstimator, TransformerMixin, ABC):
    """Abstract base class for dimensionality reduction and feature selection estimators."""

    @abstractmethod
    def fit(self, X: Any, y: Optional[Any] = None) -> "BaseDimReducer":
        return self

    @abstractmethod
    def transform(self, X: Any) -> Any:
        pass
