from dataclasses import replace
from datetime import datetime, timezone
from math import isfinite, log10
from uuid import UUID

from usfds_core.domain.entities.case import (
	AuditLog, BlacklistEntityType, Case, CaseStatus, EntityBlacklist,
	FRAUD_REASONS, LEGITIMATE_REASONS, OPEN_STATUSES,
)
from usfds_core.domain.entities.enums import RiskLevel, RuleAction
from usfds_core.repositories.base_case_repo import (
	CaseConflictError, IAuditRepository, IBlacklistRepository, ICaseRepository,
)


def compute_priority(case: Case) -> tuple[float, RiskLevel]:
	action_factor = 1.0 if case.final_action == RuleAction.REJECT else 0.6
	score = round(
		45 * (case.model_score or 0) + 35 * action_factor
		+ 10 * min(len(case.triggered_rule_codes), 3) / 3
		+ 10 * min(log10(1 + case.amount) / 7, 1), 2,
	)
	priority = RiskLevel.LOW
	for threshold, level in ((35, RiskLevel.MEDIUM), (55, RiskLevel.HIGH), (75, RiskLevel.CRITICAL)):
		if score >= threshold:
			priority = level
	return score, priority


class BlacklistService:
	def __init__(self, repository: IBlacklistRepository, audit: IAuditRepository):
		self.repository = repository
		self.audit = audit

	def add(self, entry: EntityBlacklist) -> EntityBlacklist:
		entry.entity_value = entry.entity_value.strip()
		entry.reason = entry.reason.strip()
		if not entry.entity_value or len(entry.reason) < 10:
			raise ValueError("Entity value and a reason of at least 10 characters are required")
		if any(
			item.status == "ACTIVE" and item.entity_type == entry.entity_type
			and item.entity_value == entry.entity_value
			for item in self.repository.list_by_project(entry.project_id)
		):
			raise CaseConflictError("Entity is already blacklisted")
		saved = self.repository.save(entry)
		self.audit.append(AuditLog(
			entry.project_id, "BLACKLIST_ENTRY", str(entry.blacklist_id), "CREATED",
			entry.created_by, entry.reason, {"source_case_id": str(entry.source_case_id) if entry.source_case_id else None},
		))
		return saved

	def remove(self, project_id: UUID, blacklist_id: UUID, actor: str, reason: str) -> EntityBlacklist:
		if len(reason.strip()) < 10:
			raise ValueError("Removal reason must have at least 10 characters")
		entry = next((item for item in self.repository.list_by_project(project_id) if item.blacklist_id == blacklist_id), None)
		if entry is None:
			raise LookupError("Blacklist entry not found")
		if entry.status != "ACTIVE":
			raise CaseConflictError("Blacklist entry has already been removed")
		entry = replace(entry, status="REMOVED", removed_by=actor, removed_at=datetime.now(timezone.utc))
		saved = self.repository.save(entry)
		self.audit.append(AuditLog(project_id, "BLACKLIST_ENTRY", str(blacklist_id), "REMOVED", actor, reason.strip()))
		return saved


