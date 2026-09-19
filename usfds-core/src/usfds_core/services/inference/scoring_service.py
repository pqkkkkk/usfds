from typing import Any, Tuple, Union
import numpy as np
import pandas as pd


class ModelScorer:
    """Provides unified inference scoring with configurable decision threshold."""

    @staticmethod
    def predict_probabilities(model: Any, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """Extract continuous fraud probabilities P(fraud) from model.

        If model does not have predict_proba, falls back to decision_function or raw predictions.
        """
        if hasattr(model, "predict_proba"):
            probs = model.predict_proba(X)
            if hasattr(probs, "ndim") and probs.ndim >= 2 and probs.shape[1] >= 2:
                return probs[:, 1]
            elif hasattr(probs, "ndim") and probs.ndim >= 2 and probs.shape[1] == 1:
                return probs[:, 0]
            return np.asarray(probs)
        elif hasattr(model, "decision_function"):
            decision = model.decision_function(X)
            # Sigmoid normalization for decision scores
            return 1.0 / (1.0 + np.exp(-decision))
        elif hasattr(model, "predict"):
            preds = model.predict(X)
            return np.asarray(preds, dtype=float)
        else:
            raise ValueError(f"Model object {type(model)} has no predict or predict_proba method.")

    @staticmethod
    def predict(
        model: Any,
        X: Union[pd.DataFrame, np.ndarray],
        threshold: float = 0.5,
    ) -> np.ndarray:
        """Predict binary classification labels (0 or 1) using a custom decision threshold."""
        fraud_probs = ModelScorer.predict_probabilities(model, X)
        return (fraud_probs >= threshold).astype(int)

    @staticmethod
    def predict_with_probabilities(
        model: Any,
        X: Union[pd.DataFrame, np.ndarray],
        threshold: float = 0.5,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Predict both binary classification labels and continuous fraud probabilities."""
        fraud_probs = ModelScorer.predict_probabilities(model, X)
        preds = (fraud_probs >= threshold).astype(int)
        return preds, fraud_probs
