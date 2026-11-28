"""Compliance & Executive Report Builder for SUC-25 (SAR Dossier & Executive Risk Audit Report)."""

import csv
from datetime import datetime, timezone
import html
import io
import json
from typing import Any, Optional

from usfds_core.domain.entities.case import AuditLog, Case, CaseStatus, EntityBlacklist
from usfds_core.services.insight_report.engine import FP_REASON_LABELS, FRAUD_TYPOLOGY_LABELS


def _resolve_reason_label(reason: Optional[str]) -> str:
	if not reason:
		return "Pending / Unspecified"
	if reason in FRAUD_TYPOLOGY_LABELS:
		return FRAUD_TYPOLOGY_LABELS[reason]
	if reason in FP_REASON_LABELS:
		return FP_REASON_LABELS[reason]
	return reason.replace("_", " ").title()


class ComplianceReportBuilder:
	"""Constructs structured 5-section SAR Dossiers and Executive Risk Audit Reports (SUC-25)."""

	@staticmethod
	def build_sar_dossier(
		project_id: str,
		project_name: str,
		case: Case,
		related_cases: list[Case],
		audit_logs: list[AuditLog],
		blacklist_entries: list[EntityBlacklist],
		prepared_by: str = "local-analyst",
		reviewer_notes: str = "",
	) -> dict[str, Any]:
		"""Builds a 5-part Suspicious Activity Report (SAR) Dossier for a case (BR-IR-03)."""
		generated_at = datetime.now(timezone.utc).isoformat()
		verdict_label = (
			"CONFIRMED_FRAUD"
			if case.status == CaseStatus.RESOLVED_FRAUD
			else "FALSE_POSITIVE"
			if case.status == CaseStatus.RESOLVED_LEGITIMATE
			else case.status.value
		)

		# Extract key attributes if present
		attrs = case.attributes or {}
		channel = str(attrs.get("channel") or attrs.get("payment_channel") or "CARD_NOT_PRESENT")
		merchant = str(attrs.get("merchant_category") or attrs.get("merchant_id") or "—")
		country = str(attrs.get("country") or attrs.get("bin_country") or "—")

		# Related cases summary for the same subject_user_id
		subject_cases = [c for c in related_cases if c.user_id == case.user_id]
		if all(c.case_id != case.case_id for c in subject_cases):
			subject_cases = [case, *subject_cases]

		total_subject_exposure = round(sum(float(c.amount) for c in subject_cases), 2)
		confirmed_subject_fraud = round(
			sum(float(c.amount) for c in subject_cases if c.status == CaseStatus.RESOLVED_FRAUD),
			2,
		)

		suspicious_transactions = [
			{
				"case_id": str(c.case_id),
				"case_code": c.case_code,
				"event_id": c.event_id,
				"tx_timestamp": c.tx_timestamp.isoformat(),
				"amount": round(float(c.amount), 2),
				"final_action": c.final_action.value,
				"model_score": round(float(c.model_score), 4) if c.model_score is not None else None,
				"status": c.status.value,
				"channel": str((c.attributes or {}).get("channel") or channel),
				"merchant_category": str((c.attributes or {}).get("merchant_category") or merchant),
				"country": str((c.attributes or {}).get("country") or country),
			}
			for c in subject_cases
		]

		# Top SHAP features
		top_features = []
		for feat in (case.feature_contributions or [])[:8]:
			top_features.append({
				"feature_name": str(feat.get("feature_name") or feat.get("feature") or "feature"),
				"feature_value": feat.get("feature_value"),
				"shap_value": round(float(feat.get("shap_value") or feat.get("contribution") or 0.0), 4),
				"direction": str(feat.get("direction") or ("RISK_UP" if float(feat.get("shap_value") or 0.0) >= 0 else "RISK_DOWN")),
			})

		# Triggered rules
		violated_rules = []
		for r in case.triggered_rules or []:
			clauses = r.get("matched_clauses") or []
			violated_rules.append({
				"rule_code": str(r.get("rule_code") or ""),
				"rule_name": str(r.get("rule_name") or r.get("rule_code") or ""),
				"action": str(r.get("action") or "REVIEW"),
				"version_number": int(r.get("version_number") or 1),
				"trigger_reason": str(r.get("trigger_reason") or " AND ".join(str(c) for c in clauses)),
				"matched_clauses": [str(c) for c in clauses],
			})

		# Automated technical narrative synthesis
		typology_label = _resolve_reason_label(case.resolution_reason)
		rule_summary_str = (
			", ".join(f"{r['rule_code']} ({r['trigger_reason']})" for r in violated_rules)
			if violated_rules
			else "No manual rule triggered (AI-Exclusive detection)"
		)
		shap_summary_str = (
			", ".join(f"{f['feature_name']}={f['feature_value']} (SHAP {f['shap_value']:+.4f})" for f in top_features[:3])
			if top_features
			else "SHAP feature attributions not recorded"
		)
		score_str = f"{case.model_score * 100:.1f}%" if case.model_score is not None else "N/A (Rule-Only)"

		automated_narrative = (
			f"Transaction event '{case.event_id}' by subject '{case.user_id}' for ${case.amount:,.2f} "
			f"at {case.tx_timestamp.isoformat()} was flagged with action '{case.final_action.value}' "
			f"(AI Fraud Probability: {score_str}, Priority: {case.priority.value} [{case.priority_score:.1f}/100]). "
			f"Rule Evidence: {rule_summary_str}. "
			f"Key Anomaly Indicators: {shap_summary_str}. "
			f"Classified Typology: {typology_label}."
		)

		# Linked or subject blacklist entries
		related_blacklist = [
			{
				"blacklist_id": str(b.blacklist_id),
				"entity_type": b.entity_type.value,
				"entity_value": b.entity_value,
				"status": b.status,
				"reason": b.reason,
				"created_by": b.created_by,
				"created_at": b.created_at.isoformat(),
			}
			for b in blacklist_entries
			if b.source_case_id == case.case_id
			or (b.entity_type.value == "USER_ID" and b.entity_value == case.user_id)
		]

		# Verbatim audit trail (BR-IR-03)
		audit_trail = [
			{
				"log_id": str(log.log_id),
				"action": log.action,
				"actor": log.actor,
				"note": log.note or "",
				"details": log.details or {},
				"created_at": log.created_at.isoformat(),
			}
			for log in audit_logs
		]

		return {
			"report_type": "SAR_DOSSIER",
			"report_id": f"SAR-{case.case_code}",
			"generated_at": generated_at,
			"project_id": project_id,
			"project_name": project_name,
			"prepared_by": prepared_by.strip() or "local-analyst",
			"reviewer_notes": reviewer_notes.strip(),
			"section_1_identification": {
				"case_id": str(case.case_id),
				"case_code": case.case_code,
				"subject_user_id": case.user_id,
				"priority": case.priority.value,
				"priority_score": round(float(case.priority_score), 2),
				"status": case.status.value,
				"verdict": verdict_label,
				"verified_label": case.verified_label,
				"detected_at": case.created_at.isoformat(),
				"resolved_at": case.resolved_at.isoformat() if case.resolved_at else None,
				"resolved_by": case.resolved_by or "Pending",
				"detection_job_id": str(case.detection_job_id) if case.detection_job_id else None,
				"model_version_id": str(case.model_version_id) if case.model_version_id else None,
			},
			"section_2_financial_summary": {
				"primary_event_id": case.event_id,
				"primary_tx_timestamp": case.tx_timestamp.isoformat(),
				"primary_amount": round(float(case.amount), 2),
				"final_action": case.final_action.value,
				"channel": channel,
				"merchant_category": merchant,
				"country": country,
				"subject_flagged_tx_count": len(suspicious_transactions),
				"total_subject_exposure": total_subject_exposure,
				"confirmed_fraud_loss_prevented": confirmed_subject_fraud,
				"transactions": suspicious_transactions,
			},
			"section_3_detection_evidence": {
				"model_version_id": str(case.model_version_id) if case.model_version_id else None,
				"model_score": round(float(case.model_score), 4) if case.model_score is not None else None,
				"priority_score": round(float(case.priority_score), 2),
				"violated_rules": violated_rules,
				"top_feature_contributions": top_features,
				"attributes_snapshot": attrs,
			},
			"section_4_narrative_and_typology": {
				"fraud_typology_code": case.resolution_reason or "UNSPECIFIED",
				"fraud_typology_label": typology_label,
				"automated_technical_narrative": automated_narrative,
				"analyst_resolution_summary": case.resolution_summary or "Pending final analyst resolution summary.",
				"reviewer_notes": reviewer_notes.strip(),
			},
			"section_5_mitigation_and_audit": {
				"is_subject_blacklisted": any(
					b["status"] == "ACTIVE" and b["entity_type"] == "USER_ID"
					for b in related_blacklist
				),
				"blacklisted_entities": related_blacklist,
				"audit_trail": audit_trail,
			},
		}

	@staticmethod
	def build_executive_audit_report(
		project_id: str,
		project_name: str,
		overview: dict[str, Any],
		effectiveness: dict[str, Any],
		patterns: dict[str, Any],
		prepared_by: str = "local-analyst",
		reviewer_notes: str = "",
	) -> dict[str, Any]:
		"""Builds a comprehensive Executive Fraud & Policy Audit Report across SUC-22, SUC-23, SUC-24."""
		generated_at = datetime.now(timezone.utc).isoformat()
		return {
			"report_type": "EXECUTIVE_AUDIT_REPORT",
			"report_id": f"EXEC-AUDIT-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
			"generated_at": generated_at,
			"project_id": project_id,
			"project_name": project_name,
			"prepared_by": prepared_by.strip() or "local-analyst",
			"reviewer_notes": reviewer_notes.strip(),
			"section_1_financial_kpis": overview.get("kpis", {}),
			"section_2_operations_funnel": {
				"funnel": overview.get("funnel", []),
				"queue_breakdown": overview.get("queue_breakdown", {}),
				"financial_trends": overview.get("financial_trends", []),
				"case_sla": overview.get("case_sla", {}),
			},
			"section_3_policy_and_model_effectiveness": {
				"attribution": effectiveness.get("attribution", {}),
				"rule_leaderboard": effectiveness.get("rule_leaderboard", []),
				"model_health": effectiveness.get("model_health", {}),
				"score_drift": effectiveness.get("score_drift", {}),
				"lift_gain_curve": effectiveness.get("lift_gain_curve", []),
				"model_comparison": effectiveness.get("model_comparison", []),
			},
			"section_4_typologies_and_patterns": {
				"typology_breakdown": patterns.get("typology_breakdown", []),
				"fp_reason_breakdown": patterns.get("fp_reason_breakdown", []),
				"peak_risk_hours": [
					h for h in patterns.get("hourly_distribution", []) if h.get("is_peak_risk")
				],
				"amount_brackets": patterns.get("amount_brackets", []),
				"segment_analytics": patterns.get("segment_analytics", {}),
			},
			"section_5_watchlist_and_governance": {
				"top_flagged_subjects": patterns.get("top_flagged_subjects", []),
				"watchlist_summary": patterns.get("watchlist_summary", {}),
			},
		}

	@staticmethod
	def format_sar_markdown(dossier: dict[str, Any]) -> str:
		"""Formats a SAR Dossier dictionary into a structured Markdown document."""
		s1 = dossier["section_1_identification"]
		s2 = dossier["section_2_financial_summary"]
		s3 = dossier["section_3_detection_evidence"]
		s4 = dossier["section_4_narrative_and_typology"]
		s5 = dossier["section_5_mitigation_and_audit"]

		lines = [
			f"# SUSPICIOUS ACTIVITY REPORT (SAR) — {s1['case_code']}",
			"",
			f"- **Report ID:** `{dossier['report_id']}`",
			f"- **Generated At (UTC):** `{dossier['generated_at']}`",
			f"- **Project:** {dossier['project_name']} (`{dossier['project_id']}`)",
			f"- **Prepared By:** `{dossier['prepared_by']}`",
			"",
			"---",
			"",
			"## Part I — Subject & Case Identification",
			f"- **Case ID:** `{s1['case_id']}`",
			f"- **Case Code:** `{s1['case_code']}`",
			f"- **Subject User ID:** `{s1['subject_user_id']}`",
			f"- **Priority / Risk Level:** `{s1['priority']}` (Score: `{s1['priority_score']}`)",
			f"- **Current Status / Verdict:** `{s1['status']}` (`{s1['verdict']}`)",
			f"- **Detected At:** `{s1['detected_at']}`",
			f"- **Resolved At:** `{s1['resolved_at'] or 'Pending'}`",
			f"- **Resolved Analyst:** `{s1['resolved_by']}`",
			"",
			"## Part II — Suspicious Activity & Financial Summary",
			f"- **Primary Event ID:** `{s2['primary_event_id']}`",
			f"- **Primary Transaction Amount:** `${s2['primary_amount']:,.2f}`",
			f"- **Total Subject Exposure:** `${s2['total_subject_exposure']:,.2f}` ({s2['subject_flagged_tx_count']} flagged transaction(s))",
			f"- **Confirmed Fraud Loss Prevented:** `${s2['confirmed_fraud_loss_prevented']:,.2f}`",
			f"- **Channel / Merchant / Country:** `{s2['channel']}` / `{s2['merchant_category']}` / `{s2['country']}`",
			"",
			"| Event ID | Timestamp (UTC) | Amount ($) | Action | Model Score | Case Status |",
			"| :--- | :--- | ---: | :--- | ---: | :--- |",
		]
		for tx in s2.get("transactions", []):
			ms = f"{tx['model_score']:.4f}" if tx.get("model_score") is not None else "—"
			lines.append(
				f"| `{tx['event_id']}` | `{tx['tx_timestamp']}` | ${tx['amount']:,.2f} | `{tx['final_action']}` | {ms} | `{tx['status']}` |"
			)

		lines.extend([
			"",
			"## Part III — Automated Detection Evidence (AI & Rules)",
			f"- **Model Version ID:** `{s3['model_version_id'] or 'Rule-Only'}`",
			f"- **AI Fraud Probability Score:** `{s3['model_score'] if s3['model_score'] is not None else 'N/A'}`",
			"",
			"### Violated Business Rules",
		])
		if s3.get("violated_rules"):
			for r in s3["violated_rules"]:
				lines.append(
					f"- **`{r['rule_code']}` ({r['rule_name']})** [v{r['version_number']} — `{r['action']}`]: `{r['trigger_reason']}`"
				)
		else:
			lines.append("- *No manual rule triggered (AI-Exclusive detection).*")

		lines.extend(["", "### Top SHAP Feature Contributions"])
		if s3.get("top_feature_contributions"):
			for f in s3["top_feature_contributions"]:
				lines.append(
					f"- `{f['feature_name']}` = `{f['feature_value']}` (SHAP: `{f['shap_value']:+.4f}`)"
				)
		else:
			lines.append("- *No SHAP feature contributions recorded.*")

		lines.extend([
			"",
			"## Part IV — Investigation Narrative & Fraud Typology",
			f"- **Fraud Typology:** `{s4['fraud_typology_code']}` ({s4['fraud_typology_label']})",
			f"- **Automated Technical Synthesis:** {s4['automated_technical_narrative']}",
			f"- **Official Analyst Conclusion:** {s4['analyst_resolution_summary']}",
		])
		if s4.get("reviewer_notes"):
			lines.append(f"- **Reviewer Notes:** {s4['reviewer_notes']}")

		lines.extend([
			"",
			"## Part V — Mitigation Actions & Immutable Audit Trail",
			f"- **Subject Blacklisted:** `{'YES (ACTIVE)' if s5['is_subject_blacklisted'] else 'NO'}`",
			"",
			"### Audit History",
			"| Timestamp (UTC) | Actor | Action | Note |",
			"| :--- | :--- | :--- | :--- |",
		])
		for log in s5.get("audit_trail", []):
			lines.append(
				f"| `{log['created_at']}` | `{log['actor']}` | `{log['action']}` | {log['note'] or '—'} |"
			)

		return "\n".join(lines) + "\n"

	@staticmethod
	def format_executive_markdown(report: dict[str, Any]) -> str:
		"""Formats an Executive Audit Report dictionary into Markdown."""
		kpis = report.get("section_1_financial_kpis", {})
		s2 = report.get("section_2_operations_funnel", {})
		case_sla = s2.get("case_sla", {})
		s3 = report.get("section_3_policy_and_model_effectiveness", {})
		attr = s3.get("attribution", {})
		rules = s3.get("rule_leaderboard", [])
		mh = s3.get("model_health", {})
		drift = s3.get("score_drift", {})
		s4 = report.get("section_4_typologies_and_patterns", {})
		s5 = report.get("section_5_watchlist_and_governance", {})

		prec_str = f"{kpis['verified_precision'] * 100:.1f}%" if kpis.get("verified_precision") is not None else "—"
		vdr_str = f"{kpis['value_detection_rate'] * 100:.1f}%" if kpis.get("value_detection_rate") is not None else "—"
		missed_str = f"${kpis['missed_fraud_amount']:,.2f} ({kpis.get('net_fraud_loss_bps', 0.0):.1f} bps)" if kpis.get("missed_fraud_amount") is not None else "—"
		insult_str = f"{kpis['customer_insult_rate'] * 100:.2f}%" if kpis.get("customer_insult_rate") is not None else "—"
		mttr_p50 = f"{case_sla['mttr_p50_hours']:.1f}h" if case_sla.get("mttr_p50_hours") is not None else "—"
		mttr_p90 = f"{case_sla['mttr_p90_hours']:.1f}h" if case_sla.get("mttr_p90_hours") is not None else "—"
		ks_str = f"{mh['ks_statistic']:.3f}" if mh.get("ks_statistic") is not None else "—"
		brier_str = f"{mh['brier_score']:.4f}" if mh.get("brier_score") is not None else "—"
		ece_str = f"{mh['ece']:.4f}" if mh.get("ece") is not None else "—"
		psi_str = f"{drift['psi']:.4f} ({drift.get('status', '')})" if drift.get("psi") is not None else "—"

		lines = [
			f"# EXECUTIVE FRAUD & POLICY AUDIT REPORT — {report['project_name']}",
			"",
			f"- **Report ID:** `{report['report_id']}`",
			f"- **Generated At (UTC):** `{report['generated_at']}`",
			f"- **Project ID:** `{report['project_id']}`",
			f"- **Prepared By:** `{report['prepared_by']}`",
			f"- **Ground-Truth Mode:** `{kpis.get('label_source', 'VERIFIED_WITH_DATASET_FALLBACK')}` (`{kpis.get('ground_truth_coverage', 'FULL')}`)",
			"",
			"---",
			"",
			"## 1. Executive Financial & Operational KPIs",
			f"- **Gross Scanned Volume:** `${kpis.get('gross_scanned_volume', 0.0):,.2f}` (`{kpis.get('gross_scanned_count', 0):,}` transactions)",
			f"- **Confirmed Fraud Prevented & VDR:** `${kpis.get('confirmed_fraud_loss_prevented', 0.0):,.2f}` (`{kpis.get('confirmed_fraud_count', 0):,}` cases · VDR: `{vdr_str}`)",
			f"- **Missed Fraud & Net Loss:** `{missed_str}`",
			f"- **Customer Insult Rate & Friction:** `{insult_str}` (`${kpis.get('false_positive_friction_volume', 0.0):,.2f}` — Hard Decline `${kpis.get('hard_false_decline_amount', 0.0):,.2f}` / Soft Review `${kpis.get('soft_review_friction_amount', 0.0):,.2f}`)",
			f"- **Verified Precision & Alert-to-Fraud Ratio:** `{prec_str}` (`{kpis.get('alert_to_fraud_label', '—')}`)",
			f"- **Case Resolution & SLA:** `{kpis.get('case_resolution_rate', 0.0) * 100:.1f}%` (`{kpis.get('resolved_cases', 0)}/{kpis.get('total_cases', 0)}` resolved · MTTR P50/P90: `{mttr_p50}` / `{mttr_p90}` · SLA Breach: `{case_sla.get('sla_breach_count', 0)}`)",
			"",
			"## 2. AI Model Health & Catch Attribution",
			f"- **Total Caught Fraud:** `{attr.get('total_caught_fraud_count', 0)}` cases (`${attr.get('total_caught_fraud_amount', 0.0):,.2f}`)",
			f"- **AI-Exclusive / Overlap / Rule-Exclusive:** `{attr.get('ai_exclusive_catch_rate', 0.0) * 100:.1f}%` / `{attr.get('consensus_overlap_rate', 0.0) * 100:.1f}%` / `{attr.get('rule_exclusive_catch_rate', 0.0) * 100:.1f}%`",
			f"- **Model Health:** KS `{ks_str}` · Brier `{brier_str}` · ECE `{ece_str}` · Score Drift (PSI) `{psi_str}`",
			"",
			"## 3. Rule Ground-Truth Leaderboard",
			"| Rule Code | Rule Name | Status | Action | Hits | Verified TP | Verified FP | FAR | Unique Catch ($) | Fraud Caught ($) | Health Tag |",
			"| :--- | :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |",
		]
		for r in rules:
			far_val = r.get("false_alert_rate", r.get("verified_fpr"))
			far_s = f"{far_val * 100:.1f}%" if far_val is not None else "—"
			small_tag = " [n<30]" if r.get("is_small_sample") else ""
			lines.append(
				f"| `{r['rule_code']}` | {r['rule_name']} | `{r['status']}` | `{r['action']}` | {r['total_hits']} | {r['verified_tp']} | {r['verified_fp']} | {far_s} | ${r.get('unique_catch_amount', 0.0):,.2f} ({r.get('unique_catch_count', 0)}) | ${r['fraud_value_caught']:,.2f} | `{r['policy_health_tag']}{small_tag}` |"
			)

		lines.extend([
			"",
			"## 4. Fraud Typologies & Amount Bracket Risk Profile",
			"| Amount Bracket | Total Tx | Flagged Tx | Alert Rate | Amount at Risk ($) | Confirmed Fraud ($) |",
			"| :--- | ---: | ---: | ---: | ---: | ---: |",
		])
		for b in s4.get("amount_brackets", []):
			lines.append(
				f"| {b['label']} | {b['total_count']} | {b['flagged_count']} | {b['flag_rate'] * 100:.1f}% | ${b['amount_at_risk']:,.2f} | ${b['confirmed_fraud_amount']:,.2f} |"
			)

		wl = s5.get("watchlist_summary", {})
		lines.extend([
			"",
			"## 5. Watchlist & Governance Summary",
			f"- **Active Blacklisted Entities:** `{wl.get('active_blacklist_count', 0)}` (Matched Tx: `{wl.get('matched_tx_count', 0)}`, Exposure: `${wl.get('matched_amount', 0.0):,.2f}`)",
			f"- **Removed Historical Entries:** `{wl.get('removed_blacklist_count', 0)}`",
		])
		if report.get("reviewer_notes"):
			lines.append(f"- **Reviewer Notes:** {report['reviewer_notes']}")

		return "\n".join(lines) + "\n"

	@staticmethod
	def _render_html_document(payload: dict[str, Any], is_sar: bool) -> str:
		"""Renders a structured, print-ready A4 HTML document with KPI cards and tables (SUC-25)."""
		esc = html.escape
		report_id = esc(str(payload.get("report_id") or "REPORT"))
		project_name = esc(str(payload.get("project_name") or ""))
		generated_at = esc(str(payload.get("generated_at") or ""))
		prepared_by = esc(str(payload.get("prepared_by") or ""))
		notes = esc(str(payload.get("reviewer_notes") or ""))

		css = """
			@page { size: A4; margin: 14mm; }
			body { font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 28px; color: #0f172a; line-height: 1.5; font-size: 13px; background: #ffffff; }
			.header { border-bottom: 2px solid #0f172a; padding-bottom: 12px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
			.eyebrow { font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #0284c7; }
			h1 { font-size: 20px; margin: 4px 0 6px; color: #0f172a; }
			h2 { font-size: 14px; text-transform: uppercase; letter-spacing: 0.04em; color: #1e293b; border-left: 3px solid #0284c7; padding-left: 8px; margin: 22px 0 10px; }
			.meta { font-size: 12px; color: #475569; }
			.kpi-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 12px 0 18px; }
			.kpi-card { border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px 12px; background: #f8fafc; }
			.kpi-label { font-size: 11px; text-transform: uppercase; color: #475569; font-weight: 600; }
			.kpi-value { font-size: 17px; font-weight: 700; font-family: 'JetBrains Mono', ui-monospace, monospace; margin-top: 4px; color: #0f172a; }
			.kpi-sub { font-size: 11px; color: #64748b; margin-top: 2px; }
			table { width: 100%; border-collapse: collapse; margin: 10px 0 16px; font-size: 12px; }
			th, td { border: 1px solid #cbd5e1; padding: 6px 8px; text-align: left; }
			th { background: #f1f5f9; font-weight: 600; color: #334155; font-size: 11px; text-transform: uppercase; }
			td.num, th.num { text-align: right; font-family: 'JetBrains Mono', ui-monospace, monospace; }
			.badge { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700; border: 1px solid #cbd5e1; background: #f1f5f9; }
			.narrative { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 12px; }
			@media print { body { margin: 0; } .no-print { display: none; } table { page-break-inside: auto; } tr { page-break-inside: avoid; } }
		"""

		if is_sar:
			s1 = payload["section_1_identification"]
			s2 = payload["section_2_financial_summary"]
			s3 = payload["section_3_detection_evidence"]
			s4 = payload["section_4_narrative_and_typology"]
			s5 = payload["section_5_mitigation_and_audit"]

			tx_rows = "".join(
				f"<tr><td>{esc(str(tx['event_id']))}</td><td>{esc(str(tx['tx_timestamp']))}</td>"
				f"<td class='num'>${tx['amount']:,.2f}</td><td>{esc(str(tx['final_action']))}</td>"
				f"<td class='num'>{('%0.4f' % tx['model_score']) if tx.get('model_score') is not None else '—'}</td>"
				f"<td>{esc(str(tx['status']))}</td></tr>"
				for tx in s2.get("transactions", [])
			) or "<tr><td colspan='6'>No linked transactions</td></tr>"

			rule_rows = "".join(
				f"<tr><td>{esc(r['rule_code'])}</td><td>{esc(r['rule_name'])}</td>"
				f"<td>{esc(r['action'])}</td><td>{esc(r['trigger_reason'])}</td></tr>"
				for r in s3.get("violated_rules", [])
			) or "<tr><td colspan='4'>No deterministic rules triggered (AI-Exclusive)</td></tr>"

			shap_rows = "".join(
				f"<tr><td>{esc(f['feature_name'])}</td><td>{esc(str(f['feature_value']))}</td>"
				f"<td class='num'>{f['shap_value']:+.4f}</td><td>{esc(f['direction'])}</td></tr>"
				for f in s3.get("top_feature_contributions", [])
			) or "<tr><td colspan='4'>No SHAP feature contributions recorded</td></tr>"

			audit_rows = "".join(
				f"<tr><td>{esc(log['created_at'])}</td><td>{esc(log['actor'])}</td>"
				f"<td>{esc(log['action'])}</td><td>{esc(log.get('note') or '—')}</td></tr>"
				for log in s5.get("audit_trail", [])
			) or "<tr><td colspan='4'>No audit records</td></tr>"

			body_html = f"""
			<div class="header">
				<div>
					<div class="eyebrow">Suspicious Activity Report (SAR Dossier) &bull; {report_id}</div>
					<h1>Hồ sơ Giao dịch Đáng ngờ &mdash; {esc(s1['case_code'])}</h1>
					<div class="meta">Dự án: <strong>{project_name}</strong> &bull; Người lập: <strong>{prepared_by}</strong> &bull; Khởi tạo (UTC): {generated_at}</div>
				</div>
				<span class="badge">{esc(s1['verdict'])}</span>
			</div>
			<div class="kpi-grid">
				<div class="kpi-card"><div class="kpi-label">Đối tượng (Subject)</div><div class="kpi-value">{esc(s1['subject_user_id'])}</div><div class="kpi-sub">Priority: {esc(s1['priority'])} ({s1['priority_score']})</div></div>
				<div class="kpi-card"><div class="kpi-label">Giá trị giao dịch chính</div><div class="kpi-value">${s2['primary_amount']:,.2f}</div><div class="kpi-sub">Action: {esc(s2['final_action'])} &bull; Event {esc(s2['primary_event_id'])}</div></div>
				<div class="kpi-card"><div class="kpi-label">Tổng phơi nhiễm</div><div class="kpi-value">${s2['total_subject_exposure']:,.2f}</div><div class="kpi-sub">Blacklist: {'ACTIVE' if s5.get('is_subject_blacklisted') else 'NO'}</div></div>
			</div>
			<h2>Phần I &amp; II — Giao dịch liên quan</h2>
			<table>
				<thead><tr><th>Event ID</th><th>Thời gian (UTC)</th><th class="num">Số tiền</th><th>Hành động</th><th class="num">AI Score</th><th>Trạng thái</th></tr></thead>
				<tbody>{tx_rows}</tbody>
			</table>
			<h2>Phần III — Bằng chứng phát hiện (Luật &amp; SHAP)</h2>
			<table>
				<thead><tr><th>Mã luật</th><th>Tên luật</th><th>Hành động</th><th>Điều kiện kích hoạt</th></tr></thead>
				<tbody>{rule_rows}</tbody>
			</table>
			<table>
				<thead><tr><th>Đặc trưng</th><th>Giá trị</th><th class="num">SHAP</th><th>Chiều tác động</th></tr></thead>
				<tbody>{shap_rows}</tbody>
			</table>
			<h2>Phần IV — Diễn giải &amp; Phân loại ({esc(s4['fraud_typology_label'])})</h2>
			<div class="narrative">
				<p>{esc(s4['automated_technical_narrative'])}</p>
				<p><strong>Kết luận chuyên viên:</strong> {esc(s4['analyst_resolution_summary'])}</p>
				{f"<p><strong>Ghi chú rà soát:</strong> {notes}</p>" if notes else ""}
			</div>
			<h2>Phần V — Nhật ký kiểm toán bất biến (Audit Trail)</h2>
			<table>
				<thead><tr><th>Thời gian (UTC)</th><th>Chuyên viên</th><th>Hành động</th><th>Ghi chú</th></tr></thead>
				<tbody>{audit_rows}</tbody>
			</table>
			"""
		else:
			kpis = payload.get("section_1_financial_kpis", {})
			s2 = payload.get("section_2_operations_funnel", {})
			case_sla = s2.get("case_sla", {})
			s3 = payload.get("section_3_policy_and_model_effectiveness", {})
			mh = s3.get("model_health", {})
			drift = s3.get("score_drift", {})
			s4 = payload.get("section_4_typologies_and_patterns", {})
			s5 = payload.get("section_5_watchlist_and_governance", {})
			wl = s5.get("watchlist_summary", {})

			vdr_str = f"{kpis['value_detection_rate'] * 100:.1f}%" if kpis.get("value_detection_rate") is not None else "—"
			missed_str = f"${kpis['missed_fraud_amount']:,.2f}" if kpis.get("missed_fraud_amount") is not None else "—"
			bps_str = f"{kpis['net_fraud_loss_bps']:.1f} bps" if kpis.get("net_fraud_loss_bps") is not None else "—"
			insult_str = f"{kpis['customer_insult_rate'] * 100:.2f}%" if kpis.get("customer_insult_rate") is not None else "—"
			prec_str = f"{kpis['verified_precision'] * 100:.1f}%" if kpis.get("verified_precision") is not None else "—"
			mttr_str = f"{case_sla['mttr_p50_hours']:.1f}h / {case_sla['mttr_p90_hours']:.1f}h" if case_sla.get("mttr_p50_hours") is not None else "—"
			ks_str = f"{mh['ks_statistic']:.3f}" if mh.get("ks_statistic") is not None else "—"
			brier_str = f"{mh['brier_score']:.4f}" if mh.get("brier_score") is not None else "—"
			ece_str = f"{mh['ece']:.4f}" if mh.get("ece") is not None else "—"
			psi_str = f"{drift['psi']:.4f} ({esc(str(drift.get('status', '')))})" if drift.get("psi") is not None else "—"

			funnel_rows = "".join(
				f"<tr><td>{esc(str(f['label']))}</td><td class='num'>{f['tx_count']:,}</td>"
				f"<td class='num'>${f['amount']:,.2f}</td><td class='num'>{f['conversion_rate'] * 100:.1f}%</td></tr>"
				for f in s2.get("funnel", [])
			)
			rule_rows = "".join(
				f"<tr><td>{esc(r['rule_code'])}</td><td>{esc(r['rule_name'])}</td><td>{esc(r['action'])}</td>"
				f"<td class='num'>{r['total_hits']}</td><td class='num'>{r['verified_tp']} / {r['verified_fp']}</td>"
				f"<td class='num'>{('%0.1f%%' % (r['false_alert_rate'] * 100)) if r.get('false_alert_rate') is not None else '—'}</td>"
				f"<td class='num'>${r.get('unique_catch_amount', 0.0):,.2f} ({r.get('unique_catch_count', 0)})</td>"
				f"<td class='num'>${r['fraud_value_caught']:,.2f}</td>"
				f"<td><span class='badge'>{esc(r['policy_health_tag'])}{' [n&lt;30]' if r.get('is_small_sample') else ''}</span></td></tr>"
				for r in s3.get("rule_leaderboard", [])
			) or "<tr><td colspan='9'>Chưa ghi nhận luật kích hoạt</td></tr>"

			bracket_rows = "".join(
				f"<tr><td>{esc(b['label'])}</td><td class='num'>{b['total_count']:,}</td>"
				f"<td class='num'>{b['flagged_count']:,}</td><td class='num'>{b['flag_rate'] * 100:.1f}%</td>"
				f"<td class='num'>${b['amount_at_risk']:,.2f}</td><td class='num'>${b['confirmed_fraud_amount']:,.2f}</td></tr>"
				for b in s4.get("amount_brackets", [])
			)

			body_html = f"""
			<div class="header">
				<div>
					<div class="eyebrow">Executive Fraud &amp; Policy Audit Report &bull; {report_id}</div>
					<h1>Báo cáo Kiểm toán Gian lận &amp; Chính sách &mdash; {project_name}</h1>
					<div class="meta">Người lập: <strong>{prepared_by}</strong> &bull; Khởi tạo (UTC): {generated_at} &bull; Chế độ nhãn: {esc(str(kpis.get('label_source', '')))}</div>
				</div>
				<span class="badge">{esc(str(kpis.get('ground_truth_coverage', 'FULL')))}</span>
			</div>
			<h2>1. Chỉ số Điều hành &amp; Tài chính (VDR, Missed Fraud, Insult Rate, SLA)</h2>
			<div class="kpi-grid">
				<div class="kpi-card"><div class="kpi-label">Tổng khối lượng quét</div><div class="kpi-value">${kpis.get('gross_scanned_volume', 0.0):,.2f}</div><div class="kpi-sub">{kpis.get('gross_scanned_count', 0):,} giao dịch</div></div>
				<div class="kpi-card"><div class="kpi-label">Gian lận ngăn chặn (VDR)</div><div class="kpi-value">${kpis.get('confirmed_fraud_loss_prevented', 0.0):,.2f} ({vdr_str})</div><div class="kpi-sub">{kpis.get('confirmed_fraud_count', 0):,} ca gian lận</div></div>
				<div class="kpi-card"><div class="kpi-label">Gian lận lọt lưới (Missed Fraud)</div><div class="kpi-value">{missed_str}</div><div class="kpi-sub">Net Fraud Loss: {bps_str}</div></div>
				<div class="kpi-card"><div class="kpi-label">Customer Insult Rate</div><div class="kpi-value">{insult_str}</div><div class="kpi-sub">Hard Decline: ${kpis.get('hard_false_decline_amount', 0.0):,.2f} &bull; Soft Review: ${kpis.get('soft_review_friction_amount', 0.0):,.2f}</div></div>
				<div class="kpi-card"><div class="kpi-label">Precision &amp; Alert:Fraud</div><div class="kpi-value">{prec_str}</div><div class="kpi-sub">Ratio: {esc(str(kpis.get('alert_to_fraud_label', '—')))}</div></div>
				<div class="kpi-card"><div class="kpi-label">Vận hành SLA &amp; MTTR</div><div class="kpi-value">{kpis.get('case_resolution_rate', 0.0) * 100:.1f}%</div><div class="kpi-sub">MTTR P50/P90: {mttr_str} &bull; Quá SLA: {case_sla.get('sla_breach_count', 0)}</div></div>
			</div>
			<h2>2. Phễu Chuyển đổi 4 Tầng</h2>
			<table>
				<thead><tr><th>Giai đoạn</th><th class="num">Số GD</th><th class="num">Giá trị ($)</th><th class="num">Tỷ lệ / Tổng quét</th></tr></thead>
				<tbody>{funnel_rows}</tbody>
			</table>
			<h2>3. Sức khỏe Mô hình AI (KS / Brier / ECE / PSI) &amp; Hiệu quả Tập luật</h2>
			<div class="kpi-grid">
				<div class="kpi-card"><div class="kpi-label">KS Statistic</div><div class="kpi-value">{ks_str}</div></div>
				<div class="kpi-card"><div class="kpi-label">Brier Score / ECE</div><div class="kpi-value">{brier_str} / {ece_str}</div></div>
				<div class="kpi-card"><div class="kpi-label">Score Drift (PSI)</div><div class="kpi-value">{psi_str}</div></div>
			</div>
			<table>
				<thead><tr><th>Mã luật</th><th>Tên luật</th><th>Action</th><th class="num">Hits</th><th class="num">TP / FP</th><th class="num">FAR</th><th class="num">Unique Catch</th><th class="num">Ngăn chặn ($)</th><th>Trạng thái</th></tr></thead>
				<tbody>{rule_rows}</tbody>
			</table>
			<h2>4. Phân khúc Theo Khoảng Số tiền &amp; Danh sách đen</h2>
			<table>
				<thead><tr><th>Khoảng tiền</th><th class="num">Tổng GD</th><th class="num">Bị gắn cờ</th><th class="num">Alert Rate</th><th class="num">Rủi ro ($)</th><th class="num">Ngăn chặn ($)</th></tr></thead>
				<tbody>{bracket_rows}</tbody>
			</table>
			<div class="narrative">
				<strong>Danh sách theo dõi (Watchlist):</strong> {wl.get('active_blacklist_count', 0)} thực thể đang chặn &bull;
				{wl.get('matched_tx_count', 0)} giao dịch liên quan (${wl.get('matched_amount', 0.0):,.2f}).
				{f"<br/><strong>Ghi chú rà soát:</strong> {notes}" if notes else ""}
			</div>
			"""

		return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8" />
