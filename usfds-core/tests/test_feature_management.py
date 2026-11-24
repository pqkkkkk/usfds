"""M1 acceptance tests for Feature Management & Dynamic 2-Tier Feature Engine (ISS-040)."""
import io
import json
from uuid import uuid4

import joblib
import pandas as pd
import pytest

from usfds_core.domain.entities.enums import (
	FeatureComputeKind,
	FeatureMegafamily,
	FeatureStatus,
	LogicalDataType,
	ProjectStatus,
	RuleAction,
	RuleStatus,
)
from usfds_core.domain.entities.system import Project
from usfds_core.domain.schemas.inference_payload import ActiveRuleSnapshot, BatchInferencePayload
from usfds_core.domain.schemas.preprocessing_config import (
	DataMappingConfig,
	FeatureEngineeringConfig,
	SplitConfig,
)
from usfds_core.domain.schemas.project_schema import ColumnSchemaSpec, ProjectRawSchema
from usfds_core.domain.schemas.system_metadata import build_default_system_columns
from usfds_core.repositories.in_memory_repos import (
	InMemoryFeatureRepository,
	InMemoryFeatureSetRepository,
	InMemoryProjectRepository,
	InMemoryRuleRepository,
	InMemoryRuleVersionRepository,
)
from usfds_core.services.features import (
	BatchedFeatureScriptRunner,
	CompiledFeaturePipeline,
	FeatureCompatibilityService,
	FeatureManagementService,
	build_builtin_features_and_sets,
	validate_feature_code,
	parse_safe_expression,
)
from usfds_core.services.inference.executor import BatchInferenceExecutor
from usfds_core.services.rule_engine.executor import RuleExecutor
from usfds_core.services.rule_engine.manager import RuleManager
from usfds_core.storage.in_memory_storage import InMemoryFileStorage


def test_builtin_catalog_and_compatibility_across_heterogeneous_datasets():
	"""Built-in catalog covers 5 Megafamilies + Monetary and evaluates heterogeneous dataset schemas accurately."""
	features, feature_sets = build_builtin_features_and_sets()
	assert len(features) >= 28
	assert len(feature_sets) == 5
	for f in features:
		assert f.is_builtin is True
		assert f.project_id is None
		if f.compute_kind == FeatureComputeKind.PYTHON_CODE:
			assert f.source_code and "def compute" in f.source_code

	set_keys = {fs.set_key for fs in feature_sets}
	assert {
		"pkg_ccfd_standard",
		"pkg_ecommerce_cnp",
		"pkg_geo_behavioral",
		"pkg_network_ring",
		"pkg_minimal_anonymized",
	} == set_keys

	compat_svc = FeatureCompatibilityService(system_metadata=build_default_system_columns())

	# 1. creditcard.csv style (anonymized V1..V28 + core cols)
	cc_cols = ["event_id", "timestamp", "amount", "user_id", "label"] + [f"V{i}" for i in range(1, 29)]
	cc_report = {item.feature_key: item for item in compat_svc.evaluate(features, cc_cols).items}
	assert cc_report["hour_of_day"].status == "AVAILABLE"
	assert cc_report["tx_freq_last_1h"].status == "AVAILABLE"
	assert cc_report["amount_to_user_avg_30d"].status == "AVAILABLE"
	assert cc_report["geo_distance_km"].status == "MISSING_INPUTS"
	assert "lat" in cc_report["geo_distance_km"].missing_inputs
	assert cc_report["email_digit_ratio"].status == "MISSING_INPUTS"
	assert cc_report["device_distinct_users"].status == "MISSING_INPUTS"

	# 2. sparkov style (+ merchant, category, lat, long, merch_lat, merch_long)
	sparkov_cols = ["event_id", "timestamp", "amount", "user_id", "label", "merchant", "category", "lat", "long", "merch_lat", "merch_long"]
	sparkov_report = {item.feature_key: item for item in compat_svc.evaluate(features, sparkov_cols).items}
	assert sparkov_report["geo_distance_km"].status == "AVAILABLE"
	assert sparkov_report["user_merchant_freq_30d"].status == "AVAILABLE"

	# 3. aws-samples / e-commerce style (+ email, country, bin_country, device_id, ip_address)
	ecom_cols = ["event_id", "timestamp", "amount", "user_id", "label", "email", "country", "bin_country", "device_id", "ip_address"]
	ecom_report = {item.feature_key: item for item in compat_svc.evaluate(features, ecom_cols).items}
	assert ecom_report["email_digit_ratio"].status == "AVAILABLE"
	assert ecom_report["country_bin_mismatch"].status == "AVAILABLE"
	assert ecom_report["device_distinct_users"].status == "AVAILABLE"


