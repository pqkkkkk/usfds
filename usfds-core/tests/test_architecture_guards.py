"""Automated architecture & invariant fitness guards for usfds-core (INV-005, INV-007, INV-009, INV-013, INV-016, P-04)."""
import ast
from pathlib import Path

import numpy as np
import pandas as pd

from usfds_core.domain.entities.enums import PipelineStage
from usfds_core.domain.schemas.artifact_output import STAGE_OUTPUT_SCHEMA_MAP
from usfds_core.domain.schemas.inference_payload import ActiveRuleSnapshot
from usfds_core.domain.schemas.preprocessing_config import NON_ML_COLUMNS, SystemColumn
from usfds_core.services.inference.executor import BatchInferenceExecutor

CORE_SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "usfds_core"

# INV-005: usfds-core must never depend on infra, delivery, or external storage/web/queue frameworks.
FORBIDDEN_CORE_IMPORTS: frozenset[str] = frozenset({
	"usfds_infra",
	"usfds_server",
	"usfds_worker",
	"usfds_cli",
	"usfds_agent",
	"sqlalchemy",
	"alembic",
	"fastapi",
	"starlette",
	"uvicorn",
	"boto3",
	"botocore",
	"bullmq",
	"modal",
})

# INV-007: modules that handle large datasets/analytics via bounded DuckDB must never load full files with pandas.
LARGE_DATA_DUCKDB_PATHS: tuple[str, ...] = (
	"services/insight_report",
	"services/warehouse",
	"services/data_management",
	"services/investigation/duckdb_engine.py",
	"services/investigation/behavior_profile.py",
	"services/investigation/network_graph.py",
	"services/inference/prediction_results.py",
)

FORBIDDEN_PANDAS_FILE_READERS: frozenset[str] = frozenset({
	"read_csv",
	"read_parquet",
	"read_json",
	"read_excel",
})


def _iter_python_files(root: Path) -> list[Path]:
	if root.is_file():
		return [root]
	return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _extract_imported_modules(file_path: Path) -> list[tuple[int, str]]:
	tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
	imports: list[tuple[int, str]] = []
	for node in ast.walk(tree):
		if isinstance(node, ast.Import):
			for alias in node.names:
				imports.append((node.lineno, alias.name))
		elif isinstance(node, ast.ImportFrom) and node.module:
			imports.append((node.lineno, node.module))
	return imports


def test_core_has_no_forbidden_infra_or_web_imports():
	"""INV-005: usfds-core maintains strict inward Clean Architecture dependency direction."""
	violations: list[str] = []
	for py_file in _iter_python_files(CORE_SRC_ROOT):
		rel = py_file.relative_to(CORE_SRC_ROOT)
		for lineno, module in _extract_imported_modules(py_file):
			top_level = module.split(".", 1)[0]
			if top_level in FORBIDDEN_CORE_IMPORTS:
				violations.append(f"{rel}:{lineno} imports forbidden module '{module}'")
	assert not violations, "Clean Architecture boundary violation(s) in usfds-core:\n" + "\n".join(violations)


def test_worker_executors_do_not_depend_on_repositories():
	"""INV-005: TrainingRunExecutor and BatchInferenceExecutor have zero direct DB/repository dependencies."""
	executor_files = [
		CORE_SRC_ROOT / "services" / "training" / "executor.py",
		CORE_SRC_ROOT / "services" / "inference" / "executor.py",
	]
	violations: list[str] = []
	for py_file in executor_files:
		assert py_file.exists(), f"Expected executor file missing: {py_file}"
		rel = py_file.relative_to(CORE_SRC_ROOT)
		for lineno, module in _extract_imported_modules(py_file):
			if module == "usfds_core.repositories" or module.startswith("usfds_core.repositories."):
				violations.append(f"{rel}:{lineno} imports repository '{module}'")
	assert not violations, "Worker executor must not depend on repositories:\n" + "\n".join(violations)


