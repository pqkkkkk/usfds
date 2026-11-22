from datetime import datetime, timedelta, timezone
from copy import deepcopy
import io
from uuid import uuid4

import pytest
import pandas as pd

from usfds_core.domain.entities.case import Case, CaseStatus
from usfds_core.domain.entities.detection import DetectionJob
from usfds_core.domain.entities.enums import DetectionJobStatus, RiskLevel, RuleAction
from usfds_core.repositories.base_case_repo import CaseConflictError
from usfds_core.services.investigation.behavior_profile import (
	build_behavior_profile,
	build_behavior_profile_from_warehouse,
	build_rule_draft,
)
from usfds_core.services.investigation.case_service import CaseService, rule_feedback
from usfds_core.services.warehouse.project_warehouse import ProjectWarehouse
from usfds_core.storage.base_storage import IFileStorage


def test_single_transaction_case_ground_truth():
	case = Case(
		project_id=uuid4(), event_id="TX-1", user_id="USER-1",
		tx_timestamp=datetime.now(timezone.utc), amount=100,
		final_action=RuleAction.REVIEW, dataset_artifact_id=uuid4(), model_score=0.99,
	)
	assert case.verified_label is None
	case.status = CaseStatus.RESOLVED_LEGITIMATE
	assert case.verified_label == 0
	case.status = CaseStatus.RESOLVED_FRAUD
	assert case.verified_label == 1
	case.status = CaseStatus.IN_PROGRESS
	assert case.verified_label is None


class MemoryStore:
	def __init__(self):
		self.cases = {}
		self.logs = []

	def save(self, case, expected_version=None):
		if expected_version is not None:
			if self.cases[case.case_id].version != expected_version:
				raise CaseConflictError("stale")
			case.version += 1
		self.cases[case.case_id] = deepcopy(case)
		return deepcopy(case)

	def get_by_id(self, case_id):
		return deepcopy(self.cases.get(case_id))

	def get_by_event(self, project_id, event_id):
		return next((deepcopy(case) for case in self.cases.values() if case.project_id == project_id and case.event_id == event_id), None)

	def list_by_project(self, project_id):
		return [deepcopy(case) for case in self.cases.values() if case.project_id == project_id]

	def append(self, log):
		self.logs.append(log)


def test_case_lifecycle_is_independent_and_versioned():
	store = MemoryStore()
	service = CaseService(store, store, store)
	project_id = uuid4()
	cases = [Case(project_id, event_id, "USER-1", datetime.now(timezone.utc), 100,
		RuleAction.REVIEW, uuid4(), triggered_rules=[{
			"rule_id": "rule", "rule_version_id": "v1", "rule_code": "R1", "version_number": 1,
		}]) for event_id in ("TX-1", "TX-2")]
	assert service.intake(cases, "A")["accepted_count"] == 2
	assert service.intake(cases, "A")["skipped_event_ids"] == ["TX-1", "TX-2"]
	pending = service.update(project_id, cases[0].case_id, 1, "pending-customer", "A", summary="Contacted cardholder for verification")
	assert pending.status == CaseStatus.PENDING_CUSTOMER
	with pytest.raises(CaseConflictError):
		service.update(project_id, pending.case_id, 1, "pending-customer", "B", summary="Stale version update attempt")
	with pytest.raises(ValueError):
		service.update(project_id, pending.case_id, 2, "resolve-fraud", "A", reason="OTHER_FRAUD", summary="short")
	resolved = service.update(project_id, pending.case_id, 2, "resolve-legitimate", "A", reason="CUSTOMER_CONFIRMED", summary="Customer confirmed the payment")
	assert resolved.verified_label == 0
	assert service.get(project_id, cases[1].case_id).status == CaseStatus.OPEN
	assert rule_feedback(store.list_by_project(project_id))[0]["verified_false_positive_ratio"] == 1
	assert rule_feedback(store.list_by_project(project_id))[0]["pending"] == 1
	reopened = service.update(project_id, pending.case_id, 3, "reopen", "A", summary="New evidence warrants investigation")
	assert reopened.verified_label is None
	assert store.logs[-1].details["before"]["summary"] == "Customer confirmed the payment"


