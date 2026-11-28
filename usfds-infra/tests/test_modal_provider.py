"""Acceptance tests for Modal dynamic profile images and zero-deploy Sandbox provider (ISS-009)."""
from types import SimpleNamespace
from uuid import uuid4

from usfds_core.domain.schemas.training_payload import (
	RemoteTrainingJobSpec,
	TrainingRunPayload,
	TrainingRunResult,
)
from usfds_infra.compute.modal_provider import ModalTrainingProvider
from usfds_infra.storage.local_storage import LocalFileStorage


class _FakeModalImage:
	def __init__(self, python_version: str = "3.12"):
		self.python_version = python_version
		self.pip_packages: list[str] = []
		self.local_python_sources: list[str] = []

	def pip_install(self, *packages: str) -> "_FakeModalImage":
		self.pip_packages.extend(packages)
		return self

	def add_local_python_source(self, *module_names: str) -> "_FakeModalImage":
		self.local_python_sources.extend(module_names)
		return self


class _FakeOutputStream:
	def __init__(self, content: str = ""):
		self._content = content

	def read(self) -> str:
		return self._content


class _FakeModalSandbox:
	def __init__(self, object_id: str, exit_code=None, stdout: str = "", stderr: str = ""):
		self.object_id = object_id
		self._exit_code = exit_code
		self.stdout = _FakeOutputStream(stdout)
		self.stderr = _FakeOutputStream(stderr)
		self.terminated = False

	def poll(self):
		return self._exit_code

	def terminate(self):
		self.terminated = True


class _FakeModalSdk:
	def __init__(self):
		self.lookup_calls: list[dict] = []
		self.create_calls: list[dict] = []
		self.sandboxes: dict[str, _FakeModalSandbox] = {}
		self.Image = SimpleNamespace(
			debian_slim=lambda python_version="3.12": _FakeModalImage(python_version=python_version)
		)
		self.App = SimpleNamespace(lookup=self._app_lookup)
		self.Sandbox = SimpleNamespace(
			create=self._sandbox_create,
			from_id=self._sandbox_from_id,
		)

	def _app_lookup(self, name: str, create_if_missing: bool = False):
		self.lookup_calls.append({"name": name, "create_if_missing": create_if_missing})
		return SimpleNamespace(name=name)

	def _sandbox_create(self, *args, **kwargs):
		sb_id = f"sb-modal-{len(self.create_calls) + 1}"
		self.create_calls.append({"args": args, "kwargs": kwargs, "object_id": sb_id})
		sb = _FakeModalSandbox(object_id=sb_id, exit_code=None)
		self.sandboxes[sb_id] = sb
		return sb

	def _sandbox_from_id(self, sb_id: str):
		return self.sandboxes[sb_id]


class _LocalhostPresignedStorage:
	def generate_presigned_upload_url(self, file_path: str, content_type=None, expires_in: int = 900) -> str:
		return f"http://localhost:9000/usfds/{file_path.lstrip('/')}?X-Amz-Expires={expires_in}"

	def generate_presigned_download_url(self, file_path: str, filename=None, expires_in: int = 900) -> str:
		return f"http://localhost:9000/usfds/{file_path.lstrip('/')}?X-Amz-Expires={expires_in}"


def test_modal_image_builder_selects_minimal_pinned_dependencies_per_profile():
	"""ISS-009: build_modal_image installs minimal profile deps with pinned scikit-learn and excludes heavy non-training deps."""
	from usfds_infra.compute.modal_images import RUNTIME_PROFILE_DEPS, build_modal_image

	fake_modal = _FakeModalSdk()
	profiles = [
		"tabular-sklearn",
		"tabular-gbdt",
		"tabular-lightgbm",
		"tabular-onnx",
		"dl-pytorch-gpu",
		"dl-pyg-gpu",
	]

	for profile in profiles:
		assert profile in RUNTIME_PROFILE_DEPS
		img = build_modal_image(fake_modal, profile)
		pkgs = img.pip_packages
		joined = " ".join(pkgs)

		assert "usfds_core" in img.local_python_sources
		assert "scikit-learn>=1.4.0,<1.6.0" in pkgs
		for forbidden in ("duckdb", "ladybug", "shap", "imblearn", "category_encoders"):
			assert forbidden not in joined

		has_torch = any(p == "torch" or p.startswith("torch>") or p.startswith("torch=") for p in pkgs)
		if profile.startswith("dl-"):
			assert has_torch, f"Expected torch in {profile}: {pkgs}"
		else:
			assert not has_torch, f"Unexpected torch in non-DL profile {profile}: {pkgs}"

	assert any("xgboost" in p for p in build_modal_image(fake_modal, "tabular-gbdt").pip_packages)
	assert any("lightgbm" in p for p in build_modal_image(fake_modal, "tabular-lightgbm").pip_packages)
	assert any("onnxruntime" in p for p in build_modal_image(fake_modal, "tabular-onnx").pip_packages)
	assert any("torch-geometric" in p for p in build_modal_image(fake_modal, "dl-pyg-gpu").pip_packages)