def test_compiled_pipeline_duckdb_velocity_stacked_dag_and_anti_leakage(tmp_path):
	"""DuckDB bounded velocity + stacked expression + train-only target rate parity across joblib reload."""
	features, _ = build_builtin_features_and_sets()
	by_key = {f.feature_key: f for f in features}
	selected = [
		by_key["user_avg_amount_30d"],
		by_key["amount_to_user_avg_30d"],  # stacked EXPRESSION on user_avg_amount_30d
		by_key["merchant_hist_fraud_rate"],  # TARGET_RATE (requires_label=True)
	]

	train_df = pd.DataFrame(
		{
			"event_id": ["E1", "E2", "E3", "E4"],
			"timestamp": pd.to_datetime([
				"2026-01-01 10:00:00",
				"2026-01-01 11:00:00",
				"2026-01-01 12:00:00",
				"2026-01-01 13:00:00",
			]),
			"amount": [100.0, 300.0, 200.0, 400.0],
			"user_id": ["U1", "U1", "U2", "U1"],
			"merchant": ["M_RISKY", "M_RISKY", "M_SAFE", "M_SAFE"],
			"label": [1, 1, 0, 0],
		}
	)
	test_df = pd.DataFrame(
		{
			"event_id": ["E5", "E6"],
			"timestamp": pd.to_datetime([
				"2026-01-02 10:00:00",
				"2026-01-02 11:00:00",
			]),
			"amount": [400.0, 50.0],
			"user_id": ["U1", "U2"],
			"merchant": ["M_RISKY", "M_SAFE"],
			"label": [0, 1],  # Must NOT leak into TARGET_RATE on transform!
		}
	)

	pipeline = CompiledFeaturePipeline(specs=selected)
	train_out = pipeline.fit_transform(train_df)

	# Row 0 (E1, U1): causal past avg = 100.0 -> ratio = 1.0
	assert pytest.approx(float(train_out.loc[0, "user_avg_amount_30d"]), rel=1e-4) == 100.0
	assert pytest.approx(float(train_out.loc[0, "amount_to_user_avg_30d"]), rel=1e-4) == 1.0
	# Row 1 (E2, U1): causal avg of [100, 300] = 200.0 -> ratio = 300 / 200 = 1.5
	assert pytest.approx(float(train_out.loc[1, "user_avg_amount_30d"]), rel=1e-4) == 200.0
	assert pytest.approx(float(train_out.loc[1, "amount_to_user_avg_30d"]), rel=1e-4) == 1.5

	# Save and reload via joblib (pure data, zero pickled user functions)
	bundle_path = tmp_path / "fe.joblib"
	joblib.dump(pipeline, bundle_path)
	reloaded: CompiledFeaturePipeline = joblib.load(bundle_path)

	test_out = reloaded.transform(test_df)
	# Unlabeled inference copy must match test_out 100%
	unlabeled_out = reloaded.transform(test_df.drop(columns=["label"]))
	pd.testing.assert_frame_equal(
		test_out[["user_avg_amount_30d", "amount_to_user_avg_30d", "merchant_hist_fraud_rate"]],
		unlabeled_out[["user_avg_amount_30d", "amount_to_user_avg_30d", "merchant_hist_fraud_rate"]],
	)

	# Row 0 in test (E5, U1): history tail has [100, 300, 400] + current 400 -> avg = 300.0 -> ratio = 400/300
	assert pytest.approx(float(test_out.loc[0, "user_avg_amount_30d"]), rel=1e-4) == 300.0
	assert pytest.approx(float(test_out.loc[0, "amount_to_user_avg_30d"]), rel=1e-4) == pytest.approx(400.0 / 300.0, rel=1e-4)
	# M_RISKY had 2/2 fraud in train (not leaked by test E5 label=0), M_SAFE had 0/2 fraud in train
	assert float(test_out.loc[0, "merchant_hist_fraud_rate"]) > float(test_out.loc[1, "merchant_hist_fraud_rate"])


