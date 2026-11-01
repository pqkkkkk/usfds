from datetime import datetime, timezone
from copy import deepcopy
from uuid import uuid4

import pytest
import pandas as pd

from usfds_core.domain.entities.case import Case, CaseStatus
from usfds_core.domain.entities.enums import RuleAction
from usfds_core.repositories.base_case_repo import CaseConflictError
from usfds_core.services.investigation.behavior_profile import build_behavior_profile, build_rule_draft
from usfds_core.services.investigation.case_service import CaseService, rule_feedback


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
	claimed, _ = service.update(project_id, cases[0].case_id, 1, "claim", "A")
	with pytest.raises(CaseConflictError):
		service.update(project_id, claimed.case_id, 1, "claim", "B")
	with pytest.raises(ValueError):
		service.update(project_id, claimed.case_id, 2, "resolve-fraud", "A", reason="OTHER_FRAUD", summary="short")
	resolved, _ = service.update(project_id, claimed.case_id, 2, "resolve-legitimate", "A", reason="CUSTOMER_CONFIRMED", summary="Customer confirmed the payment")
	assert resolved.verified_label == 0
	assert service.get(project_id, cases[1].case_id).status == CaseStatus.OPEN
	assert rule_feedback(store.list_by_project(project_id))[0]["verified_false_positive_ratio"] == 1
	assert rule_feedback(store.list_by_project(project_id))[0]["pending"] == 1
	reopened, _ = service.update(project_id, claimed.case_id, 3, "reopen", "A", summary="New evidence warrants investigation")
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