"""Dynamic minimal Modal container image definitions per runtime profile (ISS-009)."""
from typing import Any, Dict, Tuple

BASE_TRAINING_DEPS: Tuple[str, ...] = (
	"pydantic>=2.6.0",
	"pandas>=2.2.0",
	"numpy>=2.0.0",
	"pyarrow>=26.0.0",
	"scikit-learn>=1.4.0,<1.6.0",
	"joblib>=1.3.0",
)

RUNTIME_PROFILE_DEPS: Dict[str, Tuple[str, ...]] = {
	"tabular-sklearn": BASE_TRAINING_DEPS,
	"tabular-gbdt": BASE_TRAINING_DEPS + ("xgboost>=3.4.1,<4.0.0",),
	"tabular-lightgbm": BASE_TRAINING_DEPS + ("lightgbm>=4.0.0",),
	"tabular-onnx": BASE_TRAINING_DEPS + ("onnxruntime>=1.17.0",),
	"dl-pytorch-gpu": BASE_TRAINING_DEPS + ("torch>=2.2.0",),
	"dl-pyg-gpu": BASE_TRAINING_DEPS + ("torch>=2.2.0", "torch-geometric>=2.5.0"),
}


def get_profile_dependencies(runtime_profile: str = "tabular-sklearn") -> Tuple[str, ...]:
	"""Return pinned pip requirements for the given runtime_profile."""
	return RUNTIME_PROFILE_DEPS.get(runtime_profile, RUNTIME_PROFILE_DEPS["tabular-sklearn"])


def build_modal_image(modal_mod: Any, runtime_profile: str = "tabular-sklearn") -> Any:
	"""Build an isolated Modal Debian Slim Python 3.12 image for the resolved runtime_profile."""
	deps = get_profile_dependencies(runtime_profile)
	return (
		modal_mod.Image.debian_slim(python_version="3.12")
		.pip_install(*deps)
		.add_local_python_source("usfds_core")
	)