def test_baseline_excludes_current_and_future_and_draft_uses_raw_schema():
	case = Case(uuid4(), "TX-1", "USER-1", datetime(2026, 10, 10, tzinfo=timezone.utc), 1000, RuleAction.REVIEW, uuid4())
	frame = pd.DataFrame([
		{"event_id": "OLD", "user_id": "USER-1", "timestamp": "2026-10-09T00:00:00Z", "amount": 100},
		{"event_id": "TX-1", "user_id": "USER-1", "timestamp": "2026-10-10T00:00:00Z", "amount": 1000},
		{"event_id": "FUTURE", "user_id": "USER-1", "timestamp": "2026-10-11T00:00:00Z", "amount": 90000},
	])
	profile = build_behavior_profile(frame, case)
	assert profile["avg_amount"] == 100
	assert profile["comparison"][0]["is_anomalous"]
	assert len(profile["timeline"]) == 2
	case.user_id = "NEW"
	assert build_behavior_profile(frame, case)["source"] == "POPULATION"
	case.status = CaseStatus.RESOLVED_FRAUD
	case.attributes = {"amount": 1000}
	case.feature_contributions = [{"feature_name": "unknown", "contribution": 1}, {"feature_name": "amount", "contribution": .2}]
	assert build_rule_draft(case, {"columns": {"amount": {"logical_type": "NUMERIC"}}})["condition"] == {"and": [{">=": [{"var": "amount"}, 1000]}]}


def test_case_escalate_without_assignee_and_claim_rejected():
	"""ISS-045 / SUC-18: Escalate only promotes priority to CRITICAL with a note; claim and assigned_to are removed."""
	store = MemoryStore()
	service = CaseService(store, store, store)
	project_id = uuid4()
	case = Case(project_id, "TX-ESC", "USER-1", datetime.now(timezone.utc), 500, RuleAction.REVIEW, None)
	assert not hasattr(case, "assigned_to")
	service.intake([case], "analyst")

	with pytest.raises(ValueError):
		service.update(project_id, case.case_id, 1, "claim", "analyst")
	with pytest.raises(ValueError):
		service.update(project_id, case.case_id, 1, "escalate", "analyst", summary="short")

	escalated = service.update(
		project_id, case.case_id, 1, "escalate", "analyst",
		summary="High velocity card testing pattern requires urgent review",
	)
	assert isinstance(escalated, Case)
	assert escalated.priority == RiskLevel.CRITICAL
	assert escalated.version == 2
	assert store.logs[-1].action == "ESCALATE"
	assert "assigned_to" not in store.logs[-1].details.get("before", {})
	assert "assigned_to" not in store.logs[-1].details.get("after", {})


class _MemoryStorage(IFileStorage):
	def __init__(self):
		self.files: dict[str, bytes] = {}

	def save_bytes(self, file_path: str, data: bytes) -> str:
		self.files[file_path] = data
		return file_path

	def read_bytes(self, file_path: str) -> bytes:
		return self.files[file_path]

	def exists(self, file_path: str) -> bool:
		return file_path in self.files


