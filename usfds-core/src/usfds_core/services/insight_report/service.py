"""Insight & Report Domain Service (SUC-22, SUC-23, SUC-24, SUC-25)."""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from usfds_core.domain.entities.case import Case, EntityBlacklist
from usfds_core.domain.entities.detection import DetectionJob
from usfds_core.domain.entities.rule import Rule, RuleVersion
from usfds_core.repositories.base_case_repo import (
	IAuditRepository,
	IBlacklistRepository,
	ICaseRepository,
)
from usfds_core.repositories.base_detection_job_repo import IDetectionJobRepository
from usfds_core.repositories.base_project_repo import IProjectRepository
from usfds_core.repositories.base_rule_repo import IRuleRepository, IRuleVersionRepository
from usfds_core.services.insight_report.engine import DuckDBInsightEngine
from usfds_core.services.insight_report.report_builder import ComplianceReportBuilder
from usfds_core.storage.base_storage import IFileStorage


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
	if dt is None:
		return None
	return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


class InsightReportService:
	"""Orchestrates cross-lifecycle Fraud Insights, Policy Attribution, and SAR/Executive Reporting."""

	def __init__(
		self,
		project_repo: Optional[IProjectRepository] = None,
		detection_job_repo: Optional[IDetectionJobRepository] = None,
		case_repo: Optional[ICaseRepository] = None,
		blacklist_repo: Optional[IBlacklistRepository] = None,
		audit_repo: Optional[IAuditRepository] = None,
		rule_repo: Optional[IRuleRepository] = None,
		rule_version_repo: Optional[IRuleVersionRepository] = None,
		file_storage: Optional[IFileStorage] = None,
	):
		self.project_repo = project_repo
		self.detection_job_repo = detection_job_repo
		self.case_repo = case_repo
		self.blacklist_repo = blacklist_repo
		self.audit_repo = audit_repo
		self.rule_repo = rule_repo
		self.rule_version_repo = rule_version_repo
		self.file_storage = file_storage

	def _validate_project(self, project_id: UUID) -> str:
		if not self.project_repo:
			return f"Project-{str(project_id)[:8]}"
		project = self.project_repo.get_by_id(project_id)
		if not project:
			raise LookupError(f"Project '{project_id}' not found.")
		return project.project_name

	def _collect_scoped_data(
		self,
		project_id: UUID,
		job_ids: Optional[list[UUID]] = None,
		model_version_id: Optional[UUID] = None,
		date_from: Optional[datetime] = None,
		date_to: Optional[datetime] = None,
	) -> tuple[
		list[DetectionJob],
		list[DetectionJob],
		list[Case],
		list[tuple[Rule, Optional[RuleVersion]]],
		list[EntityBlacklist],
	]:
		"""Enforces BR-IR-01 project isolation and applies optional job/date/model filters."""
		self._validate_project(project_id)

		all_jobs = (
			self.detection_job_repo.list_by_project(project_id)
			if self.detection_job_repo
			else []
		)
		completed_jobs = [
			j for j in all_jobs
			if (j.status.value if hasattr(j.status, "value") else str(j.status)) == "COMPLETED"
		]
		all_cases = (
			self.case_repo.list_by_project(project_id)
			if self.case_repo
			else []
		)

		job_id_set = {str(jid) for jid in job_ids} if job_ids else None
		model_ver_str = str(model_version_id) if model_version_id else None
		dt_from = _ensure_utc(date_from)
		dt_to = _ensure_utc(date_to)

		filtered_jobs: list[DetectionJob] = []
		for j in completed_jobs:
			if job_id_set is not None and str(j.job_id) not in job_id_set:
				continue
			if model_ver_str is not None and str(j.model_version_id or "") != model_ver_str:
				continue
			j_dt = _ensure_utc(j.created_at)
			if dt_from and j_dt and j_dt < dt_from:
				continue
			if dt_to and j_dt and j_dt > dt_to:
				continue
			filtered_jobs.append(j)

		filtered_cases: list[Case] = []
		for c in all_cases:
			if job_id_set is not None and str(c.detection_job_id or "") not in job_id_set:
				continue
			if model_ver_str is not None and str(c.model_version_id or "") != model_ver_str:
				continue
			c_dt = _ensure_utc(c.created_at)
			if dt_from and c_dt and c_dt < dt_from:
				continue
			if dt_to and c_dt and c_dt > dt_to:
				continue
			filtered_cases.append(c)

		rules_with_versions: list[tuple[Rule, Optional[RuleVersion]]] = []
		if self.rule_repo:
			for r in self.rule_repo.list_by_project(project_id):
				ver: Optional[RuleVersion] = None
				if self.rule_version_repo:
					if r.current_version_id:
						ver = self.rule_version_repo.get_by_id(r.current_version_id)
					if ver is None:
						ver = self.rule_version_repo.get_latest_version(r.rule_id)
				rules_with_versions.append((r, ver))

		blacklist_entries = (
			self.blacklist_repo.list_by_project(project_id)
			if self.blacklist_repo
			else []
		)

		return completed_jobs, filtered_jobs, filtered_cases, rules_with_versions, blacklist_entries

	def _build_engine(
		self,
		project_id: UUID,
		job_ids: Optional[list[UUID]] = None,
		model_version_id: Optional[UUID] = None,
		date_from: Optional[datetime] = None,
		date_to: Optional[datetime] = None,
		label_source: str = "VERIFIED_WITH_DATASET_FALLBACK",
	) -> tuple[DuckDBInsightEngine, list[DetectionJob]]:
		completed_jobs, filtered_jobs, filtered_cases, rules_with_ver, blacklist_entries = self._collect_scoped_data(
			project_id=project_id,
			job_ids=job_ids,
			model_version_id=model_version_id,
			date_from=date_from,
			date_to=date_to,
		)
		engine = DuckDBInsightEngine(
			file_storage=self.file_storage,
			jobs=filtered_jobs,
			cases=filtered_cases,
			rules=rules_with_ver,
			blacklist=blacklist_entries,
			label_source=label_source,
		)
		return engine, completed_jobs

	def get_executive_overview(
		self,
		project_id: UUID,
		job_ids: Optional[list[UUID]] = None,
		date_from: Optional[datetime] = None,
		date_to: Optional[datetime] = None,
		label_source: str = "VERIFIED_WITH_DATASET_FALLBACK",
	) -> dict[str, Any]:
		"""SUC-22: Executive Financial & Case Operations Dashboard."""
		engine, completed_jobs = self._build_engine(
			project_id=project_id,
			job_ids=job_ids,
			date_from=date_from,
			date_to=date_to,
			label_source=label_source,
		)
		overview = engine.compute_executive_overview()
		overview["available_jobs"] = [
			{
				"job_id": str(j.job_id),
				"job_name": j.job_name or f"Job-{str(j.job_id)[:8]}",
				"model_version_id": str(j.model_version_id) if j.model_version_id else None,
				"total_records": j.total_records or 0,
				"fraud_records": j.fraud_records or 0,
				"score_threshold": j.score_threshold,
				"created_at": j.created_at.isoformat(),
			}
			for j in completed_jobs
		]
		return overview

	def get_effectiveness_analysis(
		self,
		project_id: UUID,
		job_ids: Optional[list[UUID]] = None,
		model_version_id: Optional[UUID] = None,
		date_from: Optional[datetime] = None,
		date_to: Optional[datetime] = None,
		label_source: str = "VERIFIED_WITH_DATASET_FALLBACK",
	) -> dict[str, Any]:
		"""SUC-23: Rule & Model Ground-Truth Performance Analysis."""
		engine, _ = self._build_engine(
			project_id=project_id,
			job_ids=job_ids,
			model_version_id=model_version_id,
			date_from=date_from,
			date_to=date_to,
			label_source=label_source,
		)
		return engine.compute_effectiveness_analysis()

	def get_typology_and_patterns(
		self,
		project_id: UUID,
		job_ids: Optional[list[UUID]] = None,
		date_from: Optional[datetime] = None,
		date_to: Optional[datetime] = None,
		label_source: str = "VERIFIED_WITH_DATASET_FALLBACK",
	) -> dict[str, Any]:
		"""SUC-24: Fraud Typologies & Temporal-Behavioral Patterns."""
		engine, _ = self._build_engine(
			project_id=project_id,
			job_ids=job_ids,
			date_from=date_from,
			date_to=date_to,
			label_source=label_source,
		)
		return engine.compute_typology_and_patterns()

	def generate_sar_dossier(
		self,
		project_id: UUID,
		case_id: UUID,
		prepared_by: str = "local-analyst",
		reviewer_notes: str = "",
	) -> dict[str, Any]:
		"""SUC-25 (Template 1): Generates a 5-section Suspicious Activity Report (SAR) Dossier (BR-IR-03)."""
		project_name = self._validate_project(project_id)
		if not self.case_repo:
			raise ValueError("CaseRepository is not configured.")
		case = self.case_repo.get_by_id(case_id)
		if not case or case.project_id != project_id:
			raise LookupError(f"Case '{case_id}' not found in project '{project_id}'.")

		all_project_cases = self.case_repo.list_by_project(project_id)
		audit_logs = (
			self.audit_repo.list_for_entity(project_id, "CASE", str(case_id))
			if self.audit_repo
			else []
		)
		blacklist_entries = (
			self.blacklist_repo.list_by_project(project_id)
			if self.blacklist_repo
			else []
		)

		dossier = ComplianceReportBuilder.build_sar_dossier(
			project_id=str(project_id),
			project_name=project_name,
			case=case,
			related_cases=all_project_cases,
			audit_logs=audit_logs,
			blacklist_entries=blacklist_entries,
			prepared_by=prepared_by,
			reviewer_notes=reviewer_notes,
		)
		dossier["markdown_preview"] = ComplianceReportBuilder.format_sar_markdown(dossier)
		return dossier

	def generate_executive_audit_report(
		self,
		project_id: UUID,
		job_ids: Optional[list[UUID]] = None,
		date_from: Optional[datetime] = None,
		date_to: Optional[datetime] = None,
		label_source: str = "VERIFIED_WITH_DATASET_FALLBACK",
		prepared_by: str = "local-analyst",
		reviewer_notes: str = "",
	) -> dict[str, Any]:
		"""SUC-25 (Template 2): Generates an Executive Fraud & Policy Audit Report."""
		project_name = self._validate_project(project_id)
		engine, _ = self._build_engine(
			project_id=project_id,
			job_ids=job_ids,
			date_from=date_from,
			date_to=date_to,
			label_source=label_source,
		)
		overview = engine.compute_executive_overview()
		effectiveness = engine.compute_effectiveness_analysis()
		patterns = engine.compute_typology_and_patterns()

		report = ComplianceReportBuilder.build_executive_audit_report(
			project_id=str(project_id),
			project_name=project_name,
			overview=overview,
			effectiveness=effectiveness,
			patterns=patterns,
			prepared_by=prepared_by,
			reviewer_notes=reviewer_notes,
		)
		report["markdown_preview"] = ComplianceReportBuilder.format_executive_markdown(report)
		return report

	def export_report(
		self,
		project_id: UUID,
		report_type: str,
		file_format: str = "md",
		case_id: Optional[UUID] = None,
		job_ids: Optional[list[UUID]] = None,
		date_from: Optional[datetime] = None,
		date_to: Optional[datetime] = None,
		label_source: str = "VERIFIED_WITH_DATASET_FALLBACK",
		prepared_by: str = "local-analyst",
		reviewer_notes: str = "",
	) -> tuple[bytes, str, str]:
		"""Exports a SAR Dossier or Executive Audit Report as (.md, .json, .csv, .html) bytes."""
		rtype = report_type.strip().upper()
		if rtype in ("SAR", "SAR_DOSSIER"):
			if case_id is None:
				raise ValueError("case_id is required when exporting a SAR Dossier.")
			payload = self.generate_sar_dossier(
				project_id=project_id,
				case_id=case_id,
				prepared_by=prepared_by,
				reviewer_notes=reviewer_notes,
			)
		elif rtype in ("EXECUTIVE", "EXECUTIVE_AUDIT_REPORT"):
			payload = self.generate_executive_audit_report(
				project_id=project_id,
				job_ids=job_ids,
				date_from=date_from,
				date_to=date_to,
				label_source=label_source,
				prepared_by=prepared_by,
				reviewer_notes=reviewer_notes,
			)
		else:
			raise ValueError(f"Unsupported report_type '{report_type}'. Expected 'sar' or 'executive'.")

		export_payload = {k: v for k, v in payload.items() if k != "markdown_preview"}
		return ComplianceReportBuilder.format_report_export(export_payload, file_format=file_format)