def test_dynamic_python_code_enrichments_geo_graph_and_live_edit_without_repo_change():
	"""Built-in PYTHON_CODE (email, geo, network) executes in subprocess runner; cloning & editing source_code takes effect live."""
	features, _ = build_builtin_features_and_sets()
	by_key = {f.feature_key: f for f in features}

	feat_repo = InMemoryFeatureRepository()
	set_repo = InMemoryFeatureSetRepository()
	proj_repo = InMemoryProjectRepository()
	for f in features:
		feat_repo.save(f)

	project = Project(
		project_id=uuid4(),
		user_id=uuid4(),
		project_name="Live Feature Edit Proj",
		status=ProjectStatus.ACTIVE,
	)
	proj_repo.save(project)

	feat_svc = FeatureManagementService(feature_repo=feat_repo, feature_set_repo=set_repo, project_repo=proj_repo)
	cloned = feat_svc.clone_feature(
		feature_id=by_key["is_free_email"].feature_id,
		target_project_id=project.project_id,
		user_id=project.user_id,
		new_feature_key="is_free_or_custom_email",
		created_by="ds_a",
	)
	# Live edit cloned source_code in DB repository to recognize customcorp.vn
	custom_code = cloned.source_code.replace('"proton.me"', '"proton.me", "customcorp.vn"')
	updated_clone = feat_svc.update_feature(
		feature_id=cloned.feature_id,
		project_id=project.project_id,
		source_code=custom_code,
	)
	assert "customcorp.vn" in (updated_clone.source_code or "")

	selected = [
		by_key["email_digit_ratio"],
		by_key["geo_distance_km"],
		by_key["device_distinct_users"],
		by_key["community_size"],
		by_key["community_fraud_ratio"],
		updated_clone,
	]

	train_df = pd.DataFrame(
		{
			"event_id": ["E1", "E2", "E3", "E4"],
			"timestamp": pd.to_datetime([
				"2026-01-01 01:00:00",
				"2026-01-01 02:00:00",
				"2026-01-01 03:00:00",
				"2026-01-01 04:00:00",
			]),
			"amount": [50.0, 60.0, 70.0, 80.0],
			"user_id": ["U1", "U2", "U3", "U4"],
			"email": ["alice12@gmail.com", "bob@customcorp.vn", "carol9999@yahoo.com", "dave@corp.org"],
			"ip_address": ["10.0.0.1", "8.8.8.8", "8.8.4.4", "1.1.1.1"],
			"device_id": ["DEV_RING", "DEV_RING", "DEV_OTHER", "DEV_CLEAN"],
			"lat": [10.762622, 10.762622, 21.028511, 21.028511],
			"long": [106.660172, 106.660172, 105.804817, 105.804817],
			"merch_lat": [21.028511, 10.762622, 21.028511, 21.028511],
			"merch_long": [105.804817, 106.660172, 105.804817, 105.804817],
			"label": [1, 0, 0, 0],
		}
	)

	pipeline = CompiledFeaturePipeline(specs=selected)
	train_out = pipeline.fit_transform(train_df)

	# email_digit_ratio: alice12@ -> 2 / 7 chars before @
	assert pytest.approx(float(train_out.loc[0, "email_digit_ratio"]), abs=1e-4) == 2.0 / 7.0
	# HCMC -> Hanoi Haversine distance ~ 1138-1155 km (within 1%)
	hcmc_han_km = float(train_out.loc[0, "geo_distance_km"])
	assert 1125.0 <= hcmc_han_km <= 1165.0
	assert float(train_out.loc[1, "geo_distance_km"]) < 0.01
	# Network: U1 & U2 share DEV_RING -> 2 distinct users & community_size >= 2
	assert int(train_out.loc[0, "device_distinct_users"]) == 2
	assert int(train_out.loc[0, "community_size"]) >= 2
	assert float(train_out.loc[0, "community_fraud_ratio"]) > 0.0
	# Live edited clone flags bob@customcorp.vn purely from DB source_code
	assert bool(train_out.loc[1, "is_free_or_custom_email"]) is True
	assert bool(train_out.loc[3, "is_free_or_custom_email"]) is False


