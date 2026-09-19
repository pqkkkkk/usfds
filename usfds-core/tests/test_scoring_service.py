import unittest
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier

from usfds_core.services.inference.scoring_service import ModelScorer


class DummyProbModel:
    """Mock model with predefined predict_proba."""
    def __init__(self, probs):
        self._probs = probs

    def predict_proba(self, X):
        return np.column_stack([1 - self._probs, self._probs])

    def predict(self, X):
        return (self._probs >= 0.5).astype(int)


class DummyDecisionModel:
    """Mock model with decision_function only."""
    def __init__(self, scores):
        self._scores = np.asarray(scores)

    def decision_function(self, X):
        return self._scores

    def predict(self, X):
        return (self._scores >= 0).astype(int)


class TestModelScorer(unittest.TestCase):
    def test_custom_threshold_scoring(self):
        # 4 samples with fraud probabilities: 0.1, 0.35, 0.65, 0.9
        probs = np.array([0.1, 0.35, 0.65, 0.9])
        model = DummyProbModel(probs)
        X = pd.DataFrame({"feat": [1, 2, 3, 4]})

        # Test predict_probabilities
        extracted_probs = ModelScorer.predict_probabilities(model, X)
        np.testing.assert_allclose(extracted_probs, probs)

        # Default threshold = 0.5 -> labels: [0, 0, 1, 1]
        preds_05 = ModelScorer.predict(model, X, threshold=0.5)
        np.testing.assert_array_equal(preds_05, [0, 0, 1, 1])

        # Lower threshold = 0.3 -> labels: [0, 1, 1, 1]
        preds_03 = ModelScorer.predict(model, X, threshold=0.3)
        np.testing.assert_array_equal(preds_03, [0, 1, 1, 1])

        # Higher threshold = 0.8 -> labels: [0, 0, 0, 1]
        preds_08 = ModelScorer.predict(model, X, threshold=0.8)
        np.testing.assert_array_equal(preds_08, [0, 0, 0, 1])

    def test_predict_with_probabilities(self):
        probs = np.array([0.2, 0.45, 0.8])
        model = DummyProbModel(probs)
        X = pd.DataFrame({"feat": [1, 2, 3]})

        preds, returned_probs = ModelScorer.predict_with_probabilities(model, X, threshold=0.4)
        np.testing.assert_array_equal(preds, [0, 1, 1])
        np.testing.assert_allclose(returned_probs, probs)

    def test_fallback_decision_function(self):
        # Decision function: [-2.0, 0.0, 2.0]
        model = DummyDecisionModel([-2.0, 0.0, 2.0])
        X = pd.DataFrame({"feat": [1, 2, 3]})

        probs = ModelScorer.predict_probabilities(model, X)
        # At score 0.0, sigmoid(0.0) == 0.5
        self.assertAlmostEqual(probs[1], 0.5, places=3)
        self.assertLess(probs[0], 0.5)
        self.assertGreater(probs[2], 0.5)

    def test_fallback_raw_predict(self):
        class HardOnlyModel:
            def predict(self, X):
                return np.array([0, 1])

        model = HardOnlyModel()
        X = pd.DataFrame({"feat": [1, 2]})
        preds, probs = ModelScorer.predict_with_probabilities(model, X, threshold=0.5)
        np.testing.assert_array_equal(preds, [0, 1])
        np.testing.assert_array_equal(probs, [0.0, 1.0])


if __name__ == "__main__":
    unittest.main()
