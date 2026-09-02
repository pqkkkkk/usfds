import unittest
import numpy as np
import pandas as pd

from usfds_core.domain.schemas.preprocessing_config import CleansingConfig, MissingValueStrategy
from usfds_core.services.preprocessing.cleansers.standard_cleanser import StandardDataCleanser


class TestStandardDataCleanser(unittest.TestCase):
    def setUp(self):
        self.raw_data = pd.DataFrame({
            "Time": [100.0, 200.0, 200.0, 400.0, 500.0],
            "Amount": [10.0, np.nan, 20.0, 40.0, 1000.0],
            "Class": [0, 0, 0, 1, 0],
        })

    def test_drop_duplicates(self):
        df_with_dups = pd.DataFrame({
            "Time": [100, 100, 200],
            "Amount": [10, 10, 20],
            "Class": [0, 0, 1],
        })
        config = CleansingConfig(drop_duplicates=True, missing_value_strategy=MissingValueStrategy.NONE)
        cleanser = StandardDataCleanser(config)
        cleaned_df, status, report = cleanser.clean_and_validate(df_with_dups)

        self.assertEqual(len(cleaned_df), 2)
        self.assertEqual(report["removed_duplicates"], 1)
        self.assertEqual(status, "passed")

    def test_missing_value_drop(self):
        config = CleansingConfig(drop_duplicates=False, missing_value_strategy=MissingValueStrategy.DROP)
        cleanser = StandardDataCleanser(config)
        cleaned_df, status, report = cleanser.clean_and_validate(self.raw_data)

        self.assertEqual(len(cleaned_df), 4)
        self.assertFalse(cleaned_df["Amount"].isnull().any())
        self.assertEqual(status, "passed")

    def test_missing_value_mean(self):
        config = CleansingConfig(drop_duplicates=False, missing_value_strategy=MissingValueStrategy.MEAN)
        cleanser = StandardDataCleanser(config)
        cleaned_df, status, report = cleanser.clean_and_validate(self.raw_data)

        self.assertEqual(len(cleaned_df), 5)
        self.assertFalse(cleaned_df["Amount"].isnull().any())
        expected_mean = self.raw_data["Amount"].dropna().mean()
        self.assertAlmostEqual(cleaned_df.loc[1, "Amount"], expected_mean)

    def test_missing_value_constant(self):
        config = CleansingConfig(
            drop_duplicates=False,
            missing_value_strategy=MissingValueStrategy.CONSTANT,
            fill_value=0.0,
        )
        cleanser = StandardDataCleanser(config)
        cleaned_df, status, report = cleanser.clean_and_validate(self.raw_data)

        self.assertEqual(len(cleaned_df), 5)
        self.assertEqual(cleaned_df.loc[1, "Amount"], 0.0)

    def test_outlier_clipping(self):
        config = CleansingConfig(
            drop_duplicates=False,
            missing_value_strategy=MissingValueStrategy.DROP,
            outlier_clipping=True,
            outlier_upper_percentile=0.90,
        )
        cleanser = StandardDataCleanser(config)
        cleaned_df, status, report = cleanser.clean_and_validate(self.raw_data)

        self.assertTrue(report.get("outlier_clipped"))
        self.assertLess(cleaned_df["Amount"].max(), 1000.0)


if __name__ == "__main__":
    unittest.main()
