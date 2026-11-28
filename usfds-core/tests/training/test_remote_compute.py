"""Acceptance tests for M1 remote training compute abstraction, presigned storage, policy, and sync (ISS-009)."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import json
import threading
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4
import zipfile

import pandas as pd
import pytest

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.enums import (
	ExecutionType,
	ModelVersionStatus,
	PipelineStage,
	TrainingRunStatus,
	ValidationStatus,
)
from usfds_core.domain.entities.model import Model
from usfds_core.domain.schemas.training_config import TrainingRunConfig
from usfds_core.domain.schemas.training_payload import (
	RemoteJobStatus,
	RemoteTrainingJobSpec,
	TrainingRunPayload,
	TrainingRunResult,
)
from usfds_core.repositories.in_memory_repos import (
	InMemoryDatasetArtifactRepository,
	InMemoryModelRepository,
	InMemoryModelVersionRepository,
	InMemoryTrainingRunRepository,
)
from usfds_core.services.training.compute_policy import (
	ComputePolicyThresholds,
	ComputeSelectionPolicy,
)
from usfds_core.services.training.dispatchers.base_dispatcher import ITrainingRunDispatcher
from usfds_core.services.training.dispatchers.routing_dispatcher import RoutingTrainingDispatcher
from usfds_core.services.training.executor import TrainingRunExecutor
from usfds_core.services.training.providers.base_provider import (
	IRemoteComputeProvider,
	RemoteProviderRegistry,
)
from usfds_core.services.training.training_service import TrainingOrchestrationService
from usfds_core.storage.in_memory_storage import InMemoryFileStorage
from usfds_core.storage.presigned_storage import PresignedUrlStorage


class _LocalPresignedHTTPServer:
	"""Minimal local HTTP server emulating S3 presigned GET/PUT URLs for tests."""

	def __init__(self, initial_files: Optional[Dict[str, bytes]] = None):
		self.files: Dict[str, bytes] = dict(initial_files or {})
		self._server: Optional[HTTPServer] = None
		self._thread: Optional[threading.Thread] = None

	def __enter__(self) -> "_LocalPresignedHTTPServer":
		store = self.files

		class Handler(BaseHTTPRequestHandler):
			def do_GET(self):
				key = self.path.lstrip("/")
				if key not in store:
					self.send_response(404)
					self.end_headers()
					return
				data = store[key]
				self.send_response(200)
				self.send_header("Content-Length", str(len(data)))
				self.end_headers()
				self.wfile.write(data)

			def do_PUT(self):
				key = self.path.lstrip("/")
				length = int(self.headers.get("Content-Length", "0"))
				body = self.rfile.read(length)
				store[key] = body
				self.send_response(200)
				self.end_headers()

			def log_message(self, format, *args):
				return

		self._server = HTTPServer(("127.0.0.1", 0), Handler)
		self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
		self._thread.start()
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		if self._server is not None:
			self._server.shutdown()
			self._server.server_close()

	def url_for(self, key: str) -> str:
		assert self._server is not None
		host, port = self._server.server_address
		return f"http://{host}:{port}/{key.lstrip('/')}"


class _PresignedCapableStorage(InMemoryFileStorage):
	"""InMemoryFileStorage that also emits deterministic presigned GET/PUT URLs."""

	def generate_presigned_upload_url(
		self,
		file_path: str,
		content_type: Optional[str] = None,
		expires_in: int = 900,
	) -> Optional[str]:
		return f"https://s3.test.local/put/{file_path.lstrip('/')}?expires={expires_in}"

	def generate_presigned_download_url(
		self,
		file_path: str,
		filename: Optional[str] = None,
		expires_in: int = 900,
	) -> Optional[str]:
		return f"https://s3.test.local/get/{file_path.lstrip('/')}?expires={expires_in}"


class _FakeRemoteProvider(IRemoteComputeProvider):
	"""Programmable in-memory remote compute provider for unit tests."""

	def __init__(
		self,
		provider_id: str = "modal",
		available: bool = True,
		reason: Optional[str] = None,
		poll_sequence: Optional[List[RemoteJobStatus]] = None,
	):
		self._provider_id = provider_id
		self._available = available
		self._reason = reason
		self._poll_sequence = list(poll_sequence or [])
		self.submitted_specs: List[RemoteTrainingJobSpec] = []
		self.poll_calls: List[str] = []

	@property
	def provider_id(self) -> str:
		return self._provider_id

	@property
	def display_name(self) -> str:
		return "Modal Serverless"

	def is_available(self) -> Tuple[bool, Optional[str]]:
		return self._available, self._reason

	def submit(self, job_spec: RemoteTrainingJobSpec) -> str:
		self.submitted_specs.append(job_spec)
		return f"fc-{len(self.submitted_specs)}"

	def poll(self, external_job_id: str, timeout_seconds: float = 5.0) -> RemoteJobStatus:
		self.poll_calls.append(external_job_id)
		if self._poll_sequence:
			return self._poll_sequence.pop(0)
		return RemoteJobStatus(state="RUNNING")


class _RecordingLocalDispatcher(ITrainingRunDispatcher):
	def __init__(self):
		self.payloads: List[TrainingRunPayload] = []

	def dispatch_run(self, payload: TrainingRunPayload) -> None:
		self.payloads.append(payload)


def _make_sample_parquet_bytes(rows: int = 30) -> bytes:
	df = pd.DataFrame(
		{
			"amount": [float(i * 10 + 5) for i in range(rows)],
			"velocity": [float(i % 7) for i in range(rows)],
			"is_fraud": [1 if i % 3 == 0 else 0 for i in range(rows)],
		}
	)
	buf = io.BytesIO()
	df.to_parquet(buf, index=False)
	return buf.getvalue()


def _make_minimal_script_plugin_zip() -> bytes:
	manifest = {
		"model_name": "custom_script_demo",
		"display_name": "Custom Script Demo",
		"framework": "scikit-learn",
		"entrypoint": "main.py",
		"hyperparameters": {},
	}
	main_py = """
