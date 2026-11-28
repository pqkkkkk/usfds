from datetime import datetime, timezone
import io
import json
from uuid import uuid4

import pandas as pd
import pytest

from usfds_core.domain.entities.case import (
	AuditLog,
	BlacklistEntityType,
	Case,
	CaseStatus,
	EntityBlacklist,
)
from usfds_core.domain.entities.detection import DetectionJob
from usfds_core.domain.entities.enums import DetectionJobStatus, RiskLevel, RuleAction, RuleStatus
from usfds_core.domain.entities.rule import Rule, RuleVersion
from usfds_core.domain.entities.system import Project
from usfds_core.repositories.in_memory_repos import (
	InMemoryDetectionJobRepository,
	InMemoryProjectRepository,
	InMemoryRuleRepository,
	InMemoryRuleVersionRepository,
)
from usfds_core.services.insight_report.service import InsightReportService
from usfds_core.storage.base_storage import IFileStorage


class _MemoryStorage(IFileStorage):
	def __init__(self):
		self.files: dict[str, bytes] = {}

	def save_bytes(self, path: str, data: bytes) -> str:
		self.files[path] = data
		return path

	def exists(self, path: str) -> bool:
		return path in self.files

	def read_bytes(self, path: str) -> bytes:
		return self.files[path]


class _MemoryCaseStore:
	def __init__(self):
		self.cases: list[Case] = []
		self.blacklist: list[EntityBlacklist] = []
		self.logs: list[AuditLog] = []

	def get_by_id(self, case_id):
		return next((c for c in self.cases if c.case_id == case_id), None)

	def list_by_project(self, project_id):
		return [c for c in self.cases if c.project_id == project_id]

	def list_for_entity(self, project_id, entity_type, entity_id):
		return [
			log for log in self.logs
			if log.project_id == project_id and log.entity_type == entity_type and log.entity_id == entity_id
		]


class _MemoryBlacklistRepo:
	def __init__(self, items: list[EntityBlacklist]):
		self.items = items

	def list_by_project(self, project_id):
		return [b for b in self.items if b.project_id == project_id]


