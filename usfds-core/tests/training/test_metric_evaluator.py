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

    def test_visual_metrics_and_curves(self):
        y_true = [0, 0, 0, 0, 1, 1, 1, 1]
        y_pred = [0, 0, 0, 1, 0, 1, 1, 1]
        y_prob = [0.1, 0.15, 0.3, 0.6, 0.45, 0.75, 0.85, 0.9]

        metrics = MetricEvaluator.evaluate(y_true, y_pred, y_prob)

        # Verify threshold tuning grid
        self.assertIn("threshold_tuning_grid", metrics)
        grid = metrics["threshold_tuning_grid"]
        self.assertEqual(len(grid), 100)
        first_step = grid[0]
        self.assertIn("threshold", first_step)
        self.assertIn("precision", first_step)
        self.assertIn("recall", first_step)
        self.assertIn("f1_score", first_step)
        self.assertIn("tp", first_step)
        self.assertIn("fp", first_step)
        self.assertIn("fn", first_step)
        self.assertIn("tn", first_step)

        # Verify recommended thresholds
        self.assertIn("recommended_thresholds", metrics)
        recs = metrics["recommended_thresholds"]
        self.assertIn("best_f1", recs)
        self.assertIn("best_f2", recs)
        self.assertIn("youden_j", recs)
        self.assertIn("high_recall_90", recs)
        self.assertIn("high_recall_95", recs)

        # Verify ROC curve
        self.assertIn("roc_curve", metrics)
        roc = metrics["roc_curve"]
        self.assertIn("fpr", roc)
        self.assertIn("tpr", roc)
        self.assertIn("thresholds", roc)
        self.assertEqual(len(roc["fpr"]), len(roc["tpr"]))

        # Verify PR curve
        self.assertIn("pr_curve", metrics)
        pr = metrics["pr_curve"]
        self.assertIn("precision", pr)
        self.assertIn("recall", pr)

        # Verify score distribution
        self.assertIn("score_distribution", metrics)
        dist = metrics["score_distribution"]
        self.assertIn("bin_edges", dist)
        self.assertIn("legit_counts", dist)
        self.assertIn("fraud_counts", dist)
        self.assertEqual(sum(dist["legit_counts"]), 4)
        self.assertEqual(sum(dist["fraud_counts"]), 4)

    def test_evaluate_at_threshold(self):
        y_true = [0, 0, 1, 1]
        y_prob = [0.2, 0.4, 0.6, 0.8]

        # At threshold 0.5: predictions are [0, 0, 1, 1] -> perfect
        res_05 = MetricEvaluator.evaluate_at_threshold(y_true, y_prob, threshold=0.5)
        self.assertEqual(res_05["precision"], 1.0)
        self.assertEqual(res_05["recall"], 1.0)
        self.assertEqual(res_05["confusion_matrix"]["tp"], 2)

        # At threshold 0.7: predictions are [0, 0, 0, 1] -> recall drops to 0.5
        res_07 = MetricEvaluator.evaluate_at_threshold(y_true, y_prob, threshold=0.7)
        self.assertEqual(res_07["recall"], 0.5)
        self.assertEqual(res_07["confusion_matrix"]["tp"], 1)
        self.assertEqual(res_07["confusion_matrix"]["fn"], 1)

        # At threshold 0.3: predictions are [0, 1, 1, 1] -> false positive increases, precision drops
        res_03 = MetricEvaluator.evaluate_at_threshold(y_true, y_prob, threshold=0.3)
        self.assertEqual(res_03["recall"], 1.0)
        self.assertAlmostEqual(res_03["precision"], 2 / 3, places=3)
        self.assertEqual(res_03["confusion_matrix"]["fp"], 1)


if __name__ == "__main__":
    unittest.main()

