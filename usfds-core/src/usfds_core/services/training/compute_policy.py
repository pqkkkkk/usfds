"""Compute target resolution and auto-selection policy for training runs (ISS-009)."""
from typing import List, Optional, Tuple
from pydantic import BaseModel

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.enums import ExecutionType
from usfds_core.domain.entities.model import Model
from usfds_core.domain.schemas.training_payload import (
	ComputeRecommendation,
	ComputeTargetInfo,
)
from usfds_core.services.training.providers.base_provider import RemoteProviderRegistry


class ComputePolicyThresholds(BaseModel):
	"""Thresholds governing automatic compute selection."""
	row_count_threshold: int = 100_000
	gpu_frameworks: Tuple[str, ...] = (
		"pytorch",
		"torch",
		"tensorflow",
		"keras",
		"graph",
		"gnn",
		"pyg",
		"dgl",
	)


class ComputeSelectionPolicy:
	"""Resolves requested compute_target ('auto', 'local', 'worker', '<provider>') into an executable plan."""

	def __init__(self, thresholds: Optional[ComputePolicyThresholds] = None):
		self.thresholds = thresholds or ComputePolicyThresholds()

	def _requires_gpu(
		self,
		model: Optional[Model],
		plugin_framework: Optional[str] = None,
	) -> bool:
		tokens: List[str] = []
		if plugin_framework:
			tokens.append(plugin_framework.lower())
		if model is not None:
			exec_str = (
				model.execution_type.value
				if hasattr(model.execution_type, "value")
				else str(model.execution_type)
			)
			if exec_str.upper() == ExecutionType.SCRIPT.value:
				if model.model_name:
					tokens.append(model.model_name.lower())
				if model.description:
					tokens.append(model.description.lower())
				if isinstance(model.default_hyperparameters, dict):
					fw = model.default_hyperparameters.get("framework")
					if fw:
						tokens.append(str(fw).lower())
		combined = " ".join(tokens)
		return any(keyword in combined for keyword in self.thresholds.gpu_frameworks)

	@staticmethod
	def _match_profile_token(token: str) -> Optional[str]:
		t = token.strip().lower()
		if not t:
			return None
		if any(k in t for k in ("pyg", "dgl", "gnn", "graph")):
			return "dl-pyg-gpu"
		if any(k in t for k in ("pytorch", "torch", "tensorflow", "keras")):
			return "dl-pytorch-gpu"
		if any(k in t for k in ("lightgbm", "lgbm")):
			return "tabular-lightgbm"
		if "onnx" in t:
			return "tabular-onnx"
		if any(k in t for k in ("xgboost", "xgb")):
			return "tabular-gbdt"
		if any(k in t for k in ("scikit-learn", "sklearn", "random_forest", "randomforest")):
			return "tabular-sklearn"
		return None

	def resolve_runtime_profile(
		self,
		model: Optional[Model] = None,
		plugin_framework: Optional[str] = None,
	) -> str:
		"""Resolve an isolated container runtime profile for the model / plugin framework."""
		if plugin_framework:
			matched = self._match_profile_token(plugin_framework)
			if matched:
				return matched
		if model is not None:
			if isinstance(model.default_hyperparameters, dict):
				fw = model.default_hyperparameters.get("framework")
				if fw:
					matched = self._match_profile_token(str(fw))
					if matched:
						return matched
			for hint in (model.model_name or "", model.description or ""):
				matched = self._match_profile_token(hint)
				if matched:
					return matched
		return "tabular-sklearn"

	def resolve(
		self,
		requested_target: str = "auto",
		model: Optional[Model] = None,
		artifact: Optional[DatasetArtifact] = None,
		plugin_framework: Optional[str] = None,
		registry: Optional[RemoteProviderRegistry] = None,
	) -> ComputeRecommendation:
		req = (requested_target or "local").strip().lower()
		needs_gpu = self._requires_gpu(model=model, plugin_framework=plugin_framework)
		runtime_profile = self.resolve_runtime_profile(model=model, plugin_framework=plugin_framework)
		row_count = artifact.row_count if artifact is not None else None

		if req in ("local", "worker"):
			return ComputeRecommendation(
				requested_target=req,
				resolved_target=req,
				resource_tier="cpu",
				runtime_profile=runtime_profile,
				provider=None,
				selection_reason="Người dùng chọn chạy huấn luyện cục bộ / worker.",
			)

		if req == "auto":
			provider = registry.first_available() if registry is not None else None
			if provider is None:
				reasons: List[str] = []
				if registry is not None:
					for p in registry.list_providers():
						ok, reason = p.is_available()
						if not ok and reason:
							reasons.append(f"{p.display_name}: {reason}")
				suffix = f" ({'; '.join(reasons)})" if reasons else ""
				return ComputeRecommendation(
					requested_target="auto",
					resolved_target="local",
					resource_tier="cpu",
					runtime_profile=runtime_profile,
					provider=None,
					selection_reason=(
						f"Không có remote compute provider khả dụng{suffix}; tự động chuyển về local."
					),
				)

			if needs_gpu and "gpu" in provider.supported_tiers:
				return ComputeRecommendation(
					requested_target="auto",
					resolved_target=provider.provider_id,
					resource_tier="gpu",
					runtime_profile=runtime_profile,
					provider=provider.provider_id,
					selection_reason=(
						f"Mô hình Deep Learning / Graph phù hợp chạy GPU trên {provider.display_name}."
					),
				)

			if row_count is not None and row_count >= self.thresholds.row_count_threshold:
				return ComputeRecommendation(
					requested_target="auto",
					resolved_target=provider.provider_id,
					resource_tier="cpu",
					runtime_profile=runtime_profile,
					provider=provider.provider_id,
					selection_reason=(
						f"Tập dữ liệu lớn ({row_count:,} dòng >= {self.thresholds.row_count_threshold:,}); "
						f"đề xuất chạy CPU từ xa trên {provider.display_name}."
					),
				)

			row_desc = f"{row_count:,} dòng" if row_count is not None else "quy mô nhỏ"
			return ComputeRecommendation(
				requested_target="auto",
				resolved_target="local",
				resource_tier="cpu",
				runtime_profile=runtime_profile,
				provider=None,
				selection_reason=(
					f"Mô hình dạng bảng với tập dữ liệu {row_desc} (< {self.thresholds.row_count_threshold:,} dòng); "
					"chạy cục bộ nhanh và tiết kiệm chi phí hơn."
				),
			)

		# Explicit remote provider target
		if registry is None:
			raise ValueError(f"Compute target '{req}' is not configured.")
		provider = registry.get(req)
		if provider is None:
			raise ValueError(f"Compute target '{req}' is not registered.")
		ok, reason = provider.is_available()
		if not ok:
			raise ValueError(
				f"Compute target '{req}' is not available: {reason or 'provider chưa sẵn sàng'}."
			)
		tier = "gpu" if (needs_gpu and "gpu" in provider.supported_tiers) else "cpu"
		return ComputeRecommendation(
			requested_target=req,
			resolved_target=provider.provider_id,
			resource_tier=tier,
			runtime_profile=runtime_profile,
			provider=provider.provider_id,
			selection_reason=f"Người dùng chọn chạy trên {provider.display_name} ({tier.upper()}).",
		)

	def list_targets(
		self,
		registry: Optional[RemoteProviderRegistry] = None,
	) -> List[ComputeTargetInfo]:
		targets: List[ComputeTargetInfo] = [
			ComputeTargetInfo(
				target_id="auto",
				display_name="Tự động chọn (Auto)",
				provider_type="auto",
				available=True,
				reason="Tự động chọn local hoặc remote dựa trên loại mô hình và quy mô dữ liệu.",
				resource_tiers=["cpu", "gpu"],
			),
			ComputeTargetInfo(
				target_id="local",
				display_name="Local / Dedicated Worker",
				provider_type="local",
				available=True,
				reason=None,
				resource_tiers=["cpu"],
			),
		]
		if registry is not None:
			for provider in registry.list_providers():
				ok, reason = provider.is_available()
				targets.append(
					ComputeTargetInfo(
						target_id=provider.provider_id,
						display_name=provider.display_name,
						provider_type="remote",
						available=ok,
						reason=reason,
						resource_tiers=list(provider.supported_tiers),
					)
				)
		return targets