<title>{report_id}</title>
<style>{css}</style>
</head>
<body>
{body_html}
</body>
</html>"""

	@staticmethod
	def format_report_export(
		payload: dict[str, Any],
		file_format: str = "md",
	) -> tuple[bytes, str, str]:
		"""Serializes a SAR Dossier or Executive Audit Report into (bytes, filename, media_type)."""
		fmt = file_format.strip().lower()
		report_id = str(payload.get("report_id") or "report").replace(" ", "_")
		is_sar = payload.get("report_type") == "SAR_DOSSIER"

		if fmt == "json":
			content = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
			return content, f"{report_id}.json", "application/json"

		if fmt == "csv":
			buf = io.StringIO()
			writer = csv.writer(buf)
			if is_sar:
				s1 = payload["section_1_identification"]
				s2 = payload["section_2_financial_summary"]
				s4 = payload["section_4_narrative_and_typology"]
				writer.writerow([
					"report_id", "generated_at", "case_id", "case_code", "subject_user_id",
					"status", "verdict", "priority", "event_id", "tx_timestamp", "amount",
					"final_action", "fraud_typology_code", "analyst_resolution_summary",
				])
				for tx in s2.get("transactions", []):
					writer.writerow([
						payload["report_id"],
						payload["generated_at"],
						s1["case_id"],
						s1["case_code"],
						s1["subject_user_id"],
						s1["status"],
						s1["verdict"],
						s1["priority"],
						tx["event_id"],
						tx["tx_timestamp"],
						tx["amount"],
						tx["final_action"],
						s4["fraud_typology_code"],
						s4["analyst_resolution_summary"],
					])
			else:
				writer.writerow([
					"rule_code", "rule_name", "status", "action", "total_hits",
					"verified_cases", "verified_tp", "verified_fp", "false_alert_rate",
					"unique_catch_count", "unique_catch_amount", "fraud_value_caught",
					"is_small_sample", "policy_health_tag",
				])
				for r in payload.get("section_3_policy_and_model_effectiveness", {}).get("rule_leaderboard", []):
					writer.writerow([
						r["rule_code"],
						r["rule_name"],
						r["status"],
						r["action"],
						r["total_hits"],
						r["verified_cases"],
						r["verified_tp"],
						r["verified_fp"],
						r.get("false_alert_rate", r.get("verified_fpr")),
						r.get("unique_catch_count", 0),
						r.get("unique_catch_amount", 0.0),
						r["fraud_value_caught"],
						r.get("is_small_sample", False),
						r["policy_health_tag"],
					])
			return buf.getvalue().encode("utf-8"), f"{report_id}.csv", "text/csv; charset=utf-8"

		if fmt == "html":
			html_doc = ComplianceReportBuilder._render_html_document(payload, is_sar=is_sar)
			return html_doc.encode("utf-8"), f"{report_id}.html", "text/html; charset=utf-8"

		md_text = (
			ComplianceReportBuilder.format_sar_markdown(payload)
			if is_sar
			else ComplianceReportBuilder.format_executive_markdown(payload)
		)
		return md_text.encode("utf-8"), f"{report_id}.md", "text/markdown; charset=utf-8"
