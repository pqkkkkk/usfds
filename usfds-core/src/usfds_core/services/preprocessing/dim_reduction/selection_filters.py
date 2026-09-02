from typing import Any, Optional
from sklearn.feature_selection import SelectKBest, f_classif, mutual_info_classif

from usfds_core.services.preprocessing.dim_reduction.base_reducer import BaseDimReducer


class SelectKBestMITransformer(BaseDimReducer):
    """Feature selection using Mutual Information score."""

    def __init__(self, k: int = 15, random_state: Optional[int] = 42):
        self.k = k
        self.random_state = random_state
        self.selector_: Optional[SelectKBest] = None

    def fit(self, X: Any, y: Optional[Any] = None) -> "SelectKBestMITransformer":
        def mi_scorer(x_in, y_in):
            return mutual_info_classif(x_in, y_in, random_state=self.random_state)

        self.selector_ = SelectKBest(score_func=mi_scorer, k=self.k)
        self.selector_.fit(X, y)
        return self

    def transform(self, X: Any) -> Any:
        if self.selector_ is None:
            raise RuntimeError("SelectKBestMITransformer is not fitted yet.")
        return self.selector_.transform(X)


class SelectKBestFScoreTransformer(BaseDimReducer):
    """Feature selection using ANOVA F-value score."""

    def __init__(self, k: int = 15):
        self.k = k
        self.selector_: Optional[SelectKBest] = None

    def fit(self, X: Any, y: Optional[Any] = None) -> "SelectKBestFScoreTransformer":
        self.selector_ = SelectKBest(score_func=f_classif, k=self.k)
        self.selector_.fit(X, y)
        return self

    def transform(self, X: Any) -> Any:
        if self.selector_ is None:
            raise RuntimeError("SelectKBestFScoreTransformer is not fitted yet.")
        return self.selector_.transform(X)


__all__ = [
    "SelectKBest",
    "SelectKBestMITransformer",
    "SelectKBestFScoreTransformer",
]
