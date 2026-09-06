from typing import Any, List, Optional, Set, Tuple
import category_encoders as ce
from imblearn.pipeline import Pipeline
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
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
    NON_ML_COLUMNS,
    PreprocessingConfig,
    ScalerType,
    SystemColumn,
)
from usfds_core.services.preprocessing.dim_reduction.selection_filters import (
    SelectKBestFScoreTransformer,
    SelectKBestMITransformer,
)
from usfds_core.services.preprocessing.dim_reduction.selection_wrappers import RFETransformer
from usfds_core.services.preprocessing.resampling.factory import ResamplerFactory
from usfds_core.services.preprocessing.transformations.scalers import Log1pTransformer


class PreprocessingPipelineBuilder:
    """Constructs an imblearn.pipeline.Pipeline for Stage PRE_PROCESSED.

    Applies numerical scalers, categorical encoders, dimensionality reduction,
    and training data resampling, while automatically excluding non-ML identifiers
    and raw datetime columns.
    """

    @staticmethod
    def build(config: PreprocessingConfig, sample_df: Optional[pd.DataFrame] = None) -> Pipeline:
        steps: List[Tuple[str, Any]] = []
        t_cfg = config.transformation

        # 1. Determine Numerical and Categorical Columns
        num_cols = list(t_cfg.numeric_columns)
        cat_cols = list(t_cfg.categorical_columns)

        if sample_df is not None and isinstance(sample_df, pd.DataFrame):
            # Auto-detect if not explicitly configured
            if not num_cols and not cat_cols:
                for col in sample_df.columns:
                    if str(col).lower() in NON_ML_COLUMNS:
                        continue
                    if pd.api.types.is_numeric_dtype(sample_df[col]):
                        num_cols.append(str(col))
                    else:
                        cat_cols.append(str(col))
            else:
                # Filter out any accidentally included non-ML identifier columns
                num_cols = [c for c in num_cols if str(c).lower() not in NON_ML_COLUMNS and c in sample_df.columns]
                cat_cols = [c for c in cat_cols if str(c).lower() not in NON_ML_COLUMNS and c in sample_df.columns]

        # 2. Data Transformation (Scalers & Encoders)
        transformers: List[Tuple[str, Any, List[str]]] = []

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
        if selected_scaler and num_cols:
            transformers.append(("num_scaler", selected_scaler, num_cols))

        if cat_cols:
            if t_cfg.categorical_encoder in (CategoricalEncoderType.ONE_HOT, "one_hot"):
                transformers.append((
                    "cat_encoder",
                    OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                    cat_cols,
                ))
            elif t_cfg.categorical_encoder in (CategoricalEncoderType.BINARY, "binary"):
                transformers.append((
                    "cat_encoder",
                    ce.BinaryEncoder(),
                    cat_cols,
                ))
            elif t_cfg.categorical_encoder in (CategoricalEncoderType.ORDINAL, "ordinal"):
                transformers.append((
                    "cat_encoder",
                    OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
                    cat_cols,
                ))

        if transformers:
            # Use remainder="drop" so non-feature/identifier columns are not passed to PCA/models
            steps.append(("data_transformation", ColumnTransformer(transformers=transformers, remainder="drop")))

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
