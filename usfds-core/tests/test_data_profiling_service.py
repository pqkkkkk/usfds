import unittest
import numpy as np
import pandas as pd

from usfds_core.services.data_management import DataProfilingService
from usfds_core.domain.schemas.dataset_profiling import DatasetProfilingSummary
class TestDataProfilingService(unittest.TestCase):
    def setUp(self):
        self.eda_service = DataProfilingService()
        self.sample_df = pd.DataFrame({
            "transaction_id": [101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
            "user_id": ["u1", "u2", "u1", "u3", "u2", "u4", "u1", "u5", "u2", "u3"],
            "amount": [10.5, 20.0, np.nan, 45.2, np.nan, 99.9, 12.0, 50.0, 75.5, 100.0],
            "is_fraud": [0, 0, 0, 1, 0, 0, 1, 0, 0, 0],
            "location": ["US", "VN", "US", "SG", None, "VN", None, "US", "JP", "SG"],
        })

    def test_basic_eda_metrics(self):
        summary = self.eda_service.analyze(self.sample_df)

        self.assertIsInstance(summary, DatasetProfilingSummary)
        self.assertEqual(summary.row_count, 10)
        self.assertEqual(summary.field_count, 5)
        self.assertEqual(
            summary.field_names,
            ["transaction_id", "user_id", "amount", "is_fraud", "location"],
        )
        self.assertEqual(len(summary.fields), 5)

        # Field: transaction_id (all unique, no nulls)
        tx_field = summary.get_field("transaction_id")
        self.assertIsNotNone(tx_field)
        self.assertEqual(tx_field.unique_count, 10)
        self.assertEqual(tx_field.null_count, 0)
        self.assertEqual(tx_field.null_percentage, 0.0)

        # Field: user_id (5 unique users, no nulls)
        user_field = summary.get_field("user_id")
        self.assertIsNotNone(user_field)
        self.assertEqual(user_field.unique_count, 5)
        self.assertEqual(user_field.null_count, 0)
        self.assertEqual(user_field.null_percentage, 0.0)

        # Field: amount (2 nulls out of 10 -> 20.0%)
        amount_field = summary.get_field("amount")
        self.assertIsNotNone(amount_field)
        self.assertEqual(amount_field.null_count, 2)
        self.assertEqual(amount_field.null_percentage, 20.0)
        self.assertEqual(amount_field.unique_count, 8)

        # Field: location (2 nulls out of 10 -> 20.0%, 4 unique non-null values: US, VN, SG, JP)
        loc_field = summary.get_field("location")
        self.assertIsNotNone(loc_field)
        self.assertEqual(loc_field.null_count, 2)
        self.assertEqual(loc_field.null_percentage, 20.0)
        self.assertEqual(loc_field.unique_count, 4)

    def test_to_dict_serialization(self):
        summary = self.eda_service.analyze(self.sample_df)
        data = summary.to_dict()

        self.assertIn("row_count", data)
        self.assertIn("field_count", data)
        self.assertIn("field_names", data)
        self.assertIn("fields", data)
        self.assertEqual(len(data["fields"]), 5)
        self.assertEqual(data["fields"][0]["name"], "transaction_id")
        self.assertEqual(data["fields"][0]["null_count"], 0)

    def test_all_null_column(self):
        df = pd.DataFrame({
            "col_null": [None, np.nan, None, np.nan],
            "col_valid": [1, 2, 3, 4],
        })
        summary = self.eda_service.analyze(df)

        null_field = summary.get_field("col_null")
        self.assertIsNotNone(null_field)
        self.assertEqual(null_field.null_count, 4)
        self.assertEqual(null_field.null_percentage, 100.0)
        self.assertEqual(null_field.unique_count, 0)

    def test_empty_dataframe(self):
        df = pd.DataFrame(columns=["col1", "col2"])
        summary = self.eda_service.analyze(df)

        self.assertEqual(summary.row_count, 0)
        self.assertEqual(summary.field_count, 2)
        col1 = summary.get_field("col1")
        self.assertIsNotNone(col1)
        self.assertEqual(col1.null_count, 0)
        self.assertEqual(col1.null_percentage, 0.0)
        self.assertEqual(col1.unique_count, 0)

    def test_unhashable_column_handling(self):
        df = pd.DataFrame({
            "tags": [["a", "b"], ["c"], ["a", "b"], ["d"]],
        })
        summary = self.eda_service.analyze(df)
        tags_field = summary.get_field("tags")
        self.assertIsNotNone(tags_field)
        self.assertEqual(tags_field.unique_count, 3)
        self.assertEqual(tags_field.null_count, 0)


if __name__ == "__main__":
    unittest.main()
