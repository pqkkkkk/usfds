"""Modal serverless entrypoint for remote USFDS training runs (ISS-009).

Deploy manually with:
	modal deploy usfds-infra/src/usfds_infra/compute/modal_app.py
"""
from typing import Any, Dict

from usfds_core.domain.schemas.training_payload import RemoteTrainingJobSpec
from usfds_core.services.training.executor import TrainingRunExecutor
from usfds_core.storage.presigned_storage import PresignedUrlStorage


def execute_remote_training_spec(spec_dict: Dict[str, Any]) -> Dict[str, Any]:
	"""Pure execution entrypoint shared by Modal CPU/GPU functions and local tests."""
	spec = RemoteTrainingJobSpec.model_validate(spec_dict)
	storage = PresignedUrlStorage(
		read_urls=spec.read_urls,
		write_urls=spec.write_urls,
	)
	executor = TrainingRunExecutor(file_storage=storage)
	result = executor.run(spec.payload)
	return result.model_dump(mode="json")


try:
	import modal  # type: ignore[import-not-found]

	app = modal.App("usfds-training")
	image = (
		modal.Image.debian_slim(python_version="3.12")
		.pip_install(
			"pydantic>=2.0",
			"pandas>=2.0",
			"numpy>=1.26",
			"pyarrow>=15.0",
			"scikit-learn>=1.5",
			"xgboost>=2.0",
			"joblib>=1.3",
		)
		.add_local_python_source("usfds_core")
	)

	@app.function(image=image, cpu=4.0, memory=8192, timeout=14400)
	def run_usfds_training_cpu(spec_dict: Dict[str, Any]) -> Dict[str, Any]:
		return execute_remote_training_spec(spec_dict)

	@app.function(image=image, gpu="T4", cpu=4.0, memory=16384, timeout=14400)
	def run_usfds_training_gpu(spec_dict: Dict[str, Any]) -> Dict[str, Any]:
		return execute_remote_training_spec(spec_dict)

except ImportError:
	app = None
	run_usfds_training_cpu = None
	run_usfds_training_gpu = None
