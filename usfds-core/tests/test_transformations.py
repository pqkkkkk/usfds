import unittest
import numpy as np
import pandas as pd

from usfds_core.services.preprocessing.transformations.scalers import Log1pTransformer


class TestTransformations(unittest.TestCase):
    def test_log1p_transformer_dataframe(self):
        df = pd.DataFrame({
            "Amount": [0.0, 10.0, 100.0, -5.0],
            "Category": ["A", "B", "C", "D"],
        })
        transformer = Log1pTransformer(columns=["Amount"])
        transformer.fit(df)
        out = transformer.transform(df)

        self.assertAlmostEqual(out.loc[0, "Amount"], np.log1p(0.0))
        self.assertAlmostEqual(out.loc[1, "Amount"], np.log1p(10.0))
        self.assertAlmostEqual(out.loc[2, "Amount"], np.log1p(100.0))
        self.assertAlmostEqual(out.loc[3, "Amount"], np.log1p(0.0))  # negative clamped to 0
        self.assertEqual(list(out["Category"]), ["A", "B", "C", "D"])

    def test_log1p_transformer_numpy(self):
        arr = np.array([0.0, 10.0, 100.0])
        transformer = Log1pTransformer()
        out = transformer.transform(arr)
        np.testing.assert_almost_equal(out, np.log1p(arr))


if __name__ == "__main__":
    unittest.main()
