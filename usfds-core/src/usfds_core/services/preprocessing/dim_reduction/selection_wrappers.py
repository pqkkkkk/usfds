from typing import Any, Optional
from sklearn.feature_selection import RFE
from sklearn.linear_model import LogisticRegression

from usfds_core.services.preprocessing.dim_reduction.base_reducer import BaseDimReducer


class RFETransformer(BaseDimReducer):
    """Recursive Feature Elimination transformer using an estimator."""

    def __init__(self, n_features_to_select: Optional[int] = 15, estimator: Optional[Any] = None, step: int = 1):
        self.n_features_to_select = n_features_to_select
        self.estimator = estimator or LogisticRegression(max_iter=500)
        self.step = step
        self.rfe_: Optional[RFE] = None

    def fit(self, X: Any, y: Optional[Any] = None) -> "RFETransformer":
        self.rfe_ = RFE(
            estimator=self.estimator,
            n_features_to_select=self.n_features_to_select,
            step=self.step,
        )
        self.rfe_.fit(X, y)
        return self

    def transform(self, X: Any) -> Any:
        if self.rfe_ is None:
            raise RuntimeError("RFETransformer is not fitted yet.")
        return self.rfe_.transform(X)


__all__ = ["RFETransformer", "RFE"]
