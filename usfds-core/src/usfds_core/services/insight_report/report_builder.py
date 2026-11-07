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
				"assigned_to": case.assigned_to or "Unassigned",
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
			},
			"section_3_policy_and_model_effectiveness": {
				"attribution": effectiveness.get("attribution", {}),
				"rule_leaderboard": effectiveness.get("rule_leaderboard", []),
			},
			"section_4_typologies_and_patterns": {
				"typology_breakdown": patterns.get("typology_breakdown", []),
				"fp_reason_breakdown": patterns.get("fp_reason_breakdown", []),
				"peak_risk_hours": [
					h for h in patterns.get("hourly_distribution", []) if h.get("is_peak_risk")
				],
				"amount_brackets": patterns.get("amount_brackets", []),
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
			f"- **Assigned / Resolved Analyst:** `{s1['assigned_to']}` / `{s1['resolved_by']}`",
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
		s3 = report.get("section_3_policy_and_model_effectiveness", {})
		attr = s3.get("attribution", {})
		rules = s3.get("rule_leaderboard", [])
		s4 = report.get("section_4_typologies_and_patterns", {})
		s5 = report.get("section_5_watchlist_and_governance", {})

		prec_str = (
			f"{kpis.get('verified_precision', 0) * 100:.1f}%"
			if kpis.get("verified_precision") is not None
			else "—"
		)

		lines = [
			f"# EXECUTIVE FRAUD & POLICY AUDIT REPORT — {report['project_name']}",
			"",
			f"- **Report ID:** `{report['report_id']}`",
			f"- **Generated At (UTC):** `{report['generated_at']}`",
			f"- **Project ID:** `{report['project_id']}`",
			f"- **Prepared By:** `{report['prepared_by']}`",
			f"- **Ground-Truth Mode:** `{kpis.get('label_source', 'VERIFIED_WITH_DATASET_FALLBACK')}`",
			"",
			"---",
			"",
			"## 1. Executive Financial & Operational KPIs",
			f"- **Gross Scanned Volume:** `${kpis.get('gross_scanned_volume', 0.0):,.2f}` (`{kpis.get('gross_scanned_count', 0):,}` transactions)",
			f"- **Total Exposure / Amount at Risk:** `${kpis.get('amount_at_risk', 0.0):,.2f}` (`{kpis.get('flagged_tx_count', 0):,}` flagged)",
			f"- **Confirmed Fraud Loss Prevented (ROI):** `${kpis.get('confirmed_fraud_loss_prevented', 0.0):,.2f}` (`{kpis.get('confirmed_fraud_count', 0):,}` cases)",
			f"- **False Positive Friction Volume:** `${kpis.get('false_positive_friction_volume', 0.0):,.2f}` (Insult Rate: `{kpis.get('insult_rate', 0.0) * 100:.2f}%`)",
			f"- **Verified Precision & Alert-to-Fraud Ratio:** `{prec_str}` (`{kpis.get('alert_to_fraud_label', '—')}`)",
			f"- **Case Resolution SLA:** `{kpis.get('case_resolution_rate', 0.0) * 100:.1f}%` (`{kpis.get('resolved_cases', 0)}/{kpis.get('total_cases', 0)}` resolved, `{kpis.get('critical_high_backlog', 0)}` Critical/High backlog)",
			"",
			"## 2. AI vs. Rule Catch Attribution",
			f"- **Total Caught Fraud:** `{attr.get('total_caught_fraud_count', 0)}` cases (`${attr.get('total_caught_fraud_amount', 0.0):,.2f}`)",
			f"- **AI-Exclusive Catch Rate:** `{attr.get('ai_exclusive_catch_rate', 0.0) * 100:.1f}%`",
			f"- **Consensus / Overlap Rate:** `{attr.get('consensus_overlap_rate', 0.0) * 100:.1f}%`",
			f"- **Rule-Exclusive Catch Rate:** `{attr.get('rule_exclusive_catch_rate', 0.0) * 100:.1f}%`",
			"",
			"## 3. Rule Ground-Truth Leaderboard",
			"| Rule Code | Rule Name | Status | Action | Hits | Verified TP | Verified FP | Verified FPR | Fraud Caught ($) | Health Tag |",
			"| :--- | :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | :--- |",
		]
		for r in rules:
			fpr_s = f"{r['verified_fpr'] * 100:.1f}%" if r.get("verified_fpr") is not None else "—"
			lines.append(
				f"| `{r['rule_code']}` | {r['rule_name']} | `{r['status']}` | `{r['action']}` | {r['total_hits']} | {r['verified_tp']} | {r['verified_fp']} | {fpr_s} | ${r['fraud_value_caught']:,.2f} | `{r['policy_health_tag']}` |"
			)

		lines.extend([
			"",
			"## 4. Fraud Typologies & Amount Bracket Risk Profile",
			"| Amount Bracket | Total Tx | Flagged Tx | Flag Rate | Amount at Risk ($) | Confirmed Fraud ($) |",
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
			f"- **Active Blacklisted Entities:** `{wl.get('active_blacklist_count', 0)}`",
			f"- **Removed Historical Entries:** `{wl.get('removed_blacklist_count', 0)}`",
		])
		if report.get("reviewer_notes"):
			lines.append(f"- **Reviewer Notes:** {report['reviewer_notes']}")

		return "\n".join(lines) + "\n"

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
					"verified_cases", "verified_tp", "verified_fp", "verified_fpr",
					"fraud_value_caught", "policy_health_tag",
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
						r["verified_fpr"],
						r["fraud_value_caught"],
						r["policy_health_tag"],
					])
			return buf.getvalue().encode("utf-8"), f"{report_id}.csv", "text/csv; charset=utf-8"

		md_text = (
			ComplianceReportBuilder.format_sar_markdown(payload)
			if is_sar
			else ComplianceReportBuilder.format_executive_markdown(payload)
		)

		if fmt == "html":
			escaped_md = html.escape(md_text)
			html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{html.escape(report_id)}</title>
<style>
	body {{ font-family: Inter, -apple-system, BlinkMacSystemFont, sans-serif; margin: 32px; color: #0f172a; line-height: 1.5; }}
	pre {{ white-space: pre-wrap; font-family: 'JetBrains Mono', monospace; font-size: 12px; background: #f8fafc; padding: 20px; border: 1px solid #cbd5e1; border-radius: 8px; }}
</style>
</head>
<body>
<pre>{escaped_md}</pre>
</body>
</html>"""
			return html_doc.encode("utf-8"), f"{report_id}.html", "text/html; charset=utf-8"

		return md_text.encode("utf-8"), f"{report_id}.md", "text/markdown; charset=utf-8"