def test_modal_sandbox_provider_zero_deploy_submit_poll_cancel_and_localhost_guard(s3_storage, tmp_path):
	"""ISS-009: ModalTrainingProvider blocks localhost S3 endpoints and handles zero-deploy Sandbox submit/poll/cancel."""
	fake_sdk = _FakeModalSdk()

	# 1. Unavailable when disabled
	disabled_provider = ModalTrainingProvider(
		enabled=False,
		app_name="usfds-training",
		file_storage=s3_storage,
		modal_module=fake_sdk,
		token_id="ak-test",
		token_secret="as-test",
	)
	ok, reason = disabled_provider.is_available()
	assert ok is False
	assert reason

	# 2. Unavailable when storage is LocalFileStorage
	local_provider = ModalTrainingProvider(
		enabled=True,
		app_name="usfds-training",
		file_storage=LocalFileStorage(base_dir=tmp_path / "local"),
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
		file_storage=s3_storage,
		modal_module=fake_sdk,
		token_id="",
		token_secret="",
	)
	ok, reason = no_token_provider.is_available()
	assert ok is False
	assert reason

	# 4. Blocked when presigned S3 endpoint points to localhost
	localhost_provider = ModalTrainingProvider(
		enabled=True,
		app_name="usfds-training",
		file_storage=_LocalhostPresignedStorage(),
		modal_module=fake_sdk,
		token_id="ak-test",
		token_secret="as-test",
	)
	ok, reason = localhost_provider.is_available()
	assert ok is False
	assert "localhost" in (reason or "").lower()

	# 5. Available with S3 + Modal credentials + SDK (and explicit allow_localhost_presigned=True works for local tests)
	provider = ModalTrainingProvider(
		enabled=True,
		app_name="usfds-training",
		gpu_type="T4",
		cpu_cores=4.0,
		memory_mb=8192,
		gpu_memory_mb=16384,
		timeout_seconds=14400,
		file_storage=s3_storage,
		modal_module=fake_sdk,
		token_id="ak-test",
		token_secret="as-test",
	)
	ok, reason = provider.is_available()
	assert ok is True
	assert reason is None

	# 6. Submit GPU job via App.lookup(create_if_missing=True) + Sandbox.create with USFDS_SPEC_GET_URL
	run_id = uuid4()
	model_id = uuid4()
	spec_url = f"https://s3.test/get/models/{model_id}/runs/{run_id}/remote_job_spec.json"
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
		runtime_profile="dl-pytorch-gpu",
		read_urls={"datasets/train.parquet": "https://s3.test/get/train"},
		write_urls={f"models/{model_id}/runs/{run_id}/model_bundle.zip": "https://s3.test/put/model"},
		metadata={"spec_get_url": spec_url},
	)
	sb_id = provider.submit(job_spec)
	assert sb_id == "sb-modal-1"
	assert fake_sdk.lookup_calls == [{"name": "usfds-training", "create_if_missing": True}]
	assert len(fake_sdk.create_calls) == 1
	call = fake_sdk.create_calls[0]
	assert call["args"] == ("python", "-m", "usfds_core.services.training.remote_entrypoint")
	assert call["kwargs"]["gpu"] == "T4"
	assert call["kwargs"]["memory"] == 16384
	assert call["kwargs"]["timeout"] == 14400
	assert call["kwargs"]["env"]["USFDS_SPEC_GET_URL"] == spec_url
	assert any("torch" in p for p in call["kwargs"]["image"].pip_packages)

	# 7. Poll: exit_code None -> RUNNING
	status_running = provider.poll(sb_id)
	assert status_running.state == "RUNNING"

	# 8. Poll: sentinel JSON in stdout -> COMPLETED
	result = TrainingRunResult(
		run_id=run_id,
		is_success=True,
		metrics={"accuracy": 0.92, "f1_score": 0.89},
		artifact_uri=f"models/{model_id}/runs/{run_id}/model_bundle.zip",
		framework="pytorch",
	)
	fake_sdk.sandboxes[sb_id] = _FakeModalSandbox(
		sb_id,
		exit_code=0,
		stdout=f"Training starting...\n__USFDS_RESULT_JSON__:{result.model_dump_json()}\n",
	)
	status_done = provider.poll(sb_id)
	assert status_done.state == "COMPLETED"
	assert status_done.result is not None
	assert status_done.result.is_success is True
	assert status_done.result.metrics["f1_score"] == 0.89

	# 9. Poll: non-zero exit without sentinel -> FAILED with stderr tail
	fake_sdk.sandboxes[sb_id] = _FakeModalSandbox(
		sb_id,
		exit_code=137,
		stdout="",
		stderr="CUDA OOM killed process",
	)
	status_failed = provider.poll(sb_id)
	assert status_failed.state == "FAILED"
	assert "CUDA OOM" in (status_failed.error_message or "")

	# 10. Cancel calls sb.terminate()
	assert provider.cancel(sb_id) is True
	assert fake_sdk.sandboxes[sb_id].terminated is True