def test_code_validator_and_expression_parser_block_unsafe_code_and_cycles():
	"""AST security, dependency allowlist, expression SQLi defense, cycle detection, and subprocess timeout."""
	feat_repo = InMemoryFeatureRepository()
	set_repo = InMemoryFeatureSetRepository()
	proj_repo = InMemoryProjectRepository()
	project = Project(project_id=uuid4(), user_id=uuid4(), project_name="Sec Proj", status=ProjectStatus.ACTIVE)
	proj_repo.save(project)

	feat_svc = FeatureManagementService(feature_repo=feat_repo, feature_set_repo=set_repo, project_repo=proj_repo)

	# (a) DAG cycle A <-> B blocked with ValueError
	feat_a = feat_svc.create_feature(
		project_id=project.project_id,
		user_id=project.user_id,
		feature_key="feat_a",
		display_name="Feat A",
		megafamily=FeatureMegafamily.MONETARY,
		compute_kind=FeatureComputeKind.EXPRESSION,
		output_type=LogicalDataType.NUMERIC,
		config_json={"expr": "amount * 2"},
		required_inputs=["amount"],
	)
	feat_b = feat_svc.create_feature(
		project_id=project.project_id,
		user_id=project.user_id,
		feature_key="feat_b",
		display_name="Feat B",
		megafamily=FeatureMegafamily.MONETARY,
		compute_kind=FeatureComputeKind.EXPRESSION,
		output_type=LogicalDataType.NUMERIC,
		config_json={"expr": "feat_a + 1"},
		required_inputs=["feat_a"],
		depends_on_feature_ids=[feat_a.feature_id],
	)
	with pytest.raises(ValueError, match="chu trình|cycle|vòng"):
		feat_svc.update_feature(
			feature_id=feat_a.feature_id,
			project_id=project.project_id,
			config_json={"expr": "feat_b + 1"},
			required_inputs=["feat_b"],
			depends_on_feature_ids=[feat_b.feature_id],
		)

	# (b) Unsafe expression SQLi rejected
	with pytest.raises(ValueError):
		parse_safe_expression("amount; DROP TABLE features --")

	# (c) Unsafe PYTHON_CODE blocked
	for unsafe_code in [
		"import os\ndef compute(df, params):\n    return df['amount']\n",
		"import subprocess\ndef compute(df, params):\n    return df['amount']\n",
		"def compute(df, params):\n    open('/etc/passwd')\n    return df['amount']\n",
		"def compute(df, params):\n    return eval('1+1')\n",
		"def compute(df, params):\n    return ().__class__.__bases__[0].__subclasses__()\n",
	]:
		with pytest.raises(ValueError):
			validate_feature_code(unsafe_code, is_stateful=False)

	# (d) Required package outside ALLOWED_IMPORTS blocked on create; allowed package missing on system flagged MISSING_DEPENDENCY
	with pytest.raises(ValueError):
		feat_svc.create_feature(
			project_id=project.project_id,
			user_id=project.user_id,
			feature_key="bad_pkg_feat",
			display_name="Bad Pkg",
			megafamily=FeatureMegafamily.IDENTITY,
			compute_kind=FeatureComputeKind.PYTHON_CODE,
			output_type=LogicalDataType.NUMERIC,
			config_json={"required_packages": ["requests"]},
			source_code="def compute(df, params):\n    return df['amount']\n",
			required_inputs=["amount"],
		)

	compat_svc = FeatureCompatibilityService(
		system_metadata=build_default_system_columns(),
		allowed_imports={"math", "pandas", "numpy", "nonexistent_custom_lib"},
	)
	pkg_feat = feat_svc.create_feature(
		project_id=project.project_id,
		user_id=project.user_id,
		feature_key="missing_pkg_feat",
		display_name="Missing Pkg",
		megafamily=FeatureMegafamily.IDENTITY,
		compute_kind=FeatureComputeKind.PYTHON_CODE,
		output_type=LogicalDataType.NUMERIC,
		config_json={"required_packages": ["nonexistent_custom_lib"]},
		source_code="import nonexistent_custom_lib\ndef compute(df, params):\n    return df['amount']\n",
		required_inputs=["amount"],
		allowed_imports={"math", "pandas", "numpy", "nonexistent_custom_lib"},
	)
	compat_map = {
		i.feature_key: i
		for i in compat_svc.evaluate([pkg_feat], ["amount"]).items
	}
	assert compat_map["missing_pkg_feat"].status == "MISSING_DEPENDENCY"
	assert "nonexistent_custom_lib" in compat_map["missing_pkg_feat"].missing_packages

	# (e) Infinite loop PYTHON_CODE terminated on timeout
	runner = BatchedFeatureScriptRunner(timeout_seconds=1)
	loop_df = pd.DataFrame({"amount": [10.0, 20.0]})
	with pytest.raises((TimeoutError, RuntimeError)):
		runner.run_level(
			df=loop_df,
			features=[
				feat_svc.create_feature(
					project_id=project.project_id,
					user_id=project.user_id,
					feature_key="inf_loop",
					display_name="Loop",
					megafamily=FeatureMegafamily.MONETARY,
					compute_kind=FeatureComputeKind.PYTHON_CODE,
					output_type=LogicalDataType.NUMERIC,
					source_code="def compute(df, params):\n    while True:\n        pass\n",
					required_inputs=["amount"],
				)
			],
			mode="fit_transform",
		)

	# Valid expression works on PaySim-style columns
	paysim_feat = feat_svc.create_feature(
		project_id=project.project_id,
		user_id=project.user_id,
		feature_key="balance_diff",
		display_name="Balance Diff",
		megafamily=FeatureMegafamily.MONETARY,
		compute_kind=FeatureComputeKind.EXPRESSION,
		output_type=LogicalDataType.NUMERIC,
		config_json={"expr": "oldbalanceOrg - amount - newbalanceOrig"},
		required_inputs=["oldbalanceOrg", "amount", "newbalanceOrig"],
	)
	ps_df = pd.DataFrame({
		"timestamp": pd.to_datetime(["2026-01-01 00:00:00"]),
		"oldbalanceOrg": [1000.0],
		"amount": [250.0],
		"newbalanceOrig": [750.0],
	})
	res_ps = CompiledFeaturePipeline([paysim_feat]).fit_transform(ps_df)
	assert pytest.approx(float(res_ps.loc[0, "balance_diff"]), abs=1e-6) == 0.0