class CaseService:
	def __init__(self, repository: ICaseRepository, audit: IAuditRepository, blacklist: IBlacklistRepository):
		self.repository = repository
		self.audit = audit
		self.blacklist = blacklist

	def get(self, project_id: UUID, case_id: UUID) -> Case:
		case = self.repository.get_by_id(case_id)
		if case is None or case.project_id != project_id:
			raise LookupError("Case not found in this project")
		return case

	def intake(self, cases: list[Case], actor: str) -> dict:
		for case in cases:
			if not case.event_id.strip() or not case.user_id.strip():
				raise ValueError("Event and user IDs are required")
			if not isfinite(case.amount) or case.amount < 0:
				raise ValueError("Amount must be finite and non-negative")
			if case.model_score is not None and (not isfinite(case.model_score) or not 0 <= case.model_score <= 1):
				raise ValueError("Model score must be finite and within [0,1]")
			if case.final_action not in {RuleAction.REVIEW, RuleAction.REJECT}:
				raise ValueError("Only REVIEW or REJECT transactions can become cases")
		created, skipped = [], []
		for case in cases:
			if self.repository.get_by_event(case.project_id, case.event_id):
				skipped.append(case.event_id)
				continue
			case.priority_score, case.priority = compute_priority(case)
			case.case_code = f"CASE-{case.created_at.year}-{case.case_id.hex.upper()}"
			saved = self.repository.save(case)
			self.audit.append(AuditLog(case.project_id, "CASE", str(case.case_id), "CREATED", actor, details={"event_id": case.event_id}))
			created.append(str(saved.case_id))
		return {"created_case_ids": created, "accepted_count": len(created), "skipped_event_ids": skipped}

	def update(self, project_id: UUID, case_id: UUID, expected_version: int, action: str, actor: str,
			 reason: str = "", summary: str = "", assignee: str | None = None,
			 block_entities: list[tuple[BlacklistEntityType, str]] | None = None) -> tuple[Case, list[str]]:
		case = self.get(project_id, case_id)
		if block_entities and action != "resolve-fraud":
			raise ValueError("Blacklisting is only allowed with fraud resolution")
		if case.version != expected_version:
			raise CaseConflictError("Case changed; refresh before submitting again")
		previous = {"status": case.status.value, "reason": case.resolution_reason, "summary": case.resolution_summary, "assigned_to": case.assigned_to}
		case = replace(case)
		warnings = []
		if action == "reopen":
			if case.status in OPEN_STATUSES or len(summary.strip()) < 10:
				raise ValueError("Only resolved cases can reopen; a reason of at least 10 characters is required")
			case.status = CaseStatus.IN_PROGRESS
			case.assigned_to = actor
			case.resolution_reason = case.resolution_summary = None
			case.resolved_at = case.resolved_by = None
		elif case.status not in OPEN_STATUSES:
			raise CaseConflictError("Case is already resolved")
		elif action == "claim":
			if case.assigned_to and case.assigned_to != actor:
				raise CaseConflictError(f"Case is assigned to {case.assigned_to}")
			warnings = sorted({
				item.assigned_to for item in self.repository.list_by_project(project_id)
				if item.user_id == case.user_id and item.case_id != case_id and item.status in OPEN_STATUSES
				and item.assigned_to and item.assigned_to != actor
			})
			case.status, case.assigned_to = CaseStatus.IN_PROGRESS, actor
		elif action == "pending-customer":
			if len(summary.strip()) < 10:
				raise ValueError("A customer contact note of at least 10 characters is required")
			case.status = CaseStatus.PENDING_CUSTOMER
		elif action == "escalate":
			if not assignee or not assignee.strip() or len(summary.strip()) < 10:
				raise ValueError("Escalation requires an assignee and a note of at least 10 characters")
			case.priority, case.assigned_to = RiskLevel.CRITICAL, assignee.strip()
		elif action in {"resolve-fraud", "resolve-legitimate"}:
			allowed = FRAUD_REASONS if action == "resolve-fraud" else LEGITIMATE_REASONS
			if reason not in allowed or len(summary.strip()) < 10:
				raise ValueError("Select a valid resolution reason and provide at least 10 characters of evidence")
			if action == "resolve-legitimate" and block_entities:
				raise ValueError("Legitimate resolution cannot blacklist entities")
			for entity_type, value in block_entities or []:
				expected_value = case.user_id if entity_type == BlacklistEntityType.USER_ID else case.attributes.get(entity_type.value.lower())
				if not value or str(expected_value) != value:
					raise ValueError("Mitigation entity must belong to this transaction")
			case.status = CaseStatus.RESOLVED_FRAUD if action == "resolve-fraud" else CaseStatus.RESOLVED_LEGITIMATE
			case.resolution_reason, case.resolution_summary = reason, summary.strip()
			case.resolved_at, case.resolved_by = datetime.now(timezone.utc), actor
		else:
			raise ValueError("Unsupported case action")
		case.updated_at = datetime.now(timezone.utc)
		saved = self.repository.save(case, expected_version)
		for entity_type, value in block_entities or []:
			existing = next((entry for entry in self.blacklist.list_by_project(project_id) if entry.status == "ACTIVE" and entry.entity_type == entity_type and entry.entity_value == value), None)
			if existing is None:
				BlacklistService(self.blacklist, self.audit).add(EntityBlacklist(project_id, entity_type, value, summary.strip(), actor, source_case_id=case_id))
		self.audit.append(AuditLog(project_id, "CASE", str(case_id), action.upper().replace("-", "_"), actor,
			summary.strip() or None, {"before": previous, "after": {"status": saved.status.value, "assigned_to": saved.assigned_to}, "blacklisted_entities": [{"type": kind.value, "value": value} for kind, value in block_entities or []]}))
		return saved, warnings

	def add_note(self, project_id: UUID, case_id: UUID, actor: str, note: str) -> None:
		self.get(project_id, case_id)
		if not note.strip():
			raise ValueError("Note must not be empty")
		self.audit.append(AuditLog(project_id, "CASE", str(case_id), "NOTE_ADDED", actor, note.strip()))


def rule_feedback(cases: list[Case]) -> list[dict]:
	rows = {}
	for case in cases:
		for rule in case.triggered_rules:
			key = (rule["rule_id"], rule["rule_version_id"])
			row = rows.setdefault(key, {"rule_id": key[0], "rule_version_id": key[1], "rule_code": rule["rule_code"],
				"version_number": rule["version_number"], "cases_triggered": 0, "tp": 0, "fp": 0, "pending": 0})
			row["cases_triggered"] += 1
			row["pending" if case.verified_label is None else "tp" if case.verified_label == 1 else "fp"] += 1
	for row in rows.values():
		resolved = row["tp"] + row["fp"]
		row["verified_false_positive_ratio"] = row["fp"] / resolved if resolved else None
	return list(rows.values())