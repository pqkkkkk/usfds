from typing import Any, Dict, List, Optional, Union
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)


class MetricEvaluator:
    """Evaluator providing standardized and interactive visual metrics for fraud detection models."""

    @staticmethod
    def evaluate(
        y_true: Union[np.ndarray, list],
        y_pred: Union[np.ndarray, list],
        y_prob: Optional[Union[np.ndarray, list]] = None,
    ) -> Dict[str, Any]:
        """Compute standard and fraud-specific classification metrics, including curves and threshold profiles.

        Calculates:
        - accuracy, precision, recall, f1_score, f2_score
        - confusion_matrix (tn, fp, fn, tp)
        - pr_auc, roc_auc (if probabilities provided)
        - threshold_tuning_grid (100 steps from 0.01 to 0.99 for dynamic slider)
        - recommended_thresholds (best_f1, best_f2, youden_j, high_recall_90/95)
        - roc_curve (fpr, tpr, thresholds)
        - pr_curve (precision, recall)
        - score_distribution (histogram of probabilities for legit vs fraud)
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

        # Confusion Matrix for default predictions
        cm = confusion_matrix(y_true_arr, y_pred_arr, labels=[0, 1])
        if cm.shape == (2, 2):
            tn, fp, fn, tp = cm.ravel()
            metrics["confusion_matrix"] = {
                "tn": int(tn),
                "fp": int(fp),
                "fn": int(fn),
                "tp": int(tp),
            }

        # Probability-dependent metrics & visual curves
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

                # Compute rich visual data structures
                try:
                    grid = MetricEvaluator.compute_threshold_grid(y_true_arr, y_prob_arr)
                    metrics["threshold_tuning_grid"] = grid
                    metrics["recommended_thresholds"] = MetricEvaluator.compute_recommended_thresholds(
                        y_true_arr, y_prob_arr, grid
                    )
                except Exception:
                    metrics["threshold_tuning_grid"] = []
                    metrics["recommended_thresholds"] = {}

                try:
                    metrics["roc_curve"] = MetricEvaluator.compute_roc_curve(y_true_arr, y_prob_arr)
                except Exception:
                    metrics["roc_curve"] = None

                try:
                    metrics["pr_curve"] = MetricEvaluator.compute_pr_curve(y_true_arr, y_prob_arr)
                except Exception:
                    metrics["pr_curve"] = None

                try:
                    metrics["score_distribution"] = MetricEvaluator.compute_score_distribution(
                        y_true_arr, y_prob_arr
                    )
                except Exception:
                    metrics["score_distribution"] = None
            else:
                metrics["roc_auc"] = None
                metrics["pr_auc"] = None

        return metrics

    @staticmethod
    def evaluate_at_threshold(
        y_true: Union[np.ndarray, list],
        y_prob: Union[np.ndarray, list],
        threshold: float = 0.5,
    ) -> Dict[str, Any]:
        """Compute metrics for a specific decision threshold."""
        y_true_arr = np.asarray(y_true)
        y_prob_arr = np.asarray(y_prob)
        y_pred = (y_prob_arr >= threshold).astype(int)
        return MetricEvaluator.evaluate(y_true_arr, y_pred, y_prob_arr)

    @staticmethod
    def compute_threshold_grid(
        y_true: Union[np.ndarray, list],
        y_prob: Union[np.ndarray, list],
        steps: int = 100,
    ) -> List[Dict[str, Any]]:
        """Compute precision, recall, f1, f2, accuracy and confusion matrix across a uniform threshold grid."""
        y_true_arr = np.asarray(y_true)
        y_prob_arr = np.asarray(y_prob)
        y_true_bool = (y_true_arr == 1)
        total_samples = len(y_true_arr)
        pos_count = int(np.sum(y_true_bool))
        neg_count = total_samples - pos_count

        thresholds = np.linspace(0.01, 0.99, steps)
        grid: List[Dict[str, Any]] = []

        for t in thresholds:
            t_val = float(t)
            pred_pos = (y_prob_arr >= t_val)
            tp = int(np.sum(pred_pos & y_true_bool))
            fp = int(np.sum(pred_pos & ~y_true_bool))
            fn = pos_count - tp
            tn = neg_count - fp

            precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
            recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0

            pr_sum = precision + recall
            f1 = float(2 * precision * recall / pr_sum) if pr_sum > 0 else 0.0

            # F2-score: beta=2 weights recall 2x more than precision
            beta_sq = 4.0
            denom_f2 = beta_sq * precision + recall
            f2 = float((1 + beta_sq) * precision * recall / denom_f2) if denom_f2 > 0 else 0.0

            accuracy = float((tp + tn) / total_samples) if total_samples > 0 else 0.0

            grid.append({
                "threshold": round(t_val, 4),
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1_score": round(f1, 4),
                "f2_score": round(f2, 4),
                "accuracy": round(accuracy, 4),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
            })

        return grid

    @staticmethod
    def compute_recommended_thresholds(
        y_true: Union[np.ndarray, list],
        y_prob: Union[np.ndarray, list],
        grid: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Heuristically identify recommended operational thresholds."""
        if grid is None or len(grid) == 0:
            grid = MetricEvaluator.compute_threshold_grid(y_true, y_prob)

        if not grid:
            return {}

        # 1. Best F1
        best_f1 = max(grid, key=lambda x: (x["f1_score"], x["recall"]))

        # 2. Best F2 (fraud detection favorite - penalizes false negatives)
        best_f2 = max(grid, key=lambda x: (x["f2_score"], x["recall"]))

        # 3. Youden's J statistic (TPR - FPR = Recall - (FP / (FP + TN)))
        def youden_score(entry: Dict[str, Any]) -> float:
            tpr = entry["recall"]
            total_neg = entry["fp"] + entry["tn"]
            fpr = (entry["fp"] / total_neg) if total_neg > 0 else 0.0
            return tpr - fpr

        best_youden = max(grid, key=youden_score)

        # 4. Target Recall >= 90% (highest threshold meeting criteria)
        meets_90 = [x for x in grid if x["recall"] >= 0.90]
        hr_90 = max(meets_90, key=lambda x: x["threshold"]) if meets_90 else grid[0]

        # 5. Target Recall >= 95%
        meets_95 = [x for x in grid if x["recall"] >= 0.95]
        hr_95 = max(meets_95, key=lambda x: x["threshold"]) if meets_95 else grid[0]

        return {
            "best_f1": best_f1,
            "best_f2": best_f2,
            "youden_j": best_youden,
            "high_recall_90": hr_90,
            "high_recall_95": hr_95,
        }

    @staticmethod
    def compute_roc_curve(
        y_true: Union[np.ndarray, list],
        y_prob: Union[np.ndarray, list],
        max_points: int = 100,
    ) -> Dict[str, Any]:
        """Compute downsampled ROC curve coordinates (fpr, tpr, thresholds)."""
        y_true_arr = np.asarray(y_true)
        y_prob_arr = np.asarray(y_prob)

        fpr, tpr, thresholds = roc_curve(y_true_arr, y_prob_arr)

        if len(fpr) > max_points:
            indices = np.linspace(0, len(fpr) - 1, max_points, dtype=int)
            fpr = fpr[indices]
            tpr = tpr[indices]
            thresholds = thresholds[indices]

        return {
            "fpr": [round(float(x), 4) for x in fpr],
            "tpr": [round(float(x), 4) for x in tpr],
            "thresholds": [round(float(x), 4) for x in thresholds],
        }

    @staticmethod
    def compute_pr_curve(
        y_true: Union[np.ndarray, list],
        y_prob: Union[np.ndarray, list],
        max_points: int = 100,
    ) -> Dict[str, Any]:
        """Compute downsampled Precision-Recall curve coordinates."""
        y_true_arr = np.asarray(y_true)
        y_prob_arr = np.asarray(y_prob)

        prec, rec, thresholds = precision_recall_curve(y_true_arr, y_prob_arr)

        if len(prec) > max_points:
            indices = np.linspace(0, len(prec) - 1, max_points, dtype=int)
            prec = prec[indices]
            rec = rec[indices]

        return {
            "precision": [round(float(x), 4) for x in prec],
            "recall": [round(float(x), 4) for x in rec],
        }

    @staticmethod
    def compute_score_distribution(
        y_true: Union[np.ndarray, list],
        y_prob: Union[np.ndarray, list],
        bins: int = 20,
    ) -> Dict[str, Any]:
        """Compute predicted score distribution histogram for legitimate vs fraud classes."""
        y_true_arr = np.asarray(y_true)
        y_prob_arr = np.asarray(y_prob)

        bin_edges = np.linspace(0.0, 1.0, bins + 1)
        legit_probs = y_prob_arr[y_true_arr == 0]
        fraud_probs = y_prob_arr[y_true_arr == 1]

        legit_counts, _ = np.histogram(legit_probs, bins=bin_edges)
        fraud_counts, _ = np.histogram(fraud_probs, bins=bin_edges)

        return {
            "bin_edges": [round(float(x), 3) for x in bin_edges],
            "legit_counts": [int(x) for x in legit_counts],
            "fraud_counts": [int(x) for x in fraud_counts],
        }