def test_in_use_protection_blocks_deleting_referenced_feature():
	"""In-use protection blocks deleting Built-in, depended-on, FeatureSet-member, and ACTIVE-Rule-referenced features."""
	features, _ = build_builtin_features_and_sets()
	feat_repo = InMemoryFeatureRepository()
	set_repo = InMemoryFeatureSetRepository()
	proj_repo = InMemoryProjectRepository()
	rule_repo = InMemoryRuleRepository()
	rule_ver_repo = InMemoryRuleVersionRepository()

	for f in features:
		feat_repo.save(f)

	project = Project(
		project_id=uuid4(),
		user_id=uuid4(),
		project_name="In Use Proj",
		status=ProjectStatus.ACTIVE,
		raw_schema=ProjectRawSchema(
			columns={
				"event_id": ColumnSchemaSpec(logical_type=LogicalDataType.STRING, physical_dtype="object"),
				"timestamp": ColumnSchemaSpec(logical_type=LogicalDataType.DATETIME, physical_dtype="datetime64[ns]"),
				"amount": ColumnSchemaSpec(logical_type=LogicalDataType.NUMERIC, physical_dtype="float64"),
				"user_id": ColumnSchemaSpec(logical_type=LogicalDataType.STRING, physical_dtype="object"),
				"label": ColumnSchemaSpec(logical_type=LogicalDataType.NUMERIC, physical_dtype="int64"),
			}
		).model_dump(mode="json"),
	)
	proj_repo.save(project)

	rule_manager = RuleManager(
		rule_repo=rule_repo,
		version_repo=rule_ver_repo,
		project_repo=proj_repo,
		feature_repo=feat_repo,
	)
	feat_svc = FeatureManagementService(
		feature_repo=feat_repo,
		feature_set_repo=set_repo,
		project_repo=proj_repo,
		rule_manager=rule_manager,
	)

	# 1. Built-in cannot be deleted
	with pytest.raises(ValueError, match="Built-in|mặc định"):
		feat_svc.delete_feature(features[0].feature_id, project_id=project.project_id)

	f_base = feat_svc.create_feature(
		project_id=project.project_id,
		user_id=project.user_id,
		feature_key="f_base",
		display_name="F Base",
		megafamily=FeatureMegafamily.MONETARY,
		compute_kind=FeatureComputeKind.EXPRESSION,
		output_type=LogicalDataType.NUMERIC,
		config_json={"expr": "amount * 2"},
		required_inputs=["amount"],
	)
	f_ratio = feat_svc.create_feature(
		project_id=project.project_id,
		user_id=project.user_id,
		feature_key="f_ratio",
		display_name="F Ratio",
		megafamily=FeatureMegafamily.MONETARY,
		compute_kind=FeatureComputeKind.EXPRESSION,
		output_type=LogicalDataType.NUMERIC,
		config_json={"expr": "f_base / 2"},
		required_inputs=["f_base"],
		depends_on_feature_ids=[f_base.feature_id],
	)
	f_set = feat_svc.create_feature_set(
		project_id=project.project_id,
		user_id=project.user_id,
		set_key="custom_set",
		name="Custom Set",
		feature_ids=[f_base.feature_id],
	)
	rule, _ = rule_manager.create_rule(
		project_id=project.project_id,
		rule_code="R_ENRICHED",
		name="Rule using f_base",
		description="test",
		condition={">": [{"var": "enriched.f_base"}, 100]},
		action=RuleAction.REVIEW,
		status=RuleStatus.ACTIVE,
		user_id=project.user_id,
	)

	# Blocked by dependency (f_ratio)
	with pytest.raises(ValueError):
		feat_svc.delete_feature(f_base.feature_id, project_id=project.project_id)
	feat_svc.delete_feature(f_ratio.feature_id, project_id=project.project_id)

	# Still blocked by FeatureSet
	with pytest.raises(ValueError):
		feat_svc.delete_feature(f_base.feature_id, project_id=project.project_id)
	feat_svc.delete_feature_set(f_set.feature_set_id, project_id=project.project_id)

	# Still blocked by ACTIVE Rule
	with pytest.raises(ValueError):
		feat_svc.delete_feature(f_base.feature_id, project_id=project.project_id)
	rule_manager.set_rule_status(rule.rule_id, RuleStatus.INACTIVE)

	# Now deletion succeeds
	assert feat_svc.delete_feature(f_base.feature_id, project_id=project.project_id) is True


