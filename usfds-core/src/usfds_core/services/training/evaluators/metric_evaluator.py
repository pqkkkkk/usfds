from typing import Any, Dict, Optional, Union
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


class MetricEvaluator:
    """Evaluator providing standardized metrics for fraud detection models."""

    @staticmethod
    def evaluate(
        y_true: Union[np.ndarray, list],
        y_pred: Union[np.ndarray, list],
        y_prob: Optional[Union[np.ndarray, list]] = None,
    ) -> Dict[str, Any]:
        """Compute standard and fraud-specific classification metrics.

        Calculates:
        - accuracy
        - precision
        - recall
        - f1_score
        - f2_score (weights recall 2x more than precision, essential for fraud)
        - pr_auc (Average Precision - golden metric for imbalanced fraud data)
        - roc_auc (if probabilities provided)
        - confusion_matrix (tn, fp, fn, tp)
        """
        y_true_arr = np.asarray(y_true)
        y_pred_arr = np.asarray(y_pred)

        metrics: Dict[str, Any] = {
            "accuracy": float(accuracy_score(y_true_arr, y_pred_arr)),
            "precision": float(precision_score(y_true_arr, y_pred_arr, zero_division=0)),
            "recall": float(recall_score(y_true_arr, y_pred_arr, zero_division=0)),
            "f1_score": float(f1_score(y_true_arr, y_pred_arr, zero_division=0)),
            "f2_score": float(fbeta_score(y_true_arr, y_pred_arr, beta=2, zero_division=0)),
        }

        # Confusion Matrix
        cm = confusion_matrix(y_true_arr, y_pred_arr, labels=[0, 1])
        if cm.shape == (2, 2):
            tn, fp, fn, tp = cm.ravel()
            metrics["confusion_matrix"] = {
                "tn": int(tn),
                "fp": int(fp),
                "fn": int(fn),
                "tp": int(tp),
            }

        # Probability-dependent metrics
        if y_prob is not None:
            y_prob_arr = np.asarray(y_prob)
            unique_classes = np.unique(y_true_arr)
            if len(unique_classes) > 1:
                try:
                    metrics["roc_auc"] = float(roc_auc_score(y_true_arr, y_prob_arr))
                except Exception:
                    metrics["roc_auc"] = None

                try:
                    metrics["pr_auc"] = float(average_precision_score(y_true_arr, y_prob_arr))
                except Exception:
                    metrics["pr_auc"] = None
            else:
                metrics["roc_auc"] = None
                metrics["pr_auc"] = None

        return metrics