def test_insight_report_end_to_end_metrics_and_sar_export():
	project_repo = InMemoryProjectRepository()
	job_repo = InMemoryDetectionJobRepository()
	rule_repo = InMemoryRuleRepository()
	rule_ver_repo = InMemoryRuleVersionRepository()
	storage = _MemoryStorage()
	case_store = _MemoryCaseStore()

	project_id = uuid4()
	other_project_id = uuid4()
	project_repo.save(Project(project_id=project_id, user_id=uuid4(), project_name="E-Commerce FDS"))
	project_repo.save(Project(project_id=other_project_id, user_id=uuid4(), project_name="Other Project"))

	# Register 2 rules: R_HIGH_VAL (high precision) and R_NOISY (high FPR)
	r1 = Rule(project_id=project_id, rule_code="R_HIGH_VAL", name="High Value Wire", description="High value")
	rv1 = RuleVersion(rule_id=r1.rule_id, version_number=1, condition={">=": [{"var": "amount"}, 2500]}, action=RuleAction.REJECT)
	r1.current_version_id = rv1.rule_version_id
	rule_repo.save(r1)
	rule_ver_repo.save(rv1)

	r2 = Rule(project_id=project_id, rule_code="R_NOISY", name="Noisy Promo Rule", description="Noisy")
	rv2 = RuleVersion(rule_id=r2.rule_id, version_number=1, condition={"==": [{"var": "promo"}, 1]}, action=RuleAction.REVIEW)
	r2.current_version_id = rv2.rule_version_id
	rule_repo.save(r2)
	rule_ver_repo.save(rv2)

	# Create a completed DetectionJob with 5 scanned transactions in parquet
	job_id = uuid4()
	model_ver_id = uuid4()
	parquet_path = f"datasets/{project_id}/inferences/{job_id}/predictions.parquet"
	df = pd.DataFrame([
		# TX-1: AI-Exclusive Fraud ($500, hour 02:00, score 0.92, no rule, verified fraud)
		{
			"event_id": "TX-1", "user_id": "U-FRAUD", "timestamp": "2026-11-01T02:15:00Z",
			"amount": 500.0, "model_score": 0.92, "rule_action": "ALLOW", "final_action": "REVIEW",
			"is_flagged": 1, "triggered_rules": "[]", "label": 1,
		},
		# TX-2: Consensus Fraud ($3000, hour 03:00, score 0.88 + R_HIGH_VAL, verified fraud)
		{
			"event_id": "TX-2", "user_id": "U-FRAUD", "timestamp": "2026-11-01T03:10:00Z",
			"amount": 3000.0, "model_score": 0.88, "rule_action": "REJECT", "final_action": "REJECT",
			"is_flagged": 1, "triggered_rules": json.dumps(["R_HIGH_VAL"]), "label": 1,
		},
		# TX-3: Rule-Exclusive False Positive ($120, hour 14:00, score 0.15 + R_NOISY, verified legit)
		{
			"event_id": "TX-3", "user_id": "U-GOOD", "timestamp": "2026-11-01T14:00:00Z",
			"amount": 120.0, "model_score": 0.15, "rule_action": "REVIEW", "final_action": "REVIEW",
			"is_flagged": 1, "triggered_rules": json.dumps(["R_NOISY"]), "label": 0,
		},
		# TX-4: Unverified in Case Queue, but dataset label=1 ($8.0 micro card-testing, rule R_HIGH_VAL)
		{
			"event_id": "TX-4", "user_id": "U-CARDTEST", "timestamp": "2026-11-01T02:45:00Z",
			"amount": 8.0, "model_score": 0.30, "rule_action": "REJECT", "final_action": "REJECT",
			"is_flagged": 1, "triggered_rules": json.dumps(["R_HIGH_VAL"]), "label": 1,
		},
		# TX-5: Legitimate ALLOW transaction ($50, hour 10:00)
		{
			"event_id": "TX-5", "user_id": "U-CLEAN", "timestamp": "2026-11-01T10:00:00Z",
			"amount": 50.0, "model_score": 0.04, "rule_action": "ALLOW", "final_action": "ALLOW",
			"is_flagged": 0, "triggered_rules": "[]", "label": 0,
		},
	])
	buf = io.BytesIO()
	df.to_parquet(buf, index=False)
	storage.files[parquet_path] = buf.getvalue()

	job_repo.save(DetectionJob(
		job_id=job_id,
		project_id=project_id,
		model_version_id=model_ver_id,
		job_name="Nov Batch Scan",
		output_path=parquet_path,
		score_threshold=0.5,
		status=DetectionJobStatus.COMPLETED,
		total_records=5,
		fraud_records=4,
	))

	# Create 3 Investigation Cases (for TX-1, TX-2, TX-3) + 1 Case in other project (BR-IR-01 test)
	c1 = Case(
		project_id=project_id, event_id="TX-1", user_id="U-FRAUD",
		tx_timestamp=datetime(2026, 11, 1, 2, 15, tzinfo=timezone.utc), amount=500.0,
		final_action=RuleAction.REVIEW, dataset_artifact_id=None, detection_job_id=job_id,
		model_version_id=model_ver_id, case_code="CASE-2026-0001", model_score=0.92,
		triggered_rules=[], feature_contributions=[{"feature_name": "velocity_1h", "feature_value": 9, "shap_value": 0.45}],
		attributes={"country": "US", "channel": "WEB"}, status=CaseStatus.RESOLVED_FRAUD,
		priority=RiskLevel.CRITICAL, priority_score=85.0, resolution_reason="VELOCITY_ATTACK",
		resolution_summary="Confirmed velocity burst from same device",
		resolved_at=datetime(2026, 11, 1, 4, 0, tzinfo=timezone.utc), resolved_by="local-analyst",
	)
	c2 = Case(
		project_id=project_id, event_id="TX-2", user_id="U-FRAUD",
		tx_timestamp=datetime(2026, 11, 1, 3, 10, tzinfo=timezone.utc), amount=3000.0,
		final_action=RuleAction.REJECT, dataset_artifact_id=None, detection_job_id=job_id,
		model_version_id=model_ver_id, case_code="CASE-2026-0002", model_score=0.88,
		triggered_rules=[{"rule_id": str(r1.rule_id), "rule_version_id": str(rv1.rule_version_id), "rule_code": "R_HIGH_VAL", "rule_name": "High Value Wire", "version_number": 1, "action": "REJECT", "matched_clauses": ["amount >= 2500"]}],
		status=CaseStatus.RESOLVED_FRAUD, priority=RiskLevel.CRITICAL, priority_score=92.0,
		resolution_reason="ACCOUNT_TAKEOVER", resolution_summary="Confirmed ATO wire transfer",
		resolved_at=datetime(2026, 11, 1, 5, 0, tzinfo=timezone.utc), resolved_by="local-analyst",
	)
	c3 = Case(
		project_id=project_id, event_id="TX-3", user_id="U-GOOD",
		tx_timestamp=datetime(2026, 11, 1, 14, 0, tzinfo=timezone.utc), amount=120.0,
		final_action=RuleAction.REVIEW, dataset_artifact_id=None, detection_job_id=job_id,
		model_version_id=model_ver_id, case_code="CASE-2026-0003", model_score=0.15,
		triggered_rules=[{"rule_id": str(r2.rule_id), "rule_version_id": str(rv2.rule_version_id), "rule_code": "R_NOISY", "rule_name": "Noisy Promo Rule", "version_number": 1, "action": "REVIEW", "matched_clauses": ["promo == 1"]}],
		status=CaseStatus.RESOLVED_LEGITIMATE, priority=RiskLevel.LOW, priority_score=22.0,
		resolution_reason="OVERLY_STRICT_RULE", resolution_summary="Customer used valid holiday promo",
		resolved_at=datetime(2026, 11, 1, 15, 0, tzinfo=timezone.utc), resolved_by="local-analyst",
	)
	c_other = Case(
		project_id=other_project_id, event_id="TX-999", user_id="U-OTHER",
		tx_timestamp=datetime.now(timezone.utc), amount=99999.0, final_action=RuleAction.REJECT,
		dataset_artifact_id=None, status=CaseStatus.RESOLVED_FRAUD,
	)
	case_store.cases.extend([c1, c2, c3, c_other])

	case_store.logs.append(AuditLog(
		project_id=project_id, entity_type="CASE", entity_id=str(c2.case_id),
		action="RESOLVE_FRAUD", actor="local-analyst", note="Confirmed ATO wire transfer",
	))
	bl_entry = EntityBlacklist(
		project_id=project_id, entity_type=BlacklistEntityType.USER_ID, entity_value="U-FRAUD",
		reason="Confirmed ATO wire transfer", created_by="local-analyst", source_case_id=c2.case_id,
	)

	service = InsightReportService(
		project_repo=project_repo,
		detection_job_repo=job_repo,
		case_repo=case_store,
		blacklist_repo=_MemoryBlacklistRepo([bl_entry]),
		audit_repo=case_store,
		rule_repo=rule_repo,
		rule_version_repo=rule_ver_repo,
		file_storage=storage,
	)

	# 1. SUC-22: Overview with VERIFIED_ONLY vs VERIFIED_WITH_DATASET_FALLBACK (BR-IR-02) & BR-IR-01 isolation
	ov_verified = service.get_executive_overview(project_id, label_source="VERIFIED_ONLY")
	assert ov_verified["kpis"]["gross_scanned_volume"] == 3678.0
	assert ov_verified["kpis"]["amount_at_risk"] == 3628.0
	assert ov_verified["kpis"]["confirmed_fraud_loss_prevented"] == 3500.0  # TX-1 ($500) + TX-2 ($3000)
	assert ov_verified["kpis"]["false_positive_friction_volume"] == 120.0   # TX-3 ($120)
	assert ov_verified["kpis"]["total_cases"] == 3

	ov_fallback = service.get_executive_overview(project_id, label_source="VERIFIED_WITH_DATASET_FALLBACK")
	assert ov_fallback["kpis"]["confirmed_fraud_loss_prevented"] == 3508.0  # Includes TX-4 ($8 dataset fallback)
	assert len(ov_fallback["funnel"]) == 4

	# 2. SUC-23: Effectiveness Analysis (AI-Exclusive vs Rule-Exclusive vs Overlap + Rule Leaderboard)
	eff = service.get_effectiveness_analysis(project_id, label_source="VERIFIED_WITH_DATASET_FALLBACK")
	attr = eff["attribution"]
	assert attr["total_caught_fraud_count"] == 3
	segments = {s["segment"]: s for s in attr["segments"]}
	assert segments["AI_EXCLUSIVE"]["fraud_count"] == 1        # TX-1
	assert segments["CONSENSUS_OVERLAP"]["fraud_count"] == 1   # TX-2
	assert segments["RULE_EXCLUSIVE"]["fraud_count"] == 1      # TX-4

	rules_by_code = {r["rule_code"]: r for r in eff["rule_leaderboard"]}
	assert rules_by_code["R_HIGH_VAL"]["policy_health_tag"] == "HIGH_VALUE"
	assert rules_by_code["R_NOISY"]["policy_health_tag"] == "NOISY"
	assert rules_by_code["R_NOISY"]["verified_fpr"] == 1.0
	assert len(eff["threshold_simulator"]["curve"]) == 19

	# 3. SUC-24: Typology & Temporal-Behavioral Patterns
	pat = service.get_typology_and_patterns(project_id)
	assert pat["watchlist_summary"]["active_blacklist_count"] == 1
	assert pat["top_flagged_subjects"][0]["user_id"] == "U-FRAUD"
	assert pat["top_flagged_subjects"][0]["is_blacklisted"] is True
	brackets = {b["bracket_id"]: b for b in pat["amount_brackets"]}
	assert brackets["MICRO"]["flagged_count"] == 1       # TX-4 ($8)
	assert brackets["HIGH_VALUE"]["flagged_count"] == 1  # TX-2 ($3000)

	# 4. SUC-25: SAR Dossier & Export (BR-IR-03)
	sar = service.generate_sar_dossier(project_id, c2.case_id, prepared_by="auditor-1", reviewer_notes="Escalate to FinCEN")
	assert sar["section_1_identification"]["case_code"] == "CASE-2026-0002"
	assert sar["section_5_mitigation_and_audit"]["is_subject_blacklisted"] is True
	assert len(sar["section_5_mitigation_and_audit"]["audit_trail"]) == 1

	md_bytes, md_name, _ = service.export_report(project_id, "sar", "md", case_id=c2.case_id)
	assert md_name.endswith(".md") and b"CASE-2026-0002" in md_bytes
	csv_bytes, csv_name, _ = service.export_report(project_id, "executive", "csv")
	assert csv_name.endswith(".csv") and b"R_HIGH_VAL" in csv_bytes

	with pytest.raises(LookupError):
		service.generate_sar_dossier(project_id, c_other.case_id)


