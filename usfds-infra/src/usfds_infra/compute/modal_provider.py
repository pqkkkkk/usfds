"""Modal serverless compute provider adapter implementing IRemoteComputeProvider (ISS-009)."""
import importlib
import os
from typing import Any, List, Optional, Tuple

from usfds_core.domain.schemas.training_payload import (
	RemoteJobStatus,
	RemoteTrainingJobSpec,
	TrainingRunResult,
)
from usfds_core.services.training.providers.base_provider import IRemoteComputeProvider
from usfds_core.storage.base_storage import IFileStorage


class ModalTrainingProvider(IRemoteComputeProvider):
	"""Offloads TrainingRun jobs to Modal serverless functions using presigned URLs + polling."""

	def __init__(
		self,
		enabled: bool = False,
		app_name: str = "usfds-training",
		cpu_fn_name: str = "run_usfds_training_cpu",
		gpu_fn_name: str = "run_usfds_training_gpu",
		file_storage: Optional[IFileStorage] = None,
		modal_module: Optional[Any] = None,
		token_id: Optional[str] = None,
		token_secret: Optional[str] = None,
	):
		self._enabled = enabled
		self._app_name = app_name
		self._cpu_fn_name = cpu_fn_name
		self._gpu_fn_name = gpu_fn_name
		self._file_storage = file_storage
		self._modal_module = modal_module
		self._token_id = token_id if token_id is not None else os.getenv("MODAL_TOKEN_ID", "")
		self._token_secret = (
			token_secret if token_secret is not None else os.getenv("MODAL_TOKEN_SECRET", "")
		)

	@property
	def provider_id(self) -> str:
		return "modal"

	@property
	def display_name(self) -> str:
		return "Modal Serverless"

	@property
	def supported_tiers(self) -> List[str]:
		return ["cpu", "gpu"]

	def _load_modal_sdk(self) -> Optional[Any]:
		if self._modal_module is not None:
			return self._modal_module
		try:
			self._modal_module = importlib.import_module("modal")
			return self._modal_module
		except ImportError:
			return None

	def _storage_supports_presigned(self) -> bool:
		if self._file_storage is None:
			return False
		# Check if storage overrides base_storage's default None-returning presigned URL methods
		upload_fn = getattr(self._file_storage, "generate_presigned_upload_url", None)
		download_fn = getattr(self._file_storage, "generate_presigned_download_url", None)
		if upload_fn is None or download_fn is None:
			return False
		try:
			# LocalFileStorage inherits IFileStorage's default which returns None.
			probe = upload_fn("_usfds_presigned_probe", expires_in=60)
			return bool(probe)
		except Exception:
			return False

	def is_available(self) -> Tuple[bool, Optional[str]]:
		if not self._enabled:
			return False, "Modal chưa được bật (USFDS_MODAL_ENABLED=false)."
		if not self._app_name:
			return False, "Thiếu cấu hình USFDS_MODAL_APP_NAME."
		if not self._storage_supports_presigned():
			return False, "Remote compute yêu cầu S3 storage hỗ trợ presigned URL (USFDS_STORAGE_BACKEND=s3)."
		if not (self._token_id and self._token_secret):
			return False, "Thiếu thông tin xác thực Modal (MODAL_TOKEN_ID / MODAL_TOKEN_SECRET)."
		if self._load_modal_sdk() is None:
			return False, "Chưa cài đặt gói optional 'modal' SDK trong môi trường server."
		return True, None

	def submit(self, job_spec: RemoteTrainingJobSpec) -> str:
		ok, reason = self.is_available()
		if not ok:
			raise RuntimeError(f"ModalTrainingProvider is not available: {reason}")
		modal_mod = self._load_modal_sdk()
		assert modal_mod is not None

		fn_name = self._gpu_fn_name if job_spec.resource_tier == "gpu" else self._cpu_fn_name
		fn = modal_mod.Function.from_name(self._app_name, fn_name)
		call = fn.spawn(job_spec.model_dump(mode="json"))
		return str(call.object_id)

	def poll(self, external_job_id: str, timeout_seconds: float = 5.0) -> RemoteJobStatus:
		modal_mod = self._load_modal_sdk()
		if modal_mod is None:
			return RemoteJobStatus(
				state="FAILED",
				error_message="Modal SDK is not installed.",
			)
		try:
			call = modal_mod.FunctionCall.from_id(external_job_id)
			# Non-blocking check (timeout=0): raises TimeoutError if still executing
			raw_result = call.get(timeout=0)
		except TimeoutError:
			return RemoteJobStatus(state="RUNNING")
		except Exception as exc:
			return RemoteJobStatus(state="FAILED", error_message=str(exc))

		try:
			result = (
				raw_result
				if isinstance(raw_result, TrainingRunResult)
				else TrainingRunResult.model_validate(raw_result)
			)
		except Exception as exc:
			return RemoteJobStatus(
				state="FAILED",
				error_message=f"Invalid TrainingRunResult payload from Modal: {exc}",
			)

		if result.is_success:
			return RemoteJobStatus(state="COMPLETED", result=result)
		return RemoteJobStatus(
			state="FAILED",
			result=result,
			error_message=result.error_message or "Remote training job failed on Modal.",
		)
