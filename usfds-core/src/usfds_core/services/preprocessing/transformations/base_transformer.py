from abc import ABC, abstractmethod
from typing import Any, Optional
from sklearn.base import BaseEstimator, TransformerMixin


class BaseDataTransformer(BaseEstimator, TransformerMixin, ABC):
    """Abstract base class for scikit-learn compatible data transformation estimators."""

    @abstractmethod
    def fit(self, X: Any, y: Optional[Any] = None) -> "BaseDataTransformer":
        return self

    @abstractmethod
    def transform(self, X: Any) -> Any:
        pass