def test_insight_report_filters_by_tx_timestamp_on_warehouse_without_pandas(monkeypatch):
	def _blocked(*args, **kwargs):
		raise AssertionError("pd.read_parquet must not be used (ISS-012)")

	monkeypatch.setattr(pd, "read_parquet", _blocked)

	project_repo = InMemoryProjectRepository()
	job_repo = InMemoryDetectionJobRepository()
	storage = _MemoryStorage()
	case_store = _MemoryCaseStore()
	project_id = uuid4()
	project_repo.save(Project(project_id=project_id, user_id=uuid4(), project_name="TS Filter"))

	job_id = uuid4()
	path = f"datasets/{project_id}/inferences/{job_id}/predictions.parquet"
	rows = [
		{"event_id": "OCT-1", "user_id": "U1", "timestamp": "2026-10-05T10:00:00Z", "amount": 100.0, "model_score": 0.9,
		 "rule_action": "ALLOW", "final_action": "REVIEW", "triggered_rules": "[]", "label": 1},
		{"event_id": "NOV-1", "user_id": "U2", "timestamp": "2026-11-10T10:00:00Z", "amount": 200.0, "model_score": 0.8,
		 "rule_action": "REJECT", "final_action": "REJECT", "triggered_rules": json.dumps(["R_X"]), "label": 1},
		{"event_id": "NOV-2", "user_id": "U3", "timestamp": "2026-11-20T10:00:00Z", "amount": 50.0, "model_score": 0.1,
		 "rule_action": "ALLOW", "final_action": "ALLOW", "triggered_rules": "[]", "label": 0},
		{"event_id": "DEC-1", "user_id": "U4", "timestamp": "2026-12-02T10:00:00Z", "amount": 400.0, "model_score": 0.95,
		 "rule_action": "ALLOW", "final_action": "REVIEW", "triggered_rules": "[]", "label": 1},
	]
	buf = io.BytesIO()
	pd.DataFrame(rows).to_parquet(buf, index=False)
	storage.files[path] = buf.getvalue()
	# The job itself ran in January: filtering by job date would hide everything below.
	job_repo.save(DetectionJob(
		job_id=job_id, project_id=project_id, job_name="Jan Scan", output_path=path, score_threshold=0.5,
		status=DetectionJobStatus.COMPLETED, created_at=datetime(2027, 1, 5, tzinfo=timezone.utc),
	))
	service = InsightReportService(
		project_repo=project_repo, detection_job_repo=job_repo, case_repo=case_store,
		blacklist_repo=_MemoryBlacklistRepo([]), audit_repo=case_store, file_storage=storage,
	)
	window = {"date_from": datetime(2026, 11, 1, tzinfo=timezone.utc), "date_to": datetime(2026, 11, 30, 23, 59, tzinfo=timezone.utc)}

	ov = service.get_executive_overview(project_id, **window)
	assert ov["kpis"]["gross_scanned_volume"] == 250.0  # NOV-1 + NOV-2 only
	assert ov["kpis"]["amount_at_risk"] == 200.0

	eff = service.get_effectiveness_analysis(project_id, **window)
	assert {r["rule_code"]: r["total_hits"] for r in eff["rule_leaderboard"]} == {"R_X": 1}

	pat = service.get_typology_and_patterns(project_id, **window)
	assert sum(b["flagged_count"] for b in pat["amount_brackets"]) == 1

	assert service.get_executive_overview(project_id)["kpis"]["gross_scanned_volume"] == 750.0
	assert any(k.startswith(f"warehouse/{project_id}/fact_transactions/") for k in storage.files)


def test_sar_dossier_omits_assigned_to_and_uses_resolved_by():
	"""ISS-045: SAR dossier identification omits assigned_to and reports resolved_by."""
	from usfds_core.services.insight_report.report_builder import ComplianceReportBuilder

	project_id = uuid4()
	case = Case(
		project_id=project_id,
		event_id="EV-SAR-1",
		user_id="U-SAR-1",
		tx_timestamp=datetime(2026, 11, 20, 14, 0, tzinfo=timezone.utc),
		amount=500.0,
		final_action=RuleAction.REJECT,
		dataset_artifact_id=None,
		case_code="CASE-2026-SAR1",
		model_score=0.92,
		status=CaseStatus.RESOLVED_FRAUD,
		priority=RiskLevel.CRITICAL,
		priority_score=90.0,
		resolution_reason="OTHER_FRAUD",
		resolution_summary="Confirmed fraudulent activity by investigation",
		resolved_at=datetime(2026, 11, 20, 15, 0, tzinfo=timezone.utc),
		resolved_by="analyst1",
	)
	dossier = ComplianceReportBuilder.build_sar_dossier(
		project_id=str(project_id),
		project_name="SAR Test",
		case=case,
		related_cases=[],
		audit_logs=[],
		blacklist_entries=[],
	)
	s1 = dossier["section_1_identification"]
	assert "assigned_to" not in s1
	assert s1["resolved_by"] == "analyst1"

	md = ComplianceReportBuilder.format_sar_markdown(dossier)
	assert "Assigned / Resolved" not in md
	assert "Resolved Analyst:" in md and "analyst1" in md