def test_behavior_profile_from_warehouse_uses_duckdb_with_five_entity_dimensions(monkeypatch):
	"""ISS-045 / SUC-18: Workbench behavior profile queries ProjectWarehouse via DuckDB across all 5 entity dims without pandas file reads."""
	def _blocked(*args, **kwargs):
		raise AssertionError("pandas file read must not be used (ISS-045)")

	monkeypatch.setattr(pd, "read_parquet", _blocked)
	monkeypatch.setattr(pd, "read_csv", _blocked)

	storage = _MemoryStorage()
	project_id = uuid4()
	job_id = uuid4()
	rows = [
		{"event_id": "OLD-FAR", "user_id": "U1", "timestamp": "2026-08-01T02:00:00Z", "amount": 9999.0, "final_action": "ALLOW",
		 "device_id": "D-OLD", "ip_address": "9.9.9.9", "card_id": "C-OLD", "merchant_id": "M-OLD", "merchant_category": "TRAVEL"},
		{"event_id": "OLD-1", "user_id": "U1", "timestamp": "2026-10-05T02:00:00Z", "amount": 100.0, "final_action": "ALLOW",
		 "device_id": "D1", "ip_address": "1.1.1.1", "card_id": "C1", "merchant_id": "M1", "merchant_category": "GROCERY"},
		{"event_id": "OLD-2", "user_id": "U1", "timestamp": "2026-10-08T02:30:00Z", "amount": 200.0, "final_action": "ALLOW",
		 "device_id": "D1", "ip_address": "1.1.1.1", "card_id": "C1", "merchant_id": "M1", "merchant_category": "GROCERY"},
		{"event_id": "OTHER-1", "user_id": "U2", "timestamp": "2026-10-07T10:00:00Z", "amount": 500.0, "final_action": "ALLOW",
		 "device_id": "D2", "ip_address": "2.2.2.2", "card_id": "C2", "merchant_id": "M2", "merchant_category": "RETAIL"},
		{"event_id": "TX-1", "user_id": "U1", "timestamp": "2026-10-10T14:00:00Z", "amount": 1000.0, "final_action": "REVIEW",
		 "device_id": "D-NEW", "ip_address": "1.1.1.1", "card_id": "C1", "merchant_id": "M1", "merchant_category": "CRYPTO"},
		{"event_id": "FUTURE", "user_id": "U1", "timestamp": "2026-10-11T00:00:00Z", "amount": 90000.0, "final_action": "ALLOW",
		 "device_id": "D-FUT", "ip_address": "8.8.8.8", "card_id": "C-FUT", "merchant_id": "M-FUT", "merchant_category": "LUXURY"},
	]
	buf = io.BytesIO()
	pd.DataFrame(rows).to_parquet(buf, index=False)
	pred_path = f"datasets/{project_id}/inferences/{job_id}/predictions.parquet"
	storage.save_bytes(pred_path, buf.getvalue())

	job = DetectionJob(
		job_id=job_id,
		project_id=project_id,
		job_name="job-1",
		output_path=pred_path,
		status=DetectionJobStatus.COMPLETED,
		score_threshold=0.5,
		created_at=datetime(2026, 10, 12, tzinfo=timezone.utc),
	)
	warehouse = ProjectWarehouse(storage)
	assert warehouse.write_job_facts(job) == warehouse.fact_key(job)

	case = Case(
		project_id=project_id,
		event_id="TX-1",
		user_id="U1",
		tx_timestamp=datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc),
		amount=1000.0,
		final_action=RuleAction.REVIEW,
		dataset_artifact_id=None,
		detection_job_id=job_id,
	)
	profile = build_behavior_profile_from_warehouse(warehouse, [job], case, days=30)
	assert profile["available"] is True
	assert profile["cold_start"] is False
	assert profile["source"] == "USER"
	assert profile["history_count"] == 2
	assert profile["avg_amount"] == pytest.approx(150.0)
	assert profile["max_amount"] == pytest.approx(200.0)
	assert profile["transactions_per_day"] == pytest.approx(2 / 30)
	assert profile["common_hours_utc"] == [2]

	comp = {entry["field"]: entry for entry in profile["comparison"]}
	assert set(comp) == {"amount", "hour_utc", "device_id", "ip_address", "card_id", "merchant_id", "merchant_category"}
	assert comp["amount"]["is_anomalous"] is True
	assert comp["hour_utc"]["is_anomalous"] is True
	assert comp["device_id"]["current"] == "D-NEW" and comp["device_id"]["is_anomalous"] is True
	assert comp["ip_address"]["current"] == "1.1.1.1" and comp["ip_address"]["is_anomalous"] is False
	assert comp["card_id"]["current"] == "C1" and comp["card_id"]["is_anomalous"] is False
	assert comp["merchant_id"]["current"] == "M1" and comp["merchant_id"]["is_anomalous"] is False
	assert comp["merchant_category"]["current"] == "CRYPTO" and comp["merchant_category"]["is_anomalous"] is True

	assert [t["event_id"] for t in profile["timeline"]] == ["OLD-1", "OLD-2", "TX-1"]
	assert profile["timeline"][-1]["is_current"] is True

	cold_case = Case(
		project_id=project_id,
		event_id="TX-COLD",
		user_id="NEW_USER",
		tx_timestamp=datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc),
		amount=1000.0,
		final_action=RuleAction.REVIEW,
		dataset_artifact_id=None,
	)
	cold_profile = build_behavior_profile_from_warehouse(warehouse, [job], cold_case, days=30)
	assert cold_profile["available"] is True
	assert cold_profile["cold_start"] is True
	assert cold_profile["source"] == "POPULATION"
	assert cold_profile["transactions_per_day"] is None