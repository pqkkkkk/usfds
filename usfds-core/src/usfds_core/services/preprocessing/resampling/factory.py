from typing import Any, Optional
from imblearn.combine import SMOTEENN, SMOTETomek
from imblearn.over_sampling import ADASYN, SMOTE
from imblearn.under_sampling import RandomUnderSampler, TomekLinks

from usfds_core.domain.schemas.preprocessing_config import ResamplingConfig, ResamplingStrategy


class ResamplerFactory:
    """Factory for instantiating imbalanced-learn sampling strategies."""

    @staticmethod
    def create(config: ResamplingConfig) -> Optional[Any]:
        method = config.method
        if method in (ResamplingStrategy.NONE, "none", None):
            return None

        sampling_strategy = config.sampling_strategy
        random_state = config.random_state

        if method in (ResamplingStrategy.SMOTE, "smote"):
            return SMOTE(sampling_strategy=sampling_strategy, random_state=random_state)
        elif method in (ResamplingStrategy.ADASYN, "adasyn"):
            return ADASYN(sampling_strategy=sampling_strategy, random_state=random_state)
        elif method in (ResamplingStrategy.RANDOM_UNDERSAMPLING, "random_undersampling"):
            return RandomUnderSampler(sampling_strategy=sampling_strategy, random_state=random_state)
        elif method in (ResamplingStrategy.TOMEK_LINKS, "tomek_links"):
            return TomekLinks()
        elif method in (ResamplingStrategy.SMOTE_TOMEK, "smote_tomek"):
            return SMOTETomek(sampling_strategy=sampling_strategy, random_state=random_state)
        elif method in (ResamplingStrategy.SMOTE_ENN, "smote_enn"):
            return SMOTEENN(sampling_strategy=sampling_strategy, random_state=random_state)
        else:
            raise ValueError(f"Unsupported resampling method: {method}")


__all__ = ["ResamplerFactory"]