def _make_parquet_bytes(rows: list[dict]) -> bytes:
	buf = io.BytesIO()
	pd.DataFrame(rows).to_parquet(buf, index=False)
	return buf.getvalue()


def test_overview_missed_fraud_vdr_bps_and_insult_rate_separation():
	"""SUC-22, ISS-046: Missed Fraud/VDR/bps, Customer Insult Rate FP/(TN+FP), and REJECT vs REVIEW friction separation."""
	project_repo = InMemoryProjectRepository()
	job_repo = InMemoryDetectionJobRepository()
	storage = _MemoryStorage()
	case_store = _MemoryCaseStore()
	project_id = uuid4()
	job_id = uuid4()
	project_repo.save(Project(project_id=project_id, user_id=uuid4(), project_name="VDR & Insult"))

	rows = []
	# 10 TP REJECT ($500 each = $5,000)
	for i in range(10):
		rows.append({
			"event_id": f"TP-REJ-{i}", "user_id": f"U-TP-{i}", "timestamp": "2026-11-01T10:00:00Z",
			"amount": 500.0, "model_score": 0.95, "rule_action": "REJECT", "final_action": "REJECT",
			"is_flagged": 1, "triggered_rules": json.dumps(["R1"]), "label": 1,
		})
	# 10 TP REVIEW ($300 each = $3,000) -> total TP$ = $8,000
	for i in range(10):
		rows.append({
			"event_id": f"TP-REV-{i}", "user_id": f"U-TP-{i}", "timestamp": "2026-11-01T11:00:00Z",
			"amount": 300.0, "model_score": 0.70, "rule_action": "ALLOW", "final_action": "REVIEW",
			"is_flagged": 1, "triggered_rules": "[]", "label": 1,
		})
	# 5 FN ALLOW ($400 each = $2,000 missed fraud) -> VDR = 8000 / 10000 = 0.80
	for i in range(5):
		rows.append({
			"event_id": f"FN-{i}", "user_id": f"U-FN-{i}", "timestamp": "2026-11-01T12:00:00Z",
			"amount": 400.0, "model_score": 0.20, "rule_action": "ALLOW", "final_action": "ALLOW",
			"is_flagged": 0, "triggered_rules": "[]", "label": 1,
		})
	# 5 FP REJECT ($200 each = $1,000 hard false decline)
	for i in range(5):
		rows.append({
			"event_id": f"FP-REJ-{i}", "user_id": f"U-FP-R-{i}", "timestamp": "2026-11-01T13:00:00Z",
			"amount": 200.0, "model_score": 0.85, "rule_action": "REJECT", "final_action": "REJECT",
			"is_flagged": 1, "triggered_rules": json.dumps(["R1"]), "label": 0,
		})
	# 10 FP REVIEW ($100 each = $1,000 soft review friction) -> total FP = 15 ($2,000)
	for i in range(10):
		rows.append({
			"event_id": f"FP-REV-{i}", "user_id": f"U-FP-V-{i}", "timestamp": "2026-11-01T14:00:00Z",
			"amount": 100.0, "model_score": 0.60, "rule_action": "ALLOW", "final_action": "REVIEW",
			"is_flagged": 1, "triggered_rules": "[]", "label": 0,
		})
	# 60 TN ALLOW ($100 each = $6,000) -> TN+FP = 75, Gross$ = 5000+3000+2000+1000+1000+6000 = $18,000
	for i in range(60):
		rows.append({
			"event_id": f"TN-{i}", "user_id": f"U-TN-{i}", "timestamp": "2026-11-01T15:00:00Z",
			"amount": 100.0, "model_score": 0.05, "rule_action": "ALLOW", "final_action": "ALLOW",
			"is_flagged": 0, "triggered_rules": "[]", "label": 0,
		})
	assert len(rows) == 100

	path = f"datasets/{project_id}/inferences/{job_id}/predictions.parquet"
	storage.files[path] = _make_parquet_bytes(rows)
	job_repo.save(DetectionJob(
		job_id=job_id, project_id=project_id, job_name="Overview 100",
		output_path=path, score_threshold=0.5, status=DetectionJobStatus.COMPLETED,
	))
	service = InsightReportService(
		project_repo=project_repo, detection_job_repo=job_repo, case_repo=case_store,
		blacklist_repo=_MemoryBlacklistRepo([]), audit_repo=case_store, file_storage=storage,
	)

	ov = service.get_executive_overview(project_id, label_source="VERIFIED_WITH_DATASET_FALLBACK")
	kpis = ov["kpis"]
	assert kpis["gross_scanned_count"] == 100
	assert kpis["gross_scanned_volume"] == 18000.0
	assert kpis["confirmed_fraud_loss_prevented"] == 8000.0
	assert kpis["missed_fraud_amount"] == 2000.0
	assert kpis["missed_fraud_count"] == 5
	assert kpis["value_detection_rate"] == pytest.approx(0.8, abs=1e-4)
	assert kpis["net_fraud_loss_bps"] == pytest.approx((2000.0 / 18000.0) * 10000.0, abs=0.05)
	# Customer Insult Rate = FP / (TN + FP) = 15 / 75 = 0.20 (NOT 15 / 35)
	assert kpis["customer_insult_rate"] == pytest.approx(15.0 / 75.0, abs=1e-4)
	assert kpis["insult_rate"] == pytest.approx(15.0 / 75.0, abs=1e-4)
	assert kpis["hard_false_decline_amount"] == 1000.0
	assert kpis["hard_false_decline_count"] == 5
	assert kpis["soft_review_friction_amount"] == 1000.0
	assert kpis["soft_review_friction_count"] == 10