def test_rule_only_detection_and_backtest_auto_compile_missing_enriched_features():
	"""Rule-only BatchInferenceExecutor & RuleExecutor.backtest_dataframe auto-compile missing stateless enriched.* features and warn on requires_label=True."""
	features, _ = build_builtin_features_and_sets()
	by_key = {f.feature_key: f for f in features}
	rule_feature_defs = [
		by_key["tx_freq_last_1h"].to_dict(),
		by_key["ip_is_private"].to_dict(),
		by_key["merchant_hist_fraud_rate"].to_dict(),
	]

	raw_df = pd.DataFrame(
		{
			"event_id": ["E1", "E2", "E3"],
			"timestamp": pd.to_datetime([
				"2026-01-01 10:00:00",
				"2026-01-01 10:15:00",
				"2026-01-01 10:30:00",
			]),
			"amount": [50.0, 60.0, 70.0],
			"user_id": ["U1", "U1", "U2"],
			"ip_address": ["10.0.0.5", "192.168.1.10", "8.8.8.8"],
			"merchant": ["M1", "M1", "M2"],
			"label": [0, 1, 0],
		}
	)

	storage = InMemoryFileStorage()
	input_buf = io.BytesIO()
	raw_df.drop(columns=["label"]).to_parquet(input_buf, index=False)
	storage.save_bytes("batches/input.parquet", input_buf.getvalue())

	r1 = ActiveRuleSnapshot(
		rule_id=str(uuid4()),
		rule_version_id=str(uuid4()),
		version_number=1,
		rule_code="R_VEL_IP",
		rule_name="High velocity & private IP",
		action="REJECT",
		condition={
			"and": [
				{">=": [{"var": "enriched.tx_freq_last_1h"}, 2]},
				{"==": [{"var": "enriched.ip_is_private"}, True]},
			]
		},
	)
	r2 = ActiveRuleSnapshot(
		rule_id=str(uuid4()),
		rule_version_id=str(uuid4()),
		version_number=1,
		rule_code="R_TAR_RATE",
		rule_name="Historical merchant fraud rate",
		action="REVIEW",
		condition={">": [{"var": "enriched.merchant_hist_fraud_rate"}, 0.5]},
	)

	payload = BatchInferencePayload(
		job_id=uuid4(),
		project_id=uuid4(),
		input_path="batches/input.parquet",
		output_storage_path="batches/predictions.parquet",
		use_rules=True,
		active_rules=[r1, r2],
		rule_feature_definitions=rule_feature_defs,
	)

	executor = BatchInferenceExecutor(file_storage=storage)
	res = executor.run(payload)
	assert res.is_success is True
	assert res.fraud_records == 1
	warnings = (res.summary_metrics or {}).get("feature_warnings") or []
	assert any("merchant_hist_fraud_rate" in w for w in warnings)

	pred_df = pd.read_parquet(io.BytesIO(storage.read_bytes("batches/predictions.parquet")))
	assert list(pred_df["final_action"]) == ["ALLOW", "REJECT", "ALLOW"]

	# RuleExecutor.backtest_dataframe also auto-compiles missing stateless enriched.* and warns on requires_label=True
	rule_exec = RuleExecutor()
	bt1 = rule_exec.backtest_dataframe(
		df=raw_df,
		condition=r1.condition,
		action=RuleAction.REJECT,
		rule_code="R_VEL_IP",
		feature_definitions=rule_feature_defs,
	)
	assert bt1.total_hits == 1
	assert bt1.tp == 1

	bt2 = rule_exec.backtest_dataframe(
		df=raw_df,
		condition=r2.condition,
		action=RuleAction.REVIEW,
		rule_code="R_TAR_RATE",
		feature_definitions=rule_feature_defs,
	)
	assert bt2.total_hits == 0
	assert any("merchant_hist_fraud_rate" in w for w in bt2.feature_warnings)
