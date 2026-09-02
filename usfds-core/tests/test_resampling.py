import unittest
from imblearn.over_sampling import SMOTE
from imblearn.under_sampling import RandomUnderSampler

from usfds_core.domain.schemas.preprocessing_config import ResamplingConfig, ResamplingStrategy
from usfds_core.services.preprocessing.resampling.factory import ResamplerFactory


class TestResamplerFactory(unittest.TestCase):
    def test_create_smote(self):
        config = ResamplingConfig(method=ResamplingStrategy.SMOTE, random_state=42)
        resampler = ResamplerFactory.create(config)
        self.assertIsInstance(resampler, SMOTE)

    def test_create_random_undersampling(self):
        config = ResamplingConfig(method=ResamplingStrategy.RANDOM_UNDERSAMPLING, random_state=42)
        resampler = ResamplerFactory.create(config)
        self.assertIsInstance(resampler, RandomUnderSampler)

    def test_create_none(self):
        config = ResamplingConfig(method=ResamplingStrategy.NONE)
        resampler = ResamplerFactory.create(config)
        self.assertIsNone(resampler)


if __name__ == "__main__":
    unittest.main()