def test_overview_verified_only_returns_null_for_fn_tn_metrics_and_monotonic_funnel():
	"""SUC-22, BR-IR-02, BR-IR-04: VERIFIED_ONLY returns None for FN/TN metrics and 4-stage funnel is strictly monotonic."""
	project_repo = InMemoryProjectRepository()
	job_repo = InMemoryDetectionJobRepository()
	storage = _MemoryStorage()
	case_store = _MemoryCaseStore()
	project_id = uuid4()
	job_id = uuid4()
	project_repo.save(Project(project_id=project_id, user_id=uuid4(), project_name="Verified Only"))

	rows = []
	for i in range(100):
		is_flagged = 1 if i < 10 else 0
		rows.append({
			"event_id": f"EV-{i}", "user_id": f"U-{i}", "timestamp": "2026-11-01T10:00:00Z",
			"amount": 100.0, "model_score": 0.8 if is_flagged else 0.1,
			"rule_action": "ALLOW", "final_action": "REVIEW" if is_flagged else "ALLOW",
			"is_flagged": is_flagged, "triggered_rules": "[]", "label": 1 if i < 15 else 0,
		})

	path = f"datasets/{project_id}/inferences/{job_id}/predictions.parquet"
	storage.files[path] = _make_parquet_bytes(rows)
	job_repo.save(DetectionJob(
		job_id=job_id, project_id=project_id, job_name="Monotonic Job",
		output_path=path, score_threshold=0.5, status=DetectionJobStatus.COMPLETED,
	))

	# 4 cases created (EV-0..3), 2 closed (EV-0 fraud, EV-1 legit)
	for i in range(4):
		status = CaseStatus.OPEN
		verified_at = None
		if i == 0:
			status = CaseStatus.RESOLVED_FRAUD
			verified_at = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
		elif i == 1:
			status = CaseStatus.RESOLVED_LEGITIMATE
			verified_at = datetime(2026, 11, 1, 13, 0, tzinfo=timezone.utc)
		case_store.cases.append(Case(
			project_id=project_id, event_id=f"EV-{i}", user_id=f"U-{i}",
			tx_timestamp=datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc), amount=100.0,
			final_action=RuleAction.REVIEW, dataset_artifact_id=None, detection_job_id=job_id,
			status=status, resolved_at=verified_at,
		))

	service = InsightReportService(
		project_repo=project_repo, detection_job_repo=job_repo, case_repo=case_store,
		blacklist_repo=_MemoryBlacklistRepo([]), audit_repo=case_store, file_storage=storage,
	)
	ov = service.get_executive_overview(project_id, label_source="VERIFIED_ONLY")
	kpis = ov["kpis"]
	assert kpis["ground_truth_coverage"] == "FLAGGED_ONLY"
	assert kpis["missed_fraud_amount"] is None
	assert kpis["value_detection_rate"] is None
	assert kpis["net_fraud_loss_bps"] is None
	assert kpis["customer_insult_rate"] is None

	funnel_counts = [stage["tx_count"] for stage in ov["funnel"]]
	assert funnel_counts == [100, 10, 4, 2]
	assert funnel_counts[0] >= funnel_counts[1] >= funnel_counts[2] >= funnel_counts[3]


def test_overview_case_sla_mttr_aging_and_daily_trends():
	"""SUC-22, BR-IR-05, ISS-046: Case SLA/MTTR/Aging/Analyst stats and daily financial trends by tx_timestamp."""
	project_repo = InMemoryProjectRepository()
	job_repo = InMemoryDetectionJobRepository()
	storage = _MemoryStorage()
	case_store = _MemoryCaseStore()
	project_id = uuid4()
	job_id = uuid4()
	project_repo.save(Project(project_id=project_id, user_id=uuid4(), project_name="SLA & Trends"))

	rows = [
		{"event_id": "D1-1", "user_id": "U1", "timestamp": "2026-11-01T08:00:00Z", "amount": 200.0,
		 "model_score": 0.9, "rule_action": "ALLOW", "final_action": "REJECT", "triggered_rules": "[]", "label": 1},
		{"event_id": "D2-1", "user_id": "U2", "timestamp": "2026-11-02T09:00:00Z", "amount": 150.0,
		 "model_score": 0.8, "rule_action": "ALLOW", "final_action": "REVIEW", "triggered_rules": "[]", "label": 0},
		{"event_id": "D3-1", "user_id": "U3", "timestamp": "2026-11-03T10:00:00Z", "amount": 500.0,
		 "model_score": 0.1, "rule_action": "ALLOW", "final_action": "ALLOW", "triggered_rules": "[]", "label": 1},
		{"event_id": "D3-2", "user_id": "U4", "timestamp": "2026-11-03T12:00:00Z", "amount": 300.0,
		 "model_score": 0.85, "rule_action": "ALLOW", "final_action": "REVIEW", "triggered_rules": "[]", "label": 1},
	]
	path = f"datasets/{project_id}/inferences/{job_id}/predictions.parquet"
	storage.files[path] = _make_parquet_bytes(rows)
	job_repo.save(DetectionJob(
		job_id=job_id, project_id=project_id, job_name="Multi-day Scan",
		output_path=path, score_threshold=0.5, status=DetectionJobStatus.COMPLETED,
	))

	base_t = datetime(2026, 11, 1, 8, 0, tzinfo=timezone.utc)
	from datetime import timedelta
	case_store.cases.extend([
		# 2h resolution on CRITICAL (<= 4h -> within SLA)
		Case(
			project_id=project_id, event_id="D1-1", user_id="U1", tx_timestamp=base_t, amount=200.0,
			final_action=RuleAction.REJECT, dataset_artifact_id=None, detection_job_id=job_id,
			status=CaseStatus.RESOLVED_FRAUD, priority=RiskLevel.CRITICAL,
			created_at=base_t, resolved_at=base_t + timedelta(hours=2), resolved_by="analyst_a",
		),
		# 6h resolution on CRITICAL (> 4h -> SLA breach)
		Case(
			project_id=project_id, event_id="D2-1", user_id="U2", tx_timestamp=base_t + timedelta(days=1), amount=150.0,
			final_action=RuleAction.REVIEW, dataset_artifact_id=None, detection_job_id=job_id,
			status=CaseStatus.RESOLVED_LEGITIMATE, priority=RiskLevel.CRITICAL,
			created_at=base_t, resolved_at=base_t + timedelta(hours=6), resolved_by="analyst_a",
		),
		# 30h resolution on HIGH (> 24h -> SLA breach)
		Case(
			project_id=project_id, event_id="D3-2", user_id="U4", tx_timestamp=base_t + timedelta(days=2), amount=300.0,
			final_action=RuleAction.REVIEW, dataset_artifact_id=None, detection_job_id=job_id,
			status=CaseStatus.RESOLVED_FRAUD, priority=RiskLevel.HIGH,
			created_at=base_t, resolved_at=base_t + timedelta(hours=30), resolved_by="analyst_b",
		),
		# 80h resolution on MEDIUM (> 72h -> SLA breach)
		Case(
			project_id=project_id, event_id="D4-1", user_id="U5", tx_timestamp=base_t + timedelta(days=2), amount=100.0,
			final_action=RuleAction.REVIEW, dataset_artifact_id=None, detection_job_id=job_id,
			status=CaseStatus.RESOLVED_FRAUD, priority=RiskLevel.MEDIUM,
			created_at=base_t, resolved_at=base_t + timedelta(hours=80), resolved_by="analyst_b",
		),
	])

	service = InsightReportService(
		project_repo=project_repo, detection_job_repo=job_repo, case_repo=case_store,
		blacklist_repo=_MemoryBlacklistRepo([]), audit_repo=case_store, file_storage=storage,
	)
	ov = service.get_executive_overview(project_id)

	sla = ov["case_sla"]
	# Sorted durations: [2, 6, 30, 80] -> P50 = 18.0
	assert sla["mttr_p50_hours"] == pytest.approx(18.0, abs=0.1)
	assert sla["mttr_p90_hours"] >= 60.0
	assert sla["sla_breach_count"] == 3
	assert sla["sla_breach_rate"] == pytest.approx(0.75, abs=1e-4)
	assert len(sla["aging_buckets"]) == 4
	analysts = {a["analyst"]: a for a in sla["analyst_stats"]}
	assert set(analysts.keys()) == {"analyst_a", "analyst_b"}
	assert analysts["analyst_a"]["resolved_count"] == 2
	assert analysts["analyst_b"]["sla_breach_count"] == 2

	trends = ov["financial_trends"]
	assert len(trends) == 3
	assert all(pt["granularity"] == "DAY" for pt in trends)
	assert [pt["date"] for pt in trends] == ["2026-11-01", "2026-11-02", "2026-11-03"]


