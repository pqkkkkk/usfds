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


class _MemoryStorage:
	def __init__(self):
		self.files: dict[str, bytes] = {}

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
