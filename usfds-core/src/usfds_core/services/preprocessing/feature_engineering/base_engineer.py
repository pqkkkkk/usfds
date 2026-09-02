from abc import ABC, abstractmethod
from typing import Any, Optional
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin


class BaseFeatureEngineer(BaseEstimator, TransformerMixin, ABC):
    """Abstract base class for scikit-learn compatible feature engineering transformers."""

    @abstractmethod
    def fit(self, X: Any, y: Optional[Any] = None) -> "BaseFeatureEngineer":
        """Learn parameters from the training set."""
        return self

    @abstractmethod
    def transform(self, X: Any) -> Any:
        """Apply feature engineering transformations to input data."""
        pass
