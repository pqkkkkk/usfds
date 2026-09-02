from typing import Any, List, Tuple
import category_encoders as ce
from imblearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
from sklearn.feature_selection import SelectKBest, mutual_info_classif
from sklearn.preprocessing import (
    FunctionTransformer,
    MinMaxScaler,
    OneHotEncoder,
    OrdinalEncoder,
    RobustScaler,
    StandardScaler,
)

from usfds_core.domain.schemas.preprocessing_config import (
    CategoricalEncoderType,
    DimReductionType,
    PreprocessingConfig,
    ScalerType,
)
from usfds_core.services.preprocessing.dim_reduction.selection_filters import (
    SelectKBestFScoreTransformer,
    SelectKBestMITransformer,
)
from usfds_core.services.preprocessing.dim_reduction.selection_wrappers import RFETransformer
from usfds_core.services.preprocessing.feature_engineering.credit_card_engineer import CreditCardFeatureEngineer
from usfds_core.services.preprocessing.feature_engineering.velocity_engineer import VelocityFeatureEngineer
from usfds_core.services.preprocessing.resampling.factory import ResamplerFactory
from usfds_core.services.preprocessing.transformations.scalers import Log1pTransformer


class PreprocessingPipelineBuilder:
    """Constructs an end-to-end imblearn.pipeline.Pipeline from a PreprocessingConfig."""

    @staticmethod
    def build(config: PreprocessingConfig) -> Pipeline:
        steps: List[Tuple[str, Any]] = []

        # 1. Feature Engineering
        fe_cfg = config.feature_engineering
        if fe_cfg.enable_amount_ratios or fe_cfg.enable_hour_of_day:
            steps.append((
                "credit_card_feature_engineering",
                CreditCardFeatureEngineer(
                    time_col=fe_cfg.time_col,
                    amount_col=fe_cfg.amount_col,
                    add_ratio=fe_cfg.enable_amount_ratios,
                    enable_hour_of_day=fe_cfg.enable_hour_of_day,
                ),
            ))

        if fe_cfg.enable_velocity_features and fe_cfg.customer_id_col:
            steps.append((
                "velocity_feature_engineering",
                VelocityFeatureEngineer(
                    customer_id_col=fe_cfg.customer_id_col,
                    time_col=fe_cfg.time_col,
                    amount_col=fe_cfg.amount_col,
                    windows=fe_cfg.velocity_windows,
                ),
            ))

        # 2. Data Transformation (Scalers & Encoders)
        transformers = []
        t_cfg = config.transformation

        scaler_map = {
            ScalerType.STANDARD: StandardScaler(),
            ScalerType.MINMAX: MinMaxScaler(),
            ScalerType.ROBUST: RobustScaler(),
            ScalerType.LOG1P: Log1pTransformer(),
            "standard": StandardScaler(),
            "minmax": MinMaxScaler(),
            "robust": RobustScaler(),
            "log1p": Log1pTransformer(),
        }
        selected_scaler = scaler_map.get(t_cfg.scaler)
        if selected_scaler and t_cfg.numeric_columns:
            transformers.append(("num_scaler", selected_scaler, t_cfg.numeric_columns))

        if t_cfg.categorical_columns:
            if t_cfg.categorical_encoder in (CategoricalEncoderType.ONE_HOT, "one_hot"):
                transformers.append((
                    "cat_encoder",
                    OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                    t_cfg.categorical_columns,
                ))
            elif t_cfg.categorical_encoder in (CategoricalEncoderType.BINARY, "binary"):
                transformers.append((
                    "cat_encoder",
                    ce.BinaryEncoder(),
                    t_cfg.categorical_columns,
                ))
            elif t_cfg.categorical_encoder in (CategoricalEncoderType.ORDINAL, "ordinal"):
                transformers.append((
                    "cat_encoder",
                    OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
                    t_cfg.categorical_columns,
                ))

        if transformers:
            steps.append(("data_transformation", ColumnTransformer(transformers=transformers, remainder="passthrough")))

        # 3. Dimensionality Reduction / Feature Selection
        dr_cfg = config.dim_reduction
        if dr_cfg.method in (DimReductionType.PCA, "pca"):
            steps.append(("dim_reduction", PCA(n_components=dr_cfg.n_components or 10)))
        elif dr_cfg.method in (DimReductionType.SELECT_K_BEST_MI, "select_k_best_mi"):
            steps.append(("dim_reduction", SelectKBestMITransformer(k=dr_cfg.k_features or 15)))
        elif dr_cfg.method in (DimReductionType.SELECT_K_BEST_F2, "select_k_best_f2"):
            steps.append(("dim_reduction", SelectKBestFScoreTransformer(k=dr_cfg.k_features or 15)))
        elif dr_cfg.method in (DimReductionType.RFE, "rfe"):
            steps.append(("dim_reduction", RFETransformer(n_features_to_select=dr_cfg.k_features or 15)))

        # 4. Data Resampling (Executed only during training fit_resample)
        resampler = ResamplerFactory.create(config.resampling)
        if resampler is not None:
            steps.append(("data_resampling", resampler))

        # 5. Ensure Pipeline is non-empty
        if not steps:
            steps.append(("passthrough", FunctionTransformer()))

        return Pipeline(steps=steps)


__all__ = ["PreprocessingPipelineBuilder"]
