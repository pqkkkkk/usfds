import unittest
import numpy as np
from sklearn.datasets import make_classification

from usfds_core.services.preprocessing.dim_reduction.selection_filters import SelectKBestMITransformer
from usfds_core.services.preprocessing.dim_reduction.selection_wrappers import RFETransformer


class TestDimReduction(unittest.TestCase):
    def setUp(self):
        self.X, self.y = make_classification(
            n_samples=60,
            n_features=10,
            n_informative=4,
            n_redundant=2,
            random_state=42,
        )

    def test_select_k_best_mi(self):
        reducer = SelectKBestMITransformer(k=3, random_state=42)
        reducer.fit(self.X, self.y)
        X_reduced = reducer.transform(self.X)

        self.assertEqual(X_reduced.shape, (60, 3))

    def test_rfe_transformer(self):
        reducer = RFETransformer(n_features_to_select=4)
        reducer.fit(self.X, self.y)
        X_reduced = reducer.transform(self.X)

        self.assertEqual(X_reduced.shape, (60, 4))


if __name__ == "__main__":
    unittest.main()