def test_large_data_modules_do_not_call_pandas_full_file_readers():
	"""INV-007: Bounded DuckDB modules must not fall back to full-file pandas read_csv/read_parquet."""
	violations: list[str] = []
	for rel_target in LARGE_DATA_DUCKDB_PATHS:
		target = CORE_SRC_ROOT / rel_target
		assert target.exists(), f"Expected guarded path missing: {target}"
		for py_file in _iter_python_files(target):
			rel = py_file.relative_to(CORE_SRC_ROOT)
			tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
			for node in ast.walk(tree):
				if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
					if node.func.attr in FORBIDDEN_PANDAS_FILE_READERS:
						owner = node.func.value
						if isinstance(owner, ast.Name) and owner.id in {"pd", "pandas"}:
							violations.append(f"{rel}:{node.lineno} calls {owner.id}.{node.func.attr}()")
	assert not violations, "Large-data DuckDB guard violated (INV-007):\n" + "\n".join(violations)


def test_two_tier_feature_engineering_contract_and_core_non_ml_columns():
	"""INV-009: Core identifiers are excluded from ML features, and pipeline stage output keys remain stable."""
	for core_non_ml in (SystemColumn.EVENT_ID.value, SystemColumn.USER_ID.value, SystemColumn.TIMESTAMP.value, SystemColumn.LABEL.value):
		assert core_non_ml in NON_ML_COLUMNS
	fe_fields = STAGE_OUTPUT_SCHEMA_MAP[PipelineStage.FEATURE_ENGINEERED].model_fields
	assert "train" in fe_fields
	assert "fitted_engineers" in fe_fields
	assert "mapped" in STAGE_OUTPUT_SCHEMA_MAP[PipelineStage.MAPPED].model_fields


def test_hybrid_decision_precedence_invariants():
	"""INV-013 / BR-DT-07: Rule REJECT > Rule REVIEW or (has_model & score >= threshold) > ALLOW."""
	executor = BatchInferenceExecutor(file_storage=None)  # type: ignore[arg-type]
	df = pd.DataFrame(
		[
			{"event_id": "e1", "amount": 5000.0, "flag_reject": 1, "flag_review": 1},
			{"event_id": "e2", "amount": 100.0, "flag_reject": 0, "flag_review": 1},
			{"event_id": "e3", "amount": 200.0, "flag_reject": 0, "flag_review": 0},
			{"event_id": "e4", "amount": 300.0, "flag_reject": 0, "flag_review": 0},
		]
	)
	rules = [
		ActiveRuleSnapshot(
			rule_id="r1",
			rule_version_id="rv1",
			rule_code="R-REJ",
			rule_name="Hard reject",
			action="REJECT",
			condition={"==": [{"var": "flag_reject"}, 1]},
		),
		ActiveRuleSnapshot(
			rule_id="r2",
			rule_version_id="rv2",
			rule_code="R-REV",
			rule_name="Soft review",
			action="REVIEW",
			condition={"==": [{"var": "flag_review"}, 1]},
		),
	]
	scores = np.array([0.10, 0.10, 0.85, 0.20], dtype=float)

	result_df, summary = executor._evaluate_hybrid_decisions(
		raw_df=df,
		enriched_df=df,
		model_scores=scores,
		has_model=True,
		threshold=0.50,
		use_rules=True,
		active_rules=rules,
	)

	assert list(result_df["final_action"]) == ["REJECT", "REVIEW", "REVIEW", "ALLOW"]
	assert list(result_df["is_flagged"]) == [1, 1, 1, 0]
	assert summary["reject_count"] == 1
	assert summary["review_count"] == 2
	assert summary["allow_count"] == 1