from pathlib import Path
import joblib
import pandas as pd
from sklearn.dummy import DummyClassifier


def run_training(train_file, test_file, artifact_dir, target_column, hyperparameters):
    train_df = pd.read_parquet(train_file)
    test_df = pd.read_parquet(test_file)
    X_train = train_df.drop(columns=[target_column])
    y_train = train_df[target_column].astype(int).to_numpy()
    X_test = test_df.drop(columns=[target_column])
    y_test = test_df[target_column].astype(int).to_numpy()
    clf = DummyClassifier(strategy="prior")
    clf.fit(X_train, y_train)
    probs = clf.predict_proba(X_test)[:, -1]
    out = Path(artifact_dir)
    out.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, out / "model.joblib")
    return {"y_true": y_test.tolist(), "y_prob": probs.tolist()}


def run_inference(input_file, artifact_dir):
    df = pd.read_parquet(input_file)
    clf = joblib.load(Path(artifact_dir) / "model.joblib")
    return clf.predict_proba(df)[:, -1].tolist()
"""
	buf = io.BytesIO()
	with zipfile.ZipFile(buf, "w") as zf:
		zf.writestr("plugin_manifest.json", json.dumps(manifest))
		zf.writestr("main.py", main_py.strip())
	return buf.getvalue()


def test_presigned_storage_roundtrip_reads_and_uploads():
	"""ISS-009: PresignedUrlStorage reads mapped GET URLs, uploads mapped PUT URLs, and rejects unmapped paths."""
	with _LocalPresignedHTTPServer({"inputs/train.parquet": b"parquet-bytes"}) as http_srv:
		storage = PresignedUrlStorage(
			read_urls={"inputs/train.parquet": http_srv.url_for("inputs/train.parquet")},
			write_urls={"outputs/model.joblib": http_srv.url_for("outputs/model.joblib")},
		)

		assert storage.exists("inputs/train.parquet") is True
		assert storage.exists("inputs/missing.parquet") is False
		assert storage.read_bytes("inputs/train.parquet") == b"parquet-bytes"

		saved_path = storage.save_bytes("outputs/model.joblib", b"trained-weights")
		assert saved_path == "outputs/model.joblib"
		assert http_srv.files["outputs/model.joblib"] == b"trained-weights"

		with pytest.raises(FileNotFoundError):
			storage.read_bytes("inputs/unmapped.parquet")

		with pytest.raises(KeyError):
			storage.save_bytes("outputs/unmapped.bin", b"data")


def test_training_run_executor_runs_builtin_and_script_over_presigned_storage():
	"""ISS-009: TrainingRunExecutor executes both BUILTIN and SCRIPT models purely over PresignedUrlStorage."""
	train_bytes = _make_sample_parquet_bytes(36)
	test_bytes = _make_sample_parquet_bytes(12)
	plugin_zip = _make_minimal_script_plugin_zip()

	with _LocalPresignedHTTPServer(
		{
			"datasets/train.parquet": train_bytes,
			"datasets/test.parquet": test_bytes,
			"plugins/custom_script.zip": plugin_zip,
		}
	) as http_srv:
		# 1. BUILTIN random_forest
		builtin_model_id = uuid4()
		builtin_run_id = uuid4()
		builtin_prefix = f"models/{builtin_model_id}/runs/{builtin_run_id}"
		builtin_write_keys = [
			f"{builtin_prefix}/model.joblib",
			f"{builtin_prefix}/preprocessor.joblib",
			f"{builtin_prefix}/metrics.json",
			f"{builtin_prefix}/eval_predictions.parquet",
		]
		builtin_storage = PresignedUrlStorage(
			read_urls={
				"datasets/train.parquet": http_srv.url_for("datasets/train.parquet"),
				"datasets/test.parquet": http_srv.url_for("datasets/test.parquet"),
			},
			write_urls={k: http_srv.url_for(k) for k in builtin_write_keys},
		)
		builtin_payload = TrainingRunPayload(
			run_id=builtin_run_id,
			model_id=builtin_model_id,
			model_name="random_forest",
			execution_type="BUILTIN",
			train_storage_path="datasets/train.parquet",
			test_storage_path="datasets/test.parquet",
			target_column="is_fraud",
			hyperparameters={"n_estimators": 5, "max_depth": 3, "random_state": 42},
			compute_target="modal",
		)
		builtin_result = TrainingRunExecutor(file_storage=builtin_storage).run(builtin_payload)
		assert builtin_result.is_success is True, builtin_result.error_message
		assert f"{builtin_prefix}/model.joblib" in http_srv.files
		assert f"{builtin_prefix}/metrics.json" in http_srv.files
		assert f"{builtin_prefix}/eval_predictions.parquet" in http_srv.files

		# 2. SCRIPT plugin
		script_model_id = uuid4()
		script_run_id = uuid4()
		script_prefix = f"models/{script_model_id}/runs/{script_run_id}"
		script_write_keys = [
			f"{script_prefix}/model.joblib",
			f"{script_prefix}/model_bundle.zip",
			f"{script_prefix}/metrics.json",
			f"{script_prefix}/eval_predictions.parquet",
		]
		script_storage = PresignedUrlStorage(
			read_urls={
				"datasets/train.parquet": http_srv.url_for("datasets/train.parquet"),
				"datasets/test.parquet": http_srv.url_for("datasets/test.parquet"),
				"plugins/custom_script.zip": http_srv.url_for("plugins/custom_script.zip"),
			},
			write_urls={k: http_srv.url_for(k) for k in script_write_keys},
		)
		script_payload = TrainingRunPayload(
			run_id=script_run_id,
			model_id=script_model_id,
			model_name="custom_script_demo",
			execution_type="SCRIPT",
			entrypoint_uri="plugins/custom_script.zip",
			train_storage_path="datasets/train.parquet",
			test_storage_path="datasets/test.parquet",
			target_column="is_fraud",
			hyperparameters={},
			compute_target="modal",
		)
		script_result = TrainingRunExecutor(file_storage=script_storage).run(script_payload)
		assert script_result.is_success is True, script_result.error_message
		assert f"{script_prefix}/model_bundle.zip" in http_srv.files
		assert f"{script_prefix}/metrics.json" in http_srv.files


def test_compute_policy_selects_remote_for_dl_or_large_tabular_and_falls_back_when_unavailable():
	"""ISS-009: Auto compute policy picks GPU for DL/graph, CPU for large tabular, local for small, and falls back if unavailable."""
	policy = ComputeSelectionPolicy(thresholds=ComputePolicyThresholds(row_count_threshold=100_000))

	available_registry = RemoteProviderRegistry()
	available_registry.register(_FakeRemoteProvider(provider_id="modal", available=True))

	unavailable_registry = RemoteProviderRegistry()
	unavailable_registry.register(
		_FakeRemoteProvider(provider_id="modal", available=False, reason="Thiếu MODAL_TOKEN_ID")
	)

	rf_model = Model(model_name="random_forest", execution_type=ExecutionType.BUILTIN)
	dl_model = Model(
		model_name="fraud_gnn",
		execution_type=ExecutionType.SCRIPT,
		description="PyTorch Graph Neural Network",
	)
	small_art = DatasetArtifact(
		dataset_id=uuid4(),
		pipeline_stage=PipelineStage.PRE_PROCESSED,
		storage_path="datasets/small",
		row_count=5_000,
	)
	large_art = DatasetArtifact(
		dataset_id=uuid4(),
		pipeline_stage=PipelineStage.PRE_PROCESSED,
		storage_path="datasets/large",
		row_count=150_000,
	)

	# 1. DL / graph -> remote GPU
	rec_dl = policy.resolve(
		requested_target="auto",
		model=dl_model,
		artifact=small_art,
		plugin_framework="pytorch",
		registry=available_registry,
	)
	assert rec_dl.resolved_target == "modal"
	assert rec_dl.resource_tier == "gpu"
	assert rec_dl.provider == "modal"

	# 2. Large tabular >= 100k rows -> remote CPU
	rec_large = policy.resolve(
		requested_target="auto",
		model=rf_model,
		artifact=large_art,
		registry=available_registry,
	)
	assert rec_large.resolved_target == "modal"
	assert rec_large.resource_tier == "cpu"
	assert rec_large.provider == "modal"

	# 3. Small tabular < 100k rows -> local
	rec_small = policy.resolve(
		requested_target="auto",
		model=rf_model,
		artifact=small_art,
		registry=available_registry,
	)
	assert rec_small.resolved_target == "local"
	assert rec_small.provider is None

	# 4. Provider unavailable -> fallback local with reason
	rec_fallback = policy.resolve(
		requested_target="auto",
		model=dl_model,
		artifact=large_art,
		plugin_framework="pytorch",
		registry=unavailable_registry,
	)
	assert rec_fallback.resolved_target == "local"
	assert rec_fallback.provider is None
	assert rec_fallback.selection_reason


def test_routing_dispatcher_generates_presigned_urls_and_submits_remote_job():
	"""ISS-009: RoutingTrainingDispatcher generates presigned URLs without secrets and submits to remote provider."""
	storage = _PresignedCapableStorage()
	storage.save_bytes("datasets/train.parquet", b"train")
	storage.save_bytes("datasets/test.parquet", b"test")

	provider = _FakeRemoteProvider(provider_id="modal", available=True)
	registry = RemoteProviderRegistry()
	registry.register(provider)

	local_dispatcher = _RecordingLocalDispatcher()
	routing_dispatcher = RoutingTrainingDispatcher(
		local_dispatcher=local_dispatcher,
		provider_registry=registry,
		file_storage=storage,
		presigned_ttl_seconds=14400,
	)

	model_repo = InMemoryModelRepository()
	version_repo = InMemoryModelVersionRepository()
	run_repo = InMemoryTrainingRunRepository()
	artifact_repo = InMemoryDatasetArtifactRepository()

	model = Model(model_name="random_forest", execution_type=ExecutionType.BUILTIN)
	model_repo.save(model)
	artifact = DatasetArtifact(
		dataset_id=uuid4(),
		pipeline_stage=PipelineStage.PRE_PROCESSED,
		storage_path="datasets/art-1",
		validation_status=ValidationStatus.PASSED,
		row_count=200,
		output_paths={"train": "datasets/train.parquet", "test": "datasets/test.parquet"},
		validation_report={"target_column": "is_fraud"},
	)
	artifact_repo.save(artifact)

	service = TrainingOrchestrationService(
		dispatcher=routing_dispatcher,
		training_run_repo=run_repo,
		model_version_repo=version_repo,
		model_repo=model_repo,
		dataset_artifact_repo=artifact_repo,
		file_storage=storage,
		provider_registry=registry,
		compute_policy=ComputeSelectionPolicy(),
	)

	run = service.prepare_and_dispatch(
		TrainingRunConfig(
			model_id=model.model_id,
			dataset_artifact_id=artifact.artifact_id,
			compute_target="modal",
		),
		user_name="tester",
	)

	assert run.status == TrainingRunStatus.RUNNING
	assert run.compute_target == "modal"
	assert run.external_job_id == "fc-1"
	assert run.compute_metadata is not None
	assert run.compute_metadata["resolved_target"] == "modal"
	assert run.compute_metadata["selection_reason"]
	assert len(local_dispatcher.payloads) == 0
	assert len(provider.submitted_specs) == 1

	spec = provider.submitted_specs[0]
	assert "datasets/train.parquet" in spec.read_urls
	assert "datasets/test.parquet" in spec.read_urls
	expected_model_out = f"models/{model.model_id}/runs/{run.run_id}/model.joblib"
	expected_metrics_out = f"models/{model.model_id}/runs/{run.run_id}/metrics.json"
	assert expected_model_out in spec.write_urls
	assert expected_metrics_out in spec.write_urls
	serialized = spec.model_dump_json()
	assert "secret_key" not in serialized.lower()
	assert "access_key" not in serialized.lower()


def test_sync_remote_run_is_idempotent_and_registers_model_version():
	"""ISS-009: sync_remote_run transitions RUNNING -> COMPLETED atomically and creates exactly one ModelVersion."""
	storage = _PresignedCapableStorage()
	storage.save_bytes("datasets/train.parquet", b"train")

	model_repo = InMemoryModelRepository()
	version_repo = InMemoryModelVersionRepository()
	run_repo = InMemoryTrainingRunRepository()
	artifact_repo = InMemoryDatasetArtifactRepository()

	model = Model(model_name="random_forest", execution_type=ExecutionType.BUILTIN)
	model_repo.save(model)
	artifact = DatasetArtifact(
		dataset_id=uuid4(),
		pipeline_stage=PipelineStage.PRE_PROCESSED,
		storage_path="datasets/art-2",
		validation_status=ValidationStatus.PASSED,
		row_count=100,
		output_paths={"train": "datasets/train.parquet"},
		validation_report={"target_column": "is_fraud"},
	)
	artifact_repo.save(artifact)

	provider = _FakeRemoteProvider(provider_id="modal", available=True)
	registry = RemoteProviderRegistry()
	registry.register(provider)

	routing_dispatcher = RoutingTrainingDispatcher(
		local_dispatcher=_RecordingLocalDispatcher(),
		provider_registry=registry,
		file_storage=storage,
	)
	service = TrainingOrchestrationService(
		dispatcher=routing_dispatcher,
		training_run_repo=run_repo,
		model_version_repo=version_repo,
		model_repo=model_repo,
		dataset_artifact_repo=artifact_repo,
		file_storage=storage,
		provider_registry=registry,
		compute_policy=ComputeSelectionPolicy(),
	)

	run = service.prepare_and_dispatch(
		TrainingRunConfig(
			model_id=model.model_id,
			dataset_artifact_id=artifact.artifact_id,
			compute_target="modal",
		)
	)

	completed_result = TrainingRunResult(
		run_id=run.run_id,
		is_success=True,
		metrics={"accuracy": 0.91, "precision": 0.88, "recall": 0.85, "f1_score": 0.86},
		artifact_uri=f"models/{model.model_id}/runs/{run.run_id}/model.joblib",
		checksum_sha256="abc123",
		framework="scikit-learn",
		metrics_uri=f"models/{model.model_id}/runs/{run.run_id}/metrics.json",
		duration_seconds=12,
	)
	provider._poll_sequence = [
		RemoteJobStatus(state="RUNNING"),
		RemoteJobStatus(state="COMPLETED", result=completed_result),
		RemoteJobStatus(state="COMPLETED", result=completed_result),
	]

	# Poll 1: still RUNNING
	synced_1 = service.sync_remote_run(run.run_id)
	assert synced_1.status == TrainingRunStatus.RUNNING
	assert synced_1.version_id is None
	assert len(version_repo.list_by_model(model.model_id)) == 0

	# Poll 2: COMPLETED + registers exactly 1 CANDIDATE ModelVersion
	synced_2 = service.sync_remote_run(run.run_id)
	assert synced_2.status == TrainingRunStatus.COMPLETED
	assert synced_2.version_id is not None
	versions_after_2 = version_repo.list_by_model(model.model_id)
	assert len(versions_after_2) == 1
	assert versions_after_2[0].status == ModelVersionStatus.CANDIDATE

	# Poll 3: idempotent — does not create a duplicate ModelVersion or re-poll
	synced_3 = service.sync_remote_run(run.run_id)
	assert synced_3.status == TrainingRunStatus.COMPLETED
	assert synced_3.version_id == synced_2.version_id
	assert len(version_repo.list_by_model(model.model_id)) == 1
	assert len(provider.poll_calls) == 2


def test_importing_training_executor_does_not_load_heavy_unrelated_deps():
	"""ISS-009: Importing TrainingRunExecutor in a clean Python process must not pull duckdb/ladybug/shap/imblearn/category_encoders."""
	import subprocess
	import sys

	script = (
		"import sys\n"
		"from usfds_core.services.training.executor import TrainingRunExecutor\n"
		"forbidden = ['duckdb', 'ladybug', 'shap', 'imblearn', 'category_encoders']\n"
		"loaded = [m for m in forbidden if any(k == m or k.startswith(m + '.') for k in sys.modules)]\n"
		"assert not loaded, f'Unexpected heavy deps loaded: {loaded}'\n"
	)
	proc = subprocess.run(
		[sys.executable, "-c", script],
		capture_output=True,
		text=True,
		check=False,
	)
	assert proc.returncode == 0, f"STDERR: {proc.stderr}\nSTDOUT: {proc.stdout}"


def test_compute_policy_resolves_runtime_profile_per_model_and_framework():
	"""ISS-009: ComputeSelectionPolicy.resolve() assigns isolated runtime_profile per model and plugin framework."""
	policy = ComputeSelectionPolicy(thresholds=ComputePolicyThresholds(row_count_threshold=100_000))
	registry = RemoteProviderRegistry()
	registry.register(_FakeRemoteProvider(provider_id="modal", available=True))
	large_art = DatasetArtifact(
		dataset_id=uuid4(),
		pipeline_stage=PipelineStage.PRE_PROCESSED,
		storage_path="datasets/large",
		row_count=200_000,
	)

	rf_model = Model(model_name="random_forest", execution_type=ExecutionType.BUILTIN)
	xgb_model = Model(model_name="xgboost", execution_type=ExecutionType.BUILTIN)
	lgbm_model = Model(model_name="custom_lgbm", execution_type=ExecutionType.SCRIPT)
	onnx_model = Model(model_name="custom_onnx", execution_type=ExecutionType.SCRIPT)
	torch_model = Model(model_name="custom_mlp", execution_type=ExecutionType.SCRIPT)
	pyg_model = Model(model_name="fraud_gnn", execution_type=ExecutionType.SCRIPT)

	assert policy.resolve(requested_target="modal", model=rf_model, artifact=large_art, registry=registry).runtime_profile == "tabular-sklearn"
	assert policy.resolve(requested_target="modal", model=xgb_model, artifact=large_art, registry=registry).runtime_profile == "tabular-gbdt"
	assert policy.resolve(requested_target="modal", model=lgbm_model, artifact=large_art, plugin_framework="lightgbm", registry=registry).runtime_profile == "tabular-lightgbm"
	assert policy.resolve(requested_target="modal", model=onnx_model, artifact=large_art, plugin_framework="onnx", registry=registry).runtime_profile == "tabular-onnx"
	assert policy.resolve(requested_target="modal", model=torch_model, artifact=large_art, plugin_framework="pytorch", registry=registry).runtime_profile == "dl-pytorch-gpu"
	assert policy.resolve(requested_target="modal", model=pyg_model, artifact=large_art, plugin_framework="pyg", registry=registry).runtime_profile in ("dl-pytorch-gpu", "dl-pyg-gpu")


def test_script_plugin_with_custom_artifact_files_succeeds_over_presigned_storage():
	"""ISS-009: SCRIPT plugins emitting arbitrary auxiliary files upload only model_bundle.zip (no KeyError on PresignedUrlStorage)."""
	manifest = {
		"model_name": "custom_aux_script",
		"display_name": "Custom Aux Script",
		"framework": "scikit-learn",
		"entrypoint": "main.py",
		"hyperparameters": {},
	}
	main_py = """
