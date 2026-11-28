"""Modal zero-deploy Sandbox compute provider implementing IRemoteComputeProvider (ISS-009)."""
import importlib
import os
from typing import Any, List, Optional, Tuple
from urllib.parse import urlparse

from usfds_core.domain.schemas.training_payload import (
	RemoteJobStatus,
	RemoteTrainingJobSpec,
	TrainingRunResult,
)
from usfds_core.services.training.providers.base_provider import IRemoteComputeProvider
from usfds_core.services.training.remote_entrypoint import RESULT_SENTINEL
from usfds_core.storage.base_storage import IFileStorage
from usfds_infra.compute.modal_images import build_modal_image

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
_STDERR_TAIL_LIMIT = 2000


def _read_stream_text(stream: Any) -> str:
	if stream is None:
		return ""
	try:
		raw = stream.read() if callable(getattr(stream, "read", None)) else stream
		if isinstance(raw, bytes):
			return raw.decode("utf-8", errors="replace")
		return str(raw or "")
	except Exception:
		return ""


class ModalTrainingProvider(IRemoteComputeProvider):
	"""Offloads TrainingRun jobs to dynamically created Modal Sandboxes using presigned URLs + polling."""

	def __init__(
		self,
		enabled: bool = False,
		app_name: str = "usfds-training",
		gpu_type: str = "T4",
		cpu_cores: float = 4.0,
		memory_mb: int = 8192,
		gpu_memory_mb: int = 16384,
		timeout_seconds: int = 14400,
		file_storage: Optional[IFileStorage] = None,
		modal_module: Optional[Any] = None,
		token_id: Optional[str] = None,
		token_secret: Optional[str] = None,
		s3_public_endpoint_url: Optional[str] = None,
		allow_localhost_presigned: bool = False,
	):
		self._enabled = enabled
		self._app_name = app_name
		self._gpu_type = gpu_type
		self._cpu_cores = float(cpu_cores)
		self._memory_mb = int(memory_mb)
		self._gpu_memory_mb = int(gpu_memory_mb)
		self._timeout_seconds = int(timeout_seconds)
		self._file_storage = file_storage
		self._modal_module = modal_module
		self._token_id = token_id if token_id is not None else os.getenv("MODAL_TOKEN_ID", "")
		self._token_secret = (
			token_secret if token_secret is not None else os.getenv("MODAL_TOKEN_SECRET", "")
		)
		self._s3_public_endpoint_url = (
			s3_public_endpoint_url
			if s3_public_endpoint_url is not None
			else (os.getenv("USFDS_S3_PUBLIC_ENDPOINT_URL") or os.getenv("USFDS_S3_ENDPOINT_URL") or "")
		)
		self._allow_localhost_presigned = allow_localhost_presigned

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

	def _probe_presigned_url(self) -> Optional[str]:
		if self._file_storage is None:
			return None
		upload_fn = getattr(self._file_storage, "generate_presigned_upload_url", None)
		download_fn = getattr(self._file_storage, "generate_presigned_download_url", None)
		if upload_fn is None or download_fn is None:
			return None
		try:
			probe = upload_fn("_usfds_presigned_probe", expires_in=60)
			return str(probe) if probe else None
		except Exception:
			return None

	@staticmethod
	def _is_localhost_url(url: str) -> bool:
		if not url:
			return False
		parsed = urlparse(url)
		host = (parsed.hostname or "").strip().lower()
		return host in _LOOPBACK_HOSTS

	def is_available(self) -> Tuple[bool, Optional[str]]:
		if not self._enabled:
			return False, "Modal chưa được bật (USFDS_MODAL_ENABLED=false)."
		if not self._app_name:
			return False, "Thiếu cấu hình USFDS_MODAL_APP_NAME."
		probe_url = self._probe_presigned_url()
		if not probe_url:
			return False, "Remote compute yêu cầu S3 storage hỗ trợ presigned URL (USFDS_STORAGE_BACKEND=s3)."
		if not self._allow_localhost_presigned and (
			self._is_localhost_url(probe_url)
			or (self._s3_public_endpoint_url and self._is_localhost_url(self._s3_public_endpoint_url))
		):
			return (
				False,
				"USFDS_S3_PUBLIC_ENDPOINT_URL đang trỏ về localhost/loopback; Modal Sandbox trên cloud không thể truy cập.",
			)
		if not (self._token_id and self._token_secret):
			return False, "Thiếu thông tin xác thực Modal (MODAL_TOKEN_ID / MODAL_TOKEN_SECRET)."
		if self._load_modal_sdk() is None:
			return False, "Chưa cài đặt gói optional 'modal' SDK trong môi trường server."
		return True, None

	def _resolve_spec_get_url(self, job_spec: RemoteTrainingJobSpec) -> str:
		spec_get_url = job_spec.metadata.get("spec_get_url")
		if spec_get_url:
			return str(spec_get_url)
		if self._file_storage is not None:
			spec_path = f"models/{job_spec.payload.model_id}/runs/{job_spec.payload.run_id}/remote_job_spec.json"
			self._file_storage.save_bytes(spec_path, job_spec.model_dump_json().encode("utf-8"))
			generated = self._file_storage.generate_presigned_download_url(spec_path, expires_in=self._timeout_seconds)
			if generated:
				return str(generated)
		raise RuntimeError("Missing spec_get_url in RemoteTrainingJobSpec metadata.")

	def submit(self, job_spec: RemoteTrainingJobSpec) -> str:
		ok, reason = self.is_available()
		if not ok:
			raise RuntimeError(f"ModalTrainingProvider is not available: {reason}")
		modal_mod = self._load_modal_sdk()
		assert modal_mod is not None

		spec_get_url = self._resolve_spec_get_url(job_spec)
		app = modal_mod.App.lookup(self._app_name, create_if_missing=True)
		image = build_modal_image(modal_mod, runtime_profile=job_spec.runtime_profile)

		is_gpu = str(job_spec.resource_tier).lower() == "gpu"
		memory = self._gpu_memory_mb if is_gpu else self._memory_mb
		timeout = int(job_spec.payload.timeout_seconds or self._timeout_seconds)

		create_kwargs: dict[str, Any] = {
			"app": app,
			"image": image,
			"cpu": self._cpu_cores,
			"memory": memory,
			"timeout": timeout,
			"env": {"USFDS_SPEC_GET_URL": spec_get_url},
		}
		if is_gpu and self._gpu_type:
			create_kwargs["gpu"] = self._gpu_type

		sb = modal_mod.Sandbox.create(
			"python",
			"-m",
			"usfds_core.services.training.remote_entrypoint",
			**create_kwargs,
		)
		return str(sb.object_id)

	def poll(self, external_job_id: str, timeout_seconds: float = 5.0) -> RemoteJobStatus:
		modal_mod = self._load_modal_sdk()
		if modal_mod is None:
			return RemoteJobStatus(
				state="FAILED",
				error_message="Modal SDK is not installed.",
			)
		try:
			sb = modal_mod.Sandbox.from_id(external_job_id)
			exit_code = sb.poll()
		except Exception as exc:
			return RemoteJobStatus(state="FAILED", error_message=str(exc))

		if exit_code is None:
			return RemoteJobStatus(state="RUNNING")

		stdout_text = _read_stream_text(getattr(sb, "stdout", None))
		for line in reversed(stdout_text.splitlines()):
			if line.startswith(RESULT_SENTINEL):
				raw_json = line[len(RESULT_SENTINEL):]
				try:
					result = TrainingRunResult.model_validate_json(raw_json)
				except Exception as exc:
					return RemoteJobStatus(
						state="FAILED",
						error_message=f"Invalid TrainingRunResult sentinel JSON from Modal: {exc}",
					)
				if result.is_success:
					return RemoteJobStatus(state="COMPLETED", result=result)
				return RemoteJobStatus(
					state="FAILED",
					result=result,
					error_message=result.error_message or "Remote training job failed on Modal.",
				)

		stderr_text = _read_stream_text(getattr(sb, "stderr", None))
		tail = (stderr_text or stdout_text).strip()[-_STDERR_TAIL_LIMIT:]
		if tail:
			msg = f"Modal Sandbox exited with code {exit_code}: {tail}"
		else:
			msg = f"Modal Sandbox exited with code {exit_code} without result sentinel."
		return RemoteJobStatus(state="FAILED", error_message=msg)

	def cancel(self, external_job_id: str) -> bool:
		modal_mod = self._load_modal_sdk()
		if modal_mod is None:
			return False
		try:
			sb = modal_mod.Sandbox.from_id(external_job_id)
			sb.terminate()
			return True
		except Exception:
			return False