# INV-016 / P-04: frozen allowlists that may only shrink. [26-11-28]
REPO_ROOT = CORE_SRC_ROOT.parents[2]
PANDAS_SCANNED_SRC_ROOTS: tuple[str, ...] = (
	"usfds-core/src",
	"usfds-infra/src",
	"usfds-server/src",
	"usfds-worker/src",
)
PANDAS_IMPORT_ALLOWLIST: frozenset[str] = frozenset({
	# Legacy debt tracked in ISS-055. Never add entries; remove them as files migrate.
	"usfds-core/src/usfds_core/services/data_management/profiling.py",
	"usfds-core/src/usfds_core/services/data_management/service.py",
	"usfds-core/src/usfds_core/services/data_management/validation.py",
	"usfds-core/src/usfds_core/services/features/compiler.py",
	"usfds-core/src/usfds_core/services/features/feature_service.py",
	"usfds-core/src/usfds_core/services/features/script_runner.py",
	"usfds-core/src/usfds_core/services/inference/executor.py",
	"usfds-core/src/usfds_core/services/inference/inference_service.py",
	"usfds-core/src/usfds_core/services/inference/prediction_results.py",
	"usfds-core/src/usfds_core/services/inference/scoring_service.py",
	"usfds-core/src/usfds_core/services/insight_report/engine.py",
	"usfds-core/src/usfds_core/services/investigation/behavior_profile.py",
	"usfds-core/src/usfds_core/services/investigation/duckdb_engine.py",
	"usfds-core/src/usfds_core/services/investigation/explainability.py",
	"usfds-core/src/usfds_core/services/investigation/network_graph.py",
	"usfds-core/src/usfds_core/services/preprocessing/cleansers/base_cleanser.py",
	"usfds-core/src/usfds_core/services/preprocessing/cleansers/standard_cleanser.py",
	"usfds-core/src/usfds_core/services/preprocessing/cleansers/timestamp_normalizer.py",
	"usfds-core/src/usfds_core/services/preprocessing/cleansers/type_coercer.py",
	"usfds-core/src/usfds_core/services/preprocessing/feature_engineering/base_engineer.py",
	"usfds-core/src/usfds_core/services/preprocessing/feature_engineering/credit_card_engineer.py",
	"usfds-core/src/usfds_core/services/preprocessing/feature_engineering/velocity_engineer.py",
	"usfds-core/src/usfds_core/services/preprocessing/feature_engineering_service.py",
	"usfds-core/src/usfds_core/services/preprocessing/leaked_feature_engineering_service.py",
	"usfds-core/src/usfds_core/services/preprocessing/pipeline_builder.py",
	"usfds-core/src/usfds_core/services/preprocessing/preprocessing_service.py",
	"usfds-core/src/usfds_core/services/preprocessing/splitters/base_splitter.py",
	"usfds-core/src/usfds_core/services/preprocessing/splitters/temporal_splitter.py",
	"usfds-core/src/usfds_core/services/preprocessing/transformations/scalers.py",
	"usfds-core/src/usfds_core/services/project_management/schema_validator.py",
	"usfds-core/src/usfds_core/services/rule_engine/executor.py",
	"usfds-core/src/usfds_core/services/training/models/builtin_trainer.py",
	"usfds-core/src/usfds_core/services/training/models/script_trainer.py",
	"usfds-core/src/usfds_core/services/training/plugins/validator.py",
	"usfds-core/src/usfds_core/services/warehouse/normalization.py",
	"usfds-core/src/usfds_core/services/warehouse/project_warehouse.py",
	"usfds-server/src/usfds_server/routers/detection_router.py",
	"usfds-server/src/usfds_server/routers/investigation_router.py",
	"usfds-server/src/usfds_server/routers/rule_router.py",
	"usfds-worker/src/usfds_worker/handlers.py",
})
# DataFrame producers that bring pandas in without importing it (e.g. DuckDB `.df()`, Arrow `.to_pandas()`).
PANDAS_PRODUCER_METHODS: frozenset[str] = frozenset({"df", "fetchdf", "fetch_df", "to_pandas"})
CORE_ENGINE_LIBS: frozenset[str] = frozenset({"duckdb", "ladybug"})
# P-04 exception: job executors may import compute libraries directly.
CORE_ENGINE_EXEMPT_FILENAMES: frozenset[str] = frozenset({"executor.py"})
CORE_ENGINE_IMPORT_ALLOWLIST: frozenset[str] = frozenset({
	# Legacy debt tracked in ISS-057. Never add entries; remove them as files migrate.
	"usfds-core/src/usfds_core/services/data_management/duckdb_io.py",
	"usfds-core/src/usfds_core/services/features/compiler.py",
	"usfds-core/src/usfds_core/services/inference/prediction_results.py",
	"usfds-core/src/usfds_core/services/insight_report/engine.py",
	"usfds-core/src/usfds_core/services/investigation/behavior_profile.py",
	"usfds-core/src/usfds_core/services/investigation/duckdb_engine.py",
	"usfds-core/src/usfds_core/services/investigation/network_graph.py",
	"usfds-core/src/usfds_core/services/warehouse/project_warehouse.py",
})


