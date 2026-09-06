import unittest
import pandas as pd

from usfds_core.domain.schemas.preprocessing_config import SplitConfig
from usfds_core.services.preprocessing.splitters.temporal_splitter import TemporalDataSplitter


class TestTemporalDataSplitter(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame({
            "Time": [10, 50, 20, 40, 30, 60, 70, 80, 90, 100],
            "Amount": [100, 500, 200, 400, 300, 600, 700, 800, 900, 1000],
            "Class": [0, 0, 0, 0, 1, 0, 0, 1, 0, 0],
        })

    def test_temporal_order_preservation(self):
        config = SplitConfig(time_column="Time", target_column="Class", test_size=0.3)
        splitter = TemporalDataSplitter(config)
        X_train, X_test, y_train, y_test = splitter.split_features_target(self.df)

        # Total 10 rows: 70% train = 7 rows, 30% test = 3 rows
        self.assertEqual(len(X_train), 7)
        self.assertEqual(len(X_test), 3)
        self.assertEqual(len(y_train), 7)
        self.assertEqual(len(y_test), 3)

        # Check temporal order: Train max time <= Test min time
        self.assertLessEqual(X_train["Time"].max(), X_test["Time"].min())
        self.assertEqual(list(X_train["Time"]), [10, 20, 30, 40, 50, 60, 70])
        self.assertEqual(list(X_test["Time"]), [80, 90, 100])

    def test_split_train_test(self):
        config = SplitConfig(time_column="Time", target_column="Class", test_size=0.3)
        splitter = TemporalDataSplitter(config)
        train_df, test_df = splitter.split_train_test(self.df)

        self.assertEqual(len(train_df), 7)
        self.assertEqual(len(test_df), 3)
        # Verify Class column is retained in both
        self.assertIn("Class", train_df.columns)
        self.assertIn("Class", test_df.columns)
        self.assertEqual(list(train_df["Time"]), [10, 20, 30, 40, 50, 60, 70])
        self.assertEqual(list(test_df["Time"]), [80, 90, 100])

    def test_missing_target_column_raises_error(self):
        config = SplitConfig(time_column="Time", target_column="NonExistentTarget", test_size=0.2)
        splitter = TemporalDataSplitter(config)
        with self.assertRaises(ValueError):
            splitter.split_features_target(self.df)


if __name__ == "__main__":
    unittest.main()

