"""Acceptance tests for ModalTrainingProvider availability, submit, and poll mapping (ISS-009)."""
from types import SimpleNamespace
from uuid import uuid4

from usfds_core.domain.schemas.training_payload import (
	RemoteTrainingJobSpec,
	TrainingRunPayload,
	TrainingRunResult,
)
from usfds_infra.compute.modal_provider import ModalTrainingProvider
from usfds_infra.storage.local_storage import LocalFileStorage


class _FakeModalFunctionCall:
	def __init__(self, object_id: str, outcome):
		self.object_id = object_id
		self._outcome = outcome

	def get(self, timeout: float = 0):
		if isinstance(self._outcome, BaseException):
			raise self._outcome
		return self._outcome


class _FakeModalFunction:
	def __init__(self, call_store: dict):
		self._call_store = call_store
		self.spawn_calls: list = []

	def spawn(self, payload_dict: dict):
		self.spawn_calls.append(payload_dict)
		call_id = f"fc-modal-{len(self.spawn_calls)}"
		call = _FakeModalFunctionCall(call_id, TimeoutError("still running"))
		self._call_store[call_id] = call
		return call


class _FakeModalSdk:
	def __init__(self):
		self.calls: dict[str, _FakeModalFunctionCall] = {}
		self.cpu_fn = _FakeModalFunction(self.calls)
		self.gpu_fn = _FakeModalFunction(self.calls)
		self.Function = SimpleNamespace(from_name=self._from_name)
		self.FunctionCall = SimpleNamespace(from_id=self._from_id)

	def _from_name(self, app_name: str, fn_name: str):
		if "gpu" in fn_name.lower():
			return self.gpu_fn
		return self.cpu_fn

	def _from_id(self, call_id: str):
		return self.calls[call_id]


def test_modal_provider_availability_and_submit_poll(s3_storage, tmp_path):
	"""ISS-009: ModalTrainingProvider checks config/storage availability, submits jobs, and maps TimeoutError/result/error."""
	fake_sdk = _FakeModalSdk()

	# 1. Unavailable when disabled
	disabled_provider = ModalTrainingProvider(
		enabled=False,
		app_name="usfds-training",
		cpu_fn_name="run_usfds_training_cpu",
		gpu_fn_name="run_usfds_training_gpu",
		file_storage=s3_storage,
		modal_module=fake_sdk,
		token_id="ak-test",
		token_secret="as-test",
	)
	ok, reason = disabled_provider.is_available()
	assert ok is False
	assert reason

	# 2. Unavailable when storage is LocalFileStorage (no presigned URL support)
	local_storage = LocalFileStorage(base_dir=tmp_path / "local")
	local_provider = ModalTrainingProvider(
		enabled=True,
		app_name="usfds-training",
		cpu_fn_name="run_usfds_training_cpu",
		gpu_fn_name="run_usfds_training_gpu",
		file_storage=local_storage,
		modal_module=fake_sdk,
		token_id="ak-test",
		token_secret="as-test",
	)
	ok, reason = local_provider.is_available()
	assert ok is False
	assert "s3" in (reason or "").lower() or "presigned" in (reason or "").lower()

	# 3. Unavailable when missing Modal credentials
	no_token_provider = ModalTrainingProvider(
		enabled=True,
		app_name="usfds-training",
		cpu_fn_name="run_usfds_training_cpu",
		gpu_fn_name="run_usfds_training_gpu",
		file_storage=s3_storage,
		modal_module=fake_sdk,
		token_id="",
		token_secret="",
	)
	ok, reason = no_token_provider.is_available()
	assert ok is False
	assert reason

	# 4. Available with S3 + Modal credentials + SDK
	provider = ModalTrainingProvider(
		enabled=True,
		app_name="usfds-training",
		cpu_fn_name="run_usfds_training_cpu",
		gpu_fn_name="run_usfds_training_gpu",
		file_storage=s3_storage,
		modal_module=fake_sdk,
		token_id="ak-test",
		token_secret="as-test",
	)
	ok, reason = provider.is_available()
	assert ok is True
	assert reason is None

	# 5. Submit GPU job -> returns object_id
	run_id = uuid4()
	model_id = uuid4()
	job_spec = RemoteTrainingJobSpec(
		payload=TrainingRunPayload(
			run_id=run_id,
			model_id=model_id,
			model_name="fraud_gnn",
			execution_type="SCRIPT",
			train_storage_path="datasets/train.parquet",
			compute_target="modal",
		),
		resource_tier="gpu",
		read_urls={"datasets/train.parquet": "https://s3.test/get/train"},
		write_urls={f"models/{model_id}/runs/{run_id}/model.pt": "https://s3.test/put/model"},
	)
	call_id = provider.submit(job_spec)
	assert call_id == "fc-modal-1"
	assert len(fake_sdk.gpu_fn.spawn_calls) == 1
	assert len(fake_sdk.cpu_fn.spawn_calls) == 0

	# 6. Poll: TimeoutError -> RUNNING
	status_running = provider.poll(call_id, timeout_seconds=0.1)
	assert status_running.state == "RUNNING"

	# 7. Poll: TrainingRunResult dict -> COMPLETED
	result_dict = TrainingRunResult(
		run_id=run_id,
		is_success=True,
		metrics={"accuracy": 0.92, "f1_score": 0.89},
		artifact_uri=f"models/{model_id}/runs/{run_id}/model.pt",
		framework="pytorch",
	).model_dump(mode="json")
	fake_sdk.calls[call_id] = _FakeModalFunctionCall(call_id, result_dict)
	status_done = provider.poll(call_id, timeout_seconds=0.1)
	assert status_done.state == "COMPLETED"
	assert status_done.result is not None
	assert status_done.result.is_success is True
	assert status_done.result.metrics["f1_score"] == 0.89

	# 8. Poll: Exception -> FAILED
	fake_sdk.calls[call_id] = _FakeModalFunctionCall(call_id, RuntimeError("CUDA OOM"))
	status_failed = provider.poll(call_id, timeout_seconds=0.1)
	assert status_failed.state == "FAILED"
	assert "CUDA OOM" in (status_failed.error_message or "")