from pathlib import Path
import joblib
import pandas as pd
from sklearn.dummy import DummyClassifier


def run_training(train_file, test_file, artifact_dir, target_column, hyperparameters):
    train_df = pd.read_parquet(train_file)
    test_df = pd.read_parquet(test_file)
    X_train = train_df.drop(columns=[target_column])
    y_train = train_df[target_column].astype(int).to_numpy()
    X_test = test_df.drop(columns=[target_column])
    y_test = test_df[target_column].astype(int).to_numpy()
    clf = DummyClassifier(strategy="prior")
    clf.fit(X_train, y_train)
    probs = clf.predict_proba(X_test)[:, -1]
    out = Path(artifact_dir)
    out.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, out / "model.joblib")
    (out / "custom_scaler.pkl").write_bytes(b"custom-scaler-bytes")
    (out / "vocab.json").write_text('{"tokens": ["a", "b"]}', encoding="utf-8")
    return {"y_true": y_test.tolist(), "y_prob": probs.tolist()}


def run_inference(input_file, artifact_dir):
    df = pd.read_parquet(input_file)
    clf = joblib.load(Path(artifact_dir) / "model.joblib")
    return clf.predict_proba(df)[:, -1].tolist()
"""
	buf = io.BytesIO()
	with zipfile.ZipFile(buf, "w") as zf:
		zf.writestr("plugin_manifest.json", json.dumps(manifest))
		zf.writestr("main.py", main_py.strip())
	plugin_zip = buf.getvalue()

	train_bytes = _make_sample_parquet_bytes(36)
	test_bytes = _make_sample_parquet_bytes(12)
	model_id = uuid4()
	run_id = uuid4()
	prefix = f"models/{model_id}/runs/{run_id}"
	standard_write_keys = [
		f"{prefix}/model_bundle.zip",
		f"{prefix}/metrics.json",
		f"{prefix}/eval_predictions.parquet",
	]

	with _LocalPresignedHTTPServer(
		{
			"datasets/train.parquet": train_bytes,
			"datasets/test.parquet": test_bytes,
			"plugins/custom_aux.zip": plugin_zip,
		}
	) as http_srv:
		storage = PresignedUrlStorage(
			read_urls={
				"datasets/train.parquet": http_srv.url_for("datasets/train.parquet"),
				"datasets/test.parquet": http_srv.url_for("datasets/test.parquet"),
				"plugins/custom_aux.zip": http_srv.url_for("plugins/custom_aux.zip"),
			},
			write_urls={k: http_srv.url_for(k) for k in standard_write_keys},
		)
		payload = TrainingRunPayload(
			run_id=run_id,
			model_id=model_id,
			model_name="custom_aux_script",
			execution_type="SCRIPT",
			entrypoint_uri="plugins/custom_aux.zip",
			train_storage_path="datasets/train.parquet",
			test_storage_path="datasets/test.parquet",
			target_column="is_fraud",
			hyperparameters={},
			compute_target="modal",
		)
		result = TrainingRunExecutor(file_storage=storage).run(payload)

		assert result.is_success is True, result.error_message
		assert f"{prefix}/model_bundle.zip" in http_srv.files
		assert f"{prefix}/metrics.json" in http_srv.files
		assert f"{prefix}/custom_scaler.pkl" not in http_srv.files
		assert f"{prefix}/vocab.json" not in http_srv.files

		with zipfile.ZipFile(io.BytesIO(http_srv.files[f"{prefix}/model_bundle.zip"]), "r") as zf:
			names = set(zf.namelist())
			assert "artifacts/model.joblib" in names
			assert "artifacts/custom_scaler.pkl" in names
			assert "artifacts/vocab.json" in names
			assert "src/main.py" in names


def test_remote_entrypoint_reads_spec_url_and_emits_structured_result_json(monkeypatch, capsys):
	"""ISS-009: remote_entrypoint.main() fetches spec from USFDS_SPEC_GET_URL, runs executor, and prints sentinel JSON."""
	from usfds_core.services.training.remote_entrypoint import RESULT_SENTINEL, main as remote_main

	train_bytes = _make_sample_parquet_bytes(36)
	test_bytes = _make_sample_parquet_bytes(12)
	model_id = uuid4()
	run_id = uuid4()
	prefix = f"models/{model_id}/runs/{run_id}"
	write_keys = [
		f"{prefix}/model.joblib",
		f"{prefix}/preprocessor.joblib",
		f"{prefix}/metrics.json",
		f"{prefix}/eval_predictions.parquet",
	]

	with _LocalPresignedHTTPServer(
		{
			"datasets/train.parquet": train_bytes,
			"datasets/test.parquet": test_bytes,
		}
	) as http_srv:
		spec = RemoteTrainingJobSpec(
			payload=TrainingRunPayload(
				run_id=run_id,
				model_id=model_id,
				model_name="random_forest",
				execution_type="BUILTIN",
				train_storage_path="datasets/train.parquet",
				test_storage_path="datasets/test.parquet",
				target_column="is_fraud",
				hyperparameters={"n_estimators": 5, "max_depth": 3, "random_state": 42},
				compute_target="modal",
			),
			resource_tier="cpu",
			runtime_profile="tabular-sklearn",
			read_urls={
				"datasets/train.parquet": http_srv.url_for("datasets/train.parquet"),
				"datasets/test.parquet": http_srv.url_for("datasets/test.parquet"),
			},
			write_urls={k: http_srv.url_for(k) for k in write_keys},
		)
		spec_key = f"{prefix}/remote_job_spec.json"
		http_srv.files[spec_key] = spec.model_dump_json().encode("utf-8")

		monkeypatch.setenv("USFDS_SPEC_GET_URL", http_srv.url_for(spec_key))
		exit_code = remote_main()

		assert exit_code == 0
		captured = capsys.readouterr()
		sentinel_lines = [
			line for line in captured.out.splitlines() if line.startswith(RESULT_SENTINEL)
		]
		assert len(sentinel_lines) == 1, f"Expected sentinel line in stdout, got: {captured.out}"
		parsed = TrainingRunResult.model_validate_json(
			sentinel_lines[0][len(RESULT_SENTINEL):]
		)
		assert parsed.is_success is True
		assert parsed.run_id == run_id
		assert f"{prefix}/model.joblib" in http_srv.files
		assert f"{prefix}/metrics.json" in http_srv.files


def test_training_executor_propagates_timeout_seconds_to_script_trainer(monkeypatch, tmp_path):
	"""ISS-009: TrainingRunExecutor forwards payload.timeout_seconds into ScriptPluginTrainer."""
	from usfds_core.services.training.models import trainer_factory

	recorded_calls: List[Dict[str, Any]] = []

	class _FakeScriptTrainer:
		def __init__(self, entrypoint_uri: str, timeout_seconds: Optional[int] = 600):
			recorded_calls.append(
				{"entrypoint_uri": entrypoint_uri, "timeout_seconds": timeout_seconds}
			)

		def train(self, workspace, target_column, hyperparameters, **kwargs):
			workspace.model_dir.mkdir(parents=True, exist_ok=True)
			(workspace.model_dir / "model.joblib").write_bytes(b"fake")
			workspace.output_dir.mkdir(parents=True, exist_ok=True)
			workspace.metrics_path.write_text('{"accuracy": 0.9}', encoding="utf-8")
			return {"accuracy": 0.9}

	monkeypatch.setattr(trainer_factory, "ScriptPluginTrainer", _FakeScriptTrainer)

	plugin_zip = _make_minimal_script_plugin_zip()
	storage = InMemoryFileStorage()
	storage.save_bytes("datasets/train.parquet", _make_sample_parquet_bytes(20))
	storage.save_bytes("plugins/script.zip", plugin_zip)

	payload = TrainingRunPayload(
		run_id=uuid4(),
		model_id=uuid4(),
		model_name="custom_script_demo",
		execution_type="SCRIPT",
		entrypoint_uri="plugins/script.zip",
		train_storage_path="datasets/train.parquet",
		target_column="is_fraud",
		compute_target="modal",
		timeout_seconds=1800,
	)

	result = TrainingRunExecutor(file_storage=storage).run(payload)
	assert result.is_success is True, result.error_message
	assert len(recorded_calls) == 1
	assert recorded_calls[0]["timeout_seconds"] == 1800

