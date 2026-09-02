import unittest
import pandas as pd

from usfds_core.services.preprocessing.feature_engineering.credit_card_engineer import CreditCardFeatureEngineer


class TestCreditCardFeatureEngineer(unittest.TestCase):
    def setUp(self):
        self.train_df = pd.DataFrame({
            "Time": [0, 3600, 7200, 86400],
            "Amount": [100.0, 200.0, 300.0, 400.0],
            "V1": [1.0, 2.0, 3.0, 4.0],
        })
        self.test_df = pd.DataFrame({
            "Time": [10800, 14400],
            "Amount": [250.0, 500.0],
            "V1": [5.0, 6.0],
        })

    def test_fit_and_transform_features(self):
        engineer = CreditCardFeatureEngineer(time_col="Time", amount_col="Amount", add_ratio=True, enable_hour_of_day=True)
        engineer.fit(self.train_df)

        # Mean amount in train: (100+200+300+400)/4 = 250.0
        self.assertAlmostEqual(engineer.mean_amount_, 250.0)

        # Transform train
        out_train = engineer.transform(self.train_df)
        self.assertIn("hour_of_day", out_train.columns)
        self.assertIn("amount_to_mean_ratio", out_train.columns)
        self.assertEqual(list(out_train["hour_of_day"]), [0.0, 1.0, 2.0, 0.0])
        self.assertAlmostEqual(out_train.loc[0, "amount_to_mean_ratio"], 100.0 / 250.0, places=4)

        # Transform test using the learned train mean (no leakage)
        out_test = engineer.transform(self.test_df)
        self.assertAlmostEqual(out_test.loc[0, "amount_to_mean_ratio"], 250.0 / 250.0, places=4)
        self.assertAlmostEqual(out_test.loc[1, "amount_to_mean_ratio"], 500.0 / 250.0, places=4)


if __name__ == "__main__":
    unittest.main()
