"""Routing dispatcher that sends local/worker runs to local_dispatcher and remote runs via presigned URLs (ISS-009)."""
from typing import Dict, List, Optional

from usfds_core.domain.schemas.training_payload import (
	RemoteTrainingJobSpec,
	TrainingRunPayload,
)
from usfds_core.services.training.dispatchers.base_dispatcher import ITrainingRunDispatcher
from usfds_core.services.training.providers.base_provider import RemoteProviderRegistry
from usfds_core.storage.base_storage import IFileStorage

_STANDARD_OUTPUT_FILENAMES: List[str] = [
	"model.joblib",
	"preprocessor.joblib",
	"model.pt",
	"model.pth",
	"model.onnx",
	"model.json",
	"model_bundle.zip",
	"fitted_feature_engineers.joblib",
	"column_mapping.json",
	"metrics.json",
	"eval_predictions.parquet",
]


class RoutingTrainingDispatcher(ITrainingRunDispatcher):
	"""Routes TrainingRunPayload either to local/queue execution or a registered IRemoteComputeProvider."""

	def __init__(
		self,
		local_dispatcher: ITrainingRunDispatcher,
		provider_registry: RemoteProviderRegistry,
		file_storage: IFileStorage,
		presigned_ttl_seconds: int = 14400,
	):
		self.local_dispatcher = local_dispatcher
		self.provider_registry = provider_registry
		self.file_storage = file_storage
		self.presigned_ttl_seconds = presigned_ttl_seconds

	def build_remote_job_spec(
		self,
		payload: TrainingRunPayload,
		resource_tier: str = "cpu",
		metadata: Optional[Dict[str, object]] = None,
	) -> RemoteTrainingJobSpec:
		"""Generate presigned GET/PUT URLs for all inputs and expected outputs without leaking storage secrets."""
		read_paths: List[str] = [payload.train_storage_path]
		if payload.test_storage_path:
			read_paths.append(payload.test_storage_path)
		if payload.fe_artifact_path:
			read_paths.append(payload.fe_artifact_path)
		if payload.entrypoint_uri and self.file_storage.exists(payload.entrypoint_uri):
			read_paths.append(payload.entrypoint_uri)

		read_urls: Dict[str, str] = {}
		for path in read_paths:
			url = self.file_storage.generate_presigned_download_url(
				path,
				expires_in=self.presigned_ttl_seconds,
			)
			if not url:
				raise ValueError(
					"Remote compute requires an S3-compatible storage backend supporting presigned download URLs."
				)
			read_urls[path] = url

		output_prefix = f"models/{payload.model_id}/runs/{payload.run_id}"
		write_urls: Dict[str, str] = {}
		for filename in _STANDARD_OUTPUT_FILENAMES:
			out_path = f"{output_prefix}/{filename}"
			url = self.file_storage.generate_presigned_upload_url(
				out_path,
				expires_in=self.presigned_ttl_seconds,
			)
			if not url:
				raise ValueError(
					"Remote compute requires an S3-compatible storage backend supporting presigned upload URLs."
				)
			write_urls[out_path] = url

		tier = "gpu" if str(resource_tier).lower() == "gpu" else "cpu"
		return RemoteTrainingJobSpec(
			payload=payload,
			resource_tier=tier,
			read_urls=read_urls,
			write_urls=write_urls,
			metadata=dict(metadata or {}),
		)

	def dispatch_remote(
		self,
		payload: TrainingRunPayload,
		provider_id: str,
		resource_tier: str = "cpu",
		metadata: Optional[Dict[str, object]] = None,
	) -> str:
		provider = self.provider_registry.get(provider_id)
		if provider is None:
			raise ValueError(f"Remote compute provider '{provider_id}' is not registered.")
		ok, reason = provider.is_available()
		if not ok:
			raise ValueError(
				f"Remote compute provider '{provider_id}' is not available: {reason or 'unavailable'}."
			)
		job_spec = self.build_remote_job_spec(
			payload=payload,
			resource_tier=resource_tier,
			metadata=metadata,
		)
		return provider.submit(job_spec)

	def dispatch_run(self, payload: TrainingRunPayload) -> None:
		target = (payload.compute_target or "local").strip().lower()
		if target not in ("local", "worker") and self.provider_registry.get(target) is not None:
			self.dispatch_remote(payload=payload, provider_id=target)
			return
		self.local_dispatcher.dispatch_run(payload)
