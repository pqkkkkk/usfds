import unittest

from usfds_core.services.training.evaluators.metric_evaluator import MetricEvaluator


class TestMetricEvaluator(unittest.TestCase):
    def test_perfect_predictions(self):
        y_true = [0, 0, 1, 1]
        y_pred = [0, 0, 1, 1]
        y_prob = [0.1, 0.2, 0.8, 0.9]

        metrics = MetricEvaluator.evaluate(y_true, y_pred, y_prob)

        self.assertEqual(metrics["accuracy"], 1.0)
        self.assertEqual(metrics["precision"], 1.0)
        self.assertEqual(metrics["recall"], 1.0)
        self.assertEqual(metrics["f1_score"], 1.0)
        self.assertEqual(metrics["f2_score"], 1.0)
        self.assertEqual(metrics["roc_auc"], 1.0)
        self.assertEqual(metrics["pr_auc"], 1.0)
        self.assertEqual(metrics["confusion_matrix"], {"tn": 2, "fp": 0, "fn": 0, "tp": 2})

    def test_imbalanced_f2_weighting(self):
        # Case where recall is high (1.0) but precision is moderate (0.5)
        # TP = 2, FP = 2, FN = 0, TN = 6
        y_true = [0, 0, 0, 0, 0, 0, 1, 1]
        y_pred = [0, 0, 0, 0, 1, 1, 1, 1]  # 2 false positives, 0 false negatives
        y_prob = [0.1, 0.1, 0.2, 0.2, 0.6, 0.7, 0.8, 0.9]

        metrics = MetricEvaluator.evaluate(y_true, y_pred, y_prob)
        self.assertEqual(metrics["recall"], 1.0)
        self.assertEqual(metrics["precision"], 0.5)
        # F2-score should be higher than F1-score because recall = 1.0
        self.assertGreater(metrics["f2_score"], metrics["f1_score"])
        self.assertEqual(metrics["confusion_matrix"]["tp"], 2)
        self.assertEqual(metrics["confusion_matrix"]["fp"], 2)
        self.assertEqual(metrics["confusion_matrix"]["fn"], 0)
        self.assertEqual(metrics["confusion_matrix"]["tn"], 4)

    def test_without_probabilities(self):
        y_true = [0, 1, 0, 1]
        y_pred = [0, 1, 1, 0]

        metrics = MetricEvaluator.evaluate(y_true, y_pred)
        self.assertNotIn("roc_auc", metrics)
        self.assertNotIn("pr_auc", metrics)
        self.assertIn("f1_score", metrics)
        self.assertIn("confusion_matrix", metrics)

    def test_single_class_edge_case(self):
        # All negatives
        y_true = [0, 0, 0, 0]
        y_pred = [0, 0, 0, 0]
        y_prob = [0.1, 0.2, 0.1, 0.3]

        metrics = MetricEvaluator.evaluate(y_true, y_pred, y_prob)
        self.assertEqual(metrics["accuracy"], 1.0)
        self.assertIsNone(metrics["roc_auc"])
        self.assertIsNone(metrics["pr_auc"])


if __name__ == "__main__":
    unittest.main()
