"""Model Explainability Module using SHAP TreeExplainer for USFDS."""

from pathlib import Path
from typing import Any, Dict, List
import joblib
import pandas as pd
import shap

from usfds_core.domain.schemas.investigation_schemas import (
    FeatureContribution,
    FeatureExplanation,
)

# Friendly mapping for human-readable explanations
FRIENDLY_NAMES: Dict[str, str] = {
    "num_scaler__account_age_days": "Tuổi tài khoản (Account Age)",
    "num_scaler__total_transactions_user": "Tổng số giao dịch của user",
    "num_scaler__avg_amount_user": "Số tiền trung bình của user",
    "num_scaler__amount": "Số tiền giao dịch (Amount)",
    "num_scaler__promo_used": "Sử dụng mã khuyến mãi",
    "num_scaler__avs_match": "Khớp địa chỉ AVS (Address Verification)",
    "num_scaler__cvv_result": "Kết quả xác thực mã CVV",
    "num_scaler__three_ds_flag": "Xác thực bảo mật 3D Secure (3DS)",
    "num_scaler__shipping_distance_km": "Khoảng cách giao hàng (Shipping Distance)",
    "cat_encoder__channel_app": "Kênh Mobile App",
    "cat_encoder__channel_web": "Kênh Website",
}


class ModelExplainabilityService:
    """Computes local feature importance / SHAP values for model predictions."""

    def __init__(
        self,
        model_artifact_path: str,
        pipeline_artifact_path: str,
        test_processed_path: str,
    ):
        self.model_path = str(Path(model_artifact_path).resolve())
        self.pipeline_path = str(Path(pipeline_artifact_path).resolve())
        self.test_processed_path = str(Path(test_processed_path).resolve())

        # Lazy loaded caches
        self._model = None
        self._explainer = None
        self._feature_names = None
        self._processed_df = None

    def _ensure_loaded(self) -> None:
        """Loads model, pipeline, and initializes SHAP TreeExplainer."""
        if self._model is None:
            self._model = joblib.load(self.model_path)
            self._explainer = shap.TreeExplainer(self._model)

            pipe = joblib.load(self.pipeline_path)
            self._feature_names = list(
                pipe.named_steps["data_transformation"].get_feature_names_out()
            )

        if self._processed_df is None:
            self._processed_df = pd.read_parquet(self.test_processed_path)
            if "label" in self._processed_df.columns:
                self._processed_df = self._processed_df.drop(columns=["label"])

    def _get_display_name(self, raw_name: str) -> str:
        """Translates raw pipeline feature name to intuitive human-readable name."""
        if raw_name in FRIENDLY_NAMES:
            return FRIENDLY_NAMES[raw_name]

        if raw_name.startswith("cat_encoder__country_"):
            code = raw_name.replace("cat_encoder__country_", "")
            return f"Quốc gia giao dịch: {code}"
        if raw_name.startswith("cat_encoder__bin_country_"):
            code = raw_name.replace("cat_encoder__bin_country_", "")
            return f"Quốc gia mở thẻ (BIN): {code}"
        if raw_name.startswith("cat_encoder__merchant_category_"):
            cat = raw_name.replace("cat_encoder__merchant_category_", "")
            return f"Ngành hàng: {cat.capitalize()}"

        return raw_name

    def explain_prediction(
        self,
        event_id: int,
        row_index: int,
        y_prob: float,
        top_k: int = 5,
    ) -> FeatureExplanation:
        """Generates top positive (risk-increasing) and negative (mitigating) feature contributions."""
        self._ensure_loaded()

        # Slice target row features
        row_features = self._processed_df.iloc[[row_index]]
        shap_res = self._explainer(row_features)

        # shap_res.values shape: (1, n_features, 2) for binary classification
        if len(shap_res.values.shape) == 3:
            fraud_shap = shap_res.values[0, :, 1]
            base_val = float(shap_res.base_values[0, 1])
        else:
            fraud_shap = shap_res.values[0, :]
            base_val = float(shap_res.base_values[0])

        feature_values = row_features.iloc[0].to_dict()

        contributions: List[FeatureContribution] = []
        for feat_name, score in zip(self._feature_names, fraud_shap):
            score_float = float(score)
            impact = "INCREASES_RISK" if score_float > 0 else "DECREASES_RISK"
            display_name = self._get_display_name(feat_name)
            val = feature_values.get(feat_name, None)

            contributions.append(
                FeatureContribution(
                    feature_name=feat_name,
                    display_name=display_name,
                    feature_value=round(val, 4) if isinstance(val, (float, int)) else str(val),
                    importance_score=round(score_float, 4),
                    impact=impact,
                )
            )

        # Sort risk-increasing and mitigating factors
        risk_factors = [c for c in contributions if c.importance_score > 0]
        risk_factors.sort(key=lambda x: x.importance_score, reverse=True)

        mitigating_factors = [c for c in contributions if c.importance_score < 0]
        mitigating_factors.sort(key=lambda x: x.importance_score)

        return FeatureExplanation(
            event_id=event_id,
            base_value=round(base_val, 4),
            prediction_score=round(y_prob, 4),
            top_risk_factors=risk_factors[:top_k],
            top_mitigating_factors=mitigating_factors[:top_k],
        )