def _scanned_files(src_roots: tuple[str, ...]) -> list[Path]:
	files: list[Path] = []
	for src_root in src_roots:
		root = REPO_ROOT / src_root
		assert root.is_dir(), f"Guarded source root missing: {root}"
		files.extend(_iter_python_files(root))
	return files


def _files_importing(src_roots: tuple[str, ...], libs: frozenset[str]) -> set[str]:
	return {
		py_file.relative_to(REPO_ROOT).as_posix()
		for py_file in _scanned_files(src_roots)
		if any(module.split(".", 1)[0] in libs for _, module in _extract_imported_modules(py_file))
	}


def _calls_pandas_producer(file_path: Path) -> bool:
	tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
	return any(
		isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
		and node.func.attr in PANDAS_PRODUCER_METHODS and not node.args
		for node in ast.walk(tree)
	)


def _files_using_pandas() -> set[str]:
	"""Files that import pandas or create pandas DataFrames via DuckDB/Arrow producers."""
	return _files_importing(PANDAS_SCANNED_SRC_ROOTS, frozenset({"pandas"})) | {
		py_file.relative_to(REPO_ROOT).as_posix()
		for py_file in _scanned_files(PANDAS_SCANNED_SRC_ROOTS)
		if _calls_pandas_producer(py_file)
	}


def test_pandas_imports_limited_to_allowlist():
	"""INV-016: pandas is forbidden for data processing; only frozen legacy files may still import it."""
	new_files = _files_using_pandas() - PANDAS_IMPORT_ALLOWLIST
	assert not new_files, "pandas is forbidden (INV-016); use DuckDB/PyArrow instead in:\n" + "\n".join(sorted(new_files))


def test_pandas_allowlist_has_no_stale_entries():
	"""INV-016: the allowlist only shrinks; remove entries for files that no longer import pandas."""
	stale = PANDAS_IMPORT_ALLOWLIST - _files_using_pandas()
	assert not stale, "Remove from PANDAS_IMPORT_ALLOWLIST (no longer use pandas):\n" + "\n".join(sorted(stale))


def test_core_engine_imports_limited_to_allowlist():
	"""P-04: usfds-core reaches duckdb/ladybug engines through ports; only job executors and frozen legacy files import them directly."""
	actual = {
		rel for rel in _files_importing(("usfds-core/src",), CORE_ENGINE_LIBS)
		if rel.rsplit("/", 1)[-1] not in CORE_ENGINE_EXEMPT_FILENAMES
	}
	new_files = actual - CORE_ENGINE_IMPORT_ALLOWLIST
	stale = CORE_ENGINE_IMPORT_ALLOWLIST - actual
	assert not new_files, "Direct duckdb/ladybug import in usfds-core (P-04); put it behind a port:\n" + "\n".join(sorted(new_files))
	assert not stale, "Remove from CORE_ENGINE_IMPORT_ALLOWLIST (no longer import duckdb/ladybug):\n" + "\n".join(sorted(stale))