def test_effectiveness_rule_unique_catch_far_small_sample_and_fp_fn_samples():
	"""SUC-23, BR-IR-04, ISS-046: Rule Unique Catch, FAR, Small Sample flag (n<30), and FP/FN samples."""
	project_repo = InMemoryProjectRepository()
	job_repo = InMemoryDetectionJobRepository()
	rule_repo = InMemoryRuleRepository()
	rule_ver_repo = InMemoryRuleVersionRepository()
	storage = _MemoryStorage()
	case_store = _MemoryCaseStore()
	project_id = uuid4()
	job_id = uuid4()
	project_repo.save(Project(project_id=project_id, user_id=uuid4(), project_name="Rule Unique Catch"))

	r_unique = Rule(project_id=project_id, rule_code="R_UNIQUE", name="Unique Rule", description="Unique")
	rv_u = RuleVersion(rule_id=r_unique.rule_id, version_number=1, condition={">": [{"var": "amount"}, 100]}, action=RuleAction.REJECT)
	r_unique.current_version_id = rv_u.rule_version_id
	rule_repo.save(r_unique)
	rule_ver_repo.save(rv_u)

	r_red = Rule(project_id=project_id, rule_code="R_REDUNDANT", name="Redundant Rule", description="Redundant")
	rv_r = RuleVersion(rule_id=r_red.rule_id, version_number=1, condition={">": [{"var": "amount"}, 10]}, action=RuleAction.REVIEW)
	r_red.current_version_id = rv_r.rule_version_id
	rule_repo.save(r_red)
	rule_ver_repo.save(rv_r)

	rows = [
		# Unique catch by R_UNIQUE only (score 0.2 < 0.5, label=1)
		{"event_id": "EV-U1", "user_id": "U1", "timestamp": "2026-11-01T10:00:00Z", "amount": 900.0,
		 "model_score": 0.20, "rule_action": "REJECT", "final_action": "REJECT",
		 "triggered_rules": json.dumps(["R_UNIQUE"]), "label": 1},
		# Overlaps with AI (score 0.9 >= 0.5, label=1) -> NOT unique catch for R_REDUNDANT
		{"event_id": "EV-R-TP", "user_id": "U2", "timestamp": "2026-11-01T11:00:00Z", "amount": 500.0,
		 "model_score": 0.90, "rule_action": "REVIEW", "final_action": "REVIEW",
		 "triggered_rules": json.dumps(["R_REDUNDANT"]), "label": 1},
		# 3 FPs from R_REDUNDANT
		{"event_id": "EV-R-FP1", "user_id": "U3", "timestamp": "2026-11-01T12:00:00Z", "amount": 50.0,
		 "model_score": 0.10, "rule_action": "REVIEW", "final_action": "REVIEW",
		 "triggered_rules": json.dumps(["R_REDUNDANT"]), "label": 0},
		{"event_id": "EV-R-FP2", "user_id": "U4", "timestamp": "2026-11-01T13:00:00Z", "amount": 60.0,
		 "model_score": 0.15, "rule_action": "REVIEW", "final_action": "REVIEW",
		 "triggered_rules": json.dumps(["R_REDUNDANT"]), "label": 0},
		{"event_id": "EV-R-FP3", "user_id": "U5", "timestamp": "2026-11-01T14:00:00Z", "amount": 70.0,
		 "model_score": 0.20, "rule_action": "REVIEW", "final_action": "REVIEW",
		 "triggered_rules": json.dumps(["R_REDUNDANT"]), "label": 0},
		# 1 System FN (missed fraud)
		{"event_id": "EV-FN-1", "user_id": "U6", "timestamp": "2026-11-01T15:00:00Z", "amount": 1200.0,
		 "model_score": 0.12, "rule_action": "ALLOW", "final_action": "ALLOW",
		 "triggered_rules": "[]", "label": 1},
	]
	path = f"datasets/{project_id}/inferences/{job_id}/predictions.parquet"
	storage.files[path] = _make_parquet_bytes(rows)
	job_repo.save(DetectionJob(
		job_id=job_id, project_id=project_id, job_name="Rule Eval",
		output_path=path, score_threshold=0.5, status=DetectionJobStatus.COMPLETED,
	))

	service = InsightReportService(
		project_repo=project_repo, detection_job_repo=job_repo, case_repo=case_store,
		blacklist_repo=_MemoryBlacklistRepo([]), audit_repo=case_store,
		rule_repo=rule_repo, rule_version_repo=rule_ver_repo, file_storage=storage,
	)
	eff = service.get_effectiveness_analysis(project_id)
	by_code = {r["rule_code"]: r for r in eff["rule_leaderboard"]}

	assert by_code["R_UNIQUE"]["unique_catch_count"] == 1
	assert by_code["R_UNIQUE"]["unique_catch_amount"] == 900.0
	assert by_code["R_UNIQUE"]["is_small_sample"] is True

	assert by_code["R_REDUNDANT"]["unique_catch_count"] == 0
	assert by_code["R_REDUNDANT"]["unique_catch_amount"] == 0.0
	assert by_code["R_REDUNDANT"]["false_alert_rate"] == pytest.approx(3.0 / 4.0, abs=1e-4)
	assert by_code["R_REDUNDANT"]["is_small_sample"] is True
	assert len(by_code["R_REDUNDANT"]["fp_samples"]) == 3
	assert [s["event_id"] for s in eff["fn_samples"]] == ["EV-FN-1"]


def test_effectiveness_calibration_lift_ks_psi_and_dual_threshold_simulator():
	"""SUC-23, ISS-046: Calibration (equal_width/equal_count), Brier/ECE/KS, Lift/Gain, PSI drift, Dual-Threshold Simulator."""
	project_repo = InMemoryProjectRepository()
	job_repo = InMemoryDetectionJobRepository()
	storage = _MemoryStorage()
	case_store = _MemoryCaseStore()
	project_id = uuid4()
	job_id = uuid4()
	project_repo.save(Project(project_id=project_id, user_id=uuid4(), project_name="Model Health & Drift"))

	rows = []
	# Period 1 (30 txs): low scores for legit, high for some fraud
	for i in range(30):
		is_fraud = 1 if i >= 24 else 0
		score = 0.85 if is_fraud else round(0.05 + (i % 5) * 0.03, 2)
		action = "REJECT" if score >= 0.8 else "ALLOW"
		rows.append({
			"event_id": f"P1-{i}", "user_id": f"U1-{i}",
			"timestamp": f"2026-11-01T{i % 24:02d}:00:00Z",
			"amount": 250.0 if is_fraud else 50.0,
			"model_score": score, "rule_action": "ALLOW", "final_action": action,
			"triggered_rules": "[]", "label": is_fraud,
		})
	# Period 2 (30 txs): clear distribution shift toward higher scores
	for i in range(30):
		is_fraud = 1 if i >= 18 else 0
		score = 0.92 if is_fraud else round(0.55 + (i % 5) * 0.07, 2)
		action = "REJECT" if score >= 0.8 else ("REVIEW" if score >= 0.5 else "ALLOW")
		rows.append({
			"event_id": f"P2-{i}", "user_id": f"U2-{i}",
			"timestamp": f"2026-11-10T{i % 24:02d}:00:00Z",
			"amount": 300.0 if is_fraud else 60.0,
			"model_score": score, "rule_action": "REVIEW" if i == 0 else "ALLOW",
			"final_action": "REVIEW" if (i == 0 and action == "ALLOW") else action,
			"triggered_rules": json.dumps(["R_SPIKE"]) if i == 0 else "[]",
			"label": is_fraud,
		})

	path = f"datasets/{project_id}/inferences/{job_id}/predictions.parquet"
	storage.files[path] = _make_parquet_bytes(rows)
	job_repo.save(DetectionJob(
		job_id=job_id, project_id=project_id, job_name="Drift 60",
		output_path=path, score_threshold=0.5, status=DetectionJobStatus.COMPLETED,
	))

	service = InsightReportService(
		project_repo=project_repo, detection_job_repo=job_repo, case_repo=case_store,
		blacklist_repo=_MemoryBlacklistRepo([]), audit_repo=case_store, file_storage=storage,
	)
	eff = service.get_effectiveness_analysis(project_id)

	# Calibration modes & reliability fields (TN is NOT counted as FP in lowest bin)
	ew = eff["score_calibration_modes"]["equal_width"]
	ec = eff["score_calibration_modes"]["equal_count"]
	assert len(ew) == 10 and len(ec) >= 5
	low_bin = ew[0]
	assert "mean_predicted_score" in low_bin and "observed_fraud_rate" in low_bin
	assert low_bin["legit_count"] > 0
	assert low_bin["false_positive_count"] == 0

	mh = eff["model_health"]
	assert mh["brier_score"] is not None and 0.0 <= mh["brier_score"] <= 1.0
	assert mh["ece"] is not None and 0.0 <= mh["ece"] <= 1.0
	assert mh["ks_statistic"] is not None and mh["ks_statistic"] > 0.3

	# Lift & Gain curve
	lift = eff["lift_gain_curve"]
	assert [pt["top_pct"] for pt in lift] == [1, 2, 5, 10, 20, 30, 50, 100]
	assert lift[-1]["gain_count_pct"] == pytest.approx(1.0, abs=1e-4)

	# PSI Drift
	drift = eff["score_drift"]
	assert drift["psi"] is not None and drift["psi"] > 0.25
	assert drift["status"] == "SIGNIFICANT_SHIFT"

	# Dual-threshold simulator for both hybrid and model_only
	sim = eff["threshold_simulator"]
	assert len(sim["curve"]) == 19
	assert "hybrid" in sim["curve"][0] and "model_only" in sim["curve"][0]
	assert "hybrid" in sim["recommendations"] and "model_only" in sim["recommendations"]
	# At identical thresholds, hybrid review/flagged count >= model_only when rules hit
	pt_80 = next(p for p in sim["curve"] if abs(p["threshold"] - 0.8) < 0.01)
	assert pt_80["hybrid"]["flagged_count"] >= pt_80["model_only"]["flagged_count"]


def test_patterns_consistent_24h_segments_true_user_totals_and_watchlist_impact():
	"""SUC-24, BR-IR-04, ISS-046: Consistent 24h rates, multi-dim segment hit-rate, true user total_tx_count, watchlist impact."""
	project_repo = InMemoryProjectRepository()
	job_repo = InMemoryDetectionJobRepository()
	storage = _MemoryStorage()
	case_store = _MemoryCaseStore()
	project_id = uuid4()
	job_id = uuid4()
	project_repo.save(Project(project_id=project_id, user_id=uuid4(), project_name="Segments & Watchlist"))

	rows = [
		# U1 has 5 transactions: 2 flagged (1 fraud, 1 FP), 3 unflagged legit
		{"event_id": "U1-1", "user_id": "U1", "timestamp": "2026-11-01T02:00:00Z", "amount": 500.0,
		 "model_score": 0.9, "rule_action": "ALLOW", "final_action": "REJECT", "triggered_rules": "[]",
		 "label": 1, "merchant_category": "GAMBLING", "device_id": "DEV-BAD", "ip_address": "1.2.3.4"},
		{"event_id": "U1-2", "user_id": "U1", "timestamp": "2026-11-01T02:30:00Z", "amount": 100.0,
		 "model_score": 0.6, "rule_action": "ALLOW", "final_action": "REVIEW", "triggered_rules": "[]",
		 "label": 0, "merchant_category": "RETAIL", "device_id": "DEV-BAD", "ip_address": "1.2.3.4"},
		{"event_id": "U1-3", "user_id": "U1", "timestamp": "2026-11-01T10:00:00Z", "amount": 40.0,
		 "model_score": 0.1, "rule_action": "ALLOW", "final_action": "ALLOW", "triggered_rules": "[]",
		 "label": 0, "merchant_category": "RETAIL", "device_id": "DEV-OK", "ip_address": "5.6.7.8"},
		{"event_id": "U1-4", "user_id": "U1", "timestamp": "2026-11-01T10:15:00Z", "amount": 30.0,
		 "model_score": 0.1, "rule_action": "ALLOW", "final_action": "ALLOW", "triggered_rules": "[]",
		 "label": 0, "merchant_category": "RETAIL", "device_id": "DEV-OK", "ip_address": "5.6.7.8"},
		{"event_id": "U1-5", "user_id": "U1", "timestamp": "2026-11-01T10:30:00Z", "amount": 20.0,
		 "model_score": 0.1, "rule_action": "ALLOW", "final_action": "ALLOW", "triggered_rules": "[]",
		 "label": 0, "merchant_category": "RETAIL", "device_id": "DEV-OK", "ip_address": "5.6.7.8"},
		# Hour 14: 1 flagged FP, 0 confirmed fraud -> confirmed_fraud_rate MUST be 0.0, flagged_rate = 1.0
		{"event_id": "U2-1", "user_id": "U2", "timestamp": "2026-11-01T14:00:00Z", "amount": 80.0,
		 "model_score": 0.65, "rule_action": "ALLOW", "final_action": "REVIEW", "triggered_rules": "[]",
		 "label": 0, "merchant_category": "RETAIL", "device_id": "DEV-OK", "ip_address": "9.9.9.9"},
	]
	path = f"datasets/{project_id}/inferences/{job_id}/predictions.parquet"
	storage.files[path] = _make_parquet_bytes(rows)
	job_repo.save(DetectionJob(
		job_id=job_id, project_id=project_id, job_name="Patterns Scan",
		output_path=path, score_threshold=0.5, status=DetectionJobStatus.COMPLETED,
	))

	bl = EntityBlacklist(
		project_id=project_id, entity_type=BlacklistEntityType.USER_ID,
		entity_value="U1", reason="Repeat fraud", created_by="analyst",
	)
	service = InsightReportService(
		project_repo=project_repo, detection_job_repo=job_repo, case_repo=case_store,
		blacklist_repo=_MemoryBlacklistRepo([bl]), audit_repo=case_store, file_storage=storage,
	)
	pat = service.get_typology_and_patterns(project_id)

	hour_14 = pat["hourly_distribution"][14]
	assert hour_14["confirmed_fraud_rate"] == 0.0
	assert hour_14["flagged_rate"] == 1.0

	seg = pat["segment_analytics"]
	assert seg["amount_brackets"]["available"] is True
	assert seg["merchant_category"]["available"] is True
	assert seg["device_id"]["available"] is True
	assert seg["ip_address"]["available"] is True
	gambling = next(i for i in seg["merchant_category"]["items"] if i["segment_value"] == "GAMBLING")
	assert gambling["hit_rate"] == 1.0
	assert gambling["detection_rate"] == 1.0
	assert gambling["missed_fraud_amount"] == 0.0
	assert gambling["lift"] > 1.0
	assert gambling["is_small_sample"] is True

	u1_sub = next(s for s in pat["top_flagged_subjects"] if s["user_id"] == "U1")
	assert u1_sub["total_tx_count"] == 5
	assert u1_sub["flagged_tx_count"] == 2
	assert pat["watchlist_summary"]["matched_tx_count"] == 5
	assert pat["watchlist_summary"]["matched_amount"] == 690.0


def test_compliance_html_export_renders_structured_report_without_raw_pre():
	"""SUC-25, BR-IR-03, ISS-046: HTML export renders structured tables and @media print for SAR and Executive."""
	project_repo = InMemoryProjectRepository()
	job_repo = InMemoryDetectionJobRepository()
	storage = _MemoryStorage()
	case_store = _MemoryCaseStore()
	project_id = uuid4()
	job_id = uuid4()
	project_repo.save(Project(project_id=project_id, user_id=uuid4(), project_name="HTML Export Audit"))

	rows = [
		{"event_id": "E1", "user_id": "U1", "timestamp": "2026-11-01T10:00:00Z", "amount": 500.0,
		 "model_score": 0.9, "rule_action": "REJECT", "final_action": "REJECT",
		 "triggered_rules": json.dumps(["R1"]), "label": 1},
		{"event_id": "E2", "user_id": "U2", "timestamp": "2026-11-01T11:00:00Z", "amount": 100.0,
		 "model_score": 0.1, "rule_action": "ALLOW", "final_action": "ALLOW",
		 "triggered_rules": "[]", "label": 1},
	]
	path = f"datasets/{project_id}/inferences/{job_id}/predictions.parquet"
	storage.files[path] = _make_parquet_bytes(rows)
	job_repo.save(DetectionJob(
		job_id=job_id, project_id=project_id, job_name="HTML Scan",
		output_path=path, score_threshold=0.5, status=DetectionJobStatus.COMPLETED,
	))
	case = Case(
		project_id=project_id, event_id="E1", user_id="U1",
		tx_timestamp=datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc),
		amount=500.0, final_action=RuleAction.REJECT, dataset_artifact_id=None,
		detection_job_id=job_id, case_code="CASE-HTML-01", model_score=0.9,
		status=CaseStatus.RESOLVED_FRAUD, priority=RiskLevel.CRITICAL,
		resolution_reason="ACCOUNT_TAKEOVER", resolution_summary="Verified fraud",
		resolved_at=datetime(2026, 11, 1, 11, 0, tzinfo=timezone.utc), resolved_by="auditor",
	)
	case_store.cases.append(case)
	service = InsightReportService(
		project_repo=project_repo, detection_job_repo=job_repo, case_repo=case_store,
		blacklist_repo=_MemoryBlacklistRepo([]), audit_repo=case_store, file_storage=storage,
	)

	exec_html, _, exec_mime = service.export_report(project_id, "executive", "html")
	exec_text = exec_html.decode("utf-8")
	assert "text/html" in exec_mime
	assert "<table" in exec_text
	assert "@media print" in exec_text
	assert "<pre>" not in exec_text
	assert "VDR" in exec_text and "Missed Fraud" in exec_text and "PSI" in exec_text

	sar_html, _, sar_mime = service.export_report(project_id, "sar", "html", case_id=case.case_id)
	sar_text = sar_html.decode("utf-8")
	assert "text/html" in sar_mime
	assert "<table" in sar_text
	assert "@media print" in sar_text
	assert "<pre>" not in sar_text
	assert "CASE-HTML-01" in sar_text

