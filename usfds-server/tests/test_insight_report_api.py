from datetime import datetime, timezone
import json
from uuid import uuid4

from fastapi.testclient import TestClient
import pandas as pd

from usfds_core.domain.entities.detection import DetectionJob
from usfds_core.domain.entities.enums import DetectionJobStatus
from usfds_core.domain.entities.system import Project
from usfds_infra.database import SqliteDetectionJobRepository, SqliteProjectRepository
from usfds_server.api import app
from usfds_server.config import settings
from usfds_server.dependencies import get_db, get_storage
from usfds_server.routers.investigation_router import ingest_request
from usfds_server.schemas.investigation_api_schemas import CaseIntakeRequest


def test_insight_report_api_endpoints_and_exports(tmp_path):
	old_db, old_storage = settings.db_path, settings.storage_dir
	settings.db_path, settings.storage_dir = str(tmp_path / "reports.db"), str(tmp_path / "storage")
	try:
		with TestClient(app) as client:
			from usfds_infra.database import SqlUserRepository

			project_id, job_id = uuid4(), uuid4()
			session_gen = get_db()
			session = next(session_gen)
			actor_id = SqlUserRepository(session).get_by_username("admin").user_id
			SqliteProjectRepository(session).save(
				Project(project_id=project_id, user_id=actor_id, project_name="Insight Audit Project")
			)

			pred_df = pd.DataFrame([
				{
					"event_id": "EV-1", "user_id": "U-100", "timestamp": "2026-11-02T01:30:00Z",
					"amount": 1500.0, "model_score": 0.94, "rule_action": "REJECT", "final_action": "REJECT",
					"is_flagged": 1, "triggered_rules": json.dumps(["R_ATO"]), "label": 1,
				},
				{
					"event_id": "EV-2", "user_id": "U-200", "timestamp": "2026-11-02T14:00:00Z",
					"amount": 80.0, "model_score": 0.62, "rule_action": "ALLOW", "final_action": "REVIEW",
					"is_flagged": 1, "triggered_rules": "[]", "label": 0,
				},
				{
					"event_id": "EV-3", "user_id": "U-300", "timestamp": "2026-11-02T16:00:00Z",
					"amount": 25.0, "model_score": 0.05, "rule_action": "ALLOW", "final_action": "ALLOW",
					"is_flagged": 0, "triggered_rules": "[]", "label": 0,
				},
			])
			output_rel = f"datasets/{project_id}/inferences/{job_id}/predictions.parquet"
			get_storage().save_bytes(output_rel, pred_df.to_parquet(index=False))

			SqliteDetectionJobRepository(session).save(
				DetectionJob(
					job_id=job_id,
					project_id=project_id,
					user_id=actor_id,
					job_name="Audit Scan #1",
					output_path=output_rel,
					score_threshold=0.5,
					status=DetectionJobStatus.COMPLETED,
					total_records=3,
					fraud_records=2,
					created_at=datetime(2026, 11, 2, 2, 0, tzinfo=timezone.utc),
				)
			)
			session.commit()
			session_gen.close()

			# Dispatch EV-1 and EV-2 into Investigation and resolve EV-1 as Confirmed Fraud
			intake_gen = get_db()
			intake_session = next(intake_gen)
			intake_res = ingest_request(
				CaseIntakeRequest.model_validate({
					"project_id": str(project_id),
					"detection_job_id": str(job_id),
					"transactions": [
						{
							"event_id": "EV-1", "user_id": "U-100", "timestamp": "2026-11-02T01:30:00Z",
							"amount": 1500.0, "model_score": 0.94, "final_action": "REJECT",
							"triggered_rules": [{"rule_id": str(uuid4()), "rule_version_id": str(uuid4()), "rule_code": "R_ATO", "rule_name": "ATO Rule", "version_number": 1, "action": "REJECT", "trigger_reason": "amount >= 1000"}],
						},
						{
							"event_id": "EV-2", "user_id": "U-200", "timestamp": "2026-11-02T14:00:00Z",
							"amount": 80.0, "model_score": 0.62, "final_action": "REVIEW",
						},
					],
				}),
				intake_session,
				get_storage(),
				"local-analyst",
			)
			intake_session.commit()
			intake_gen.close()

			case_1_id = intake_res["created_case_ids"][0]
			resolve_res = client.post(
				f"/api/v1/cases/{case_1_id}/resolve",
				params={"project_id": str(project_id)},
				json={
					"expected_version": 1,
					"verdict": "FRAUD",
					"reason": "ACCOUNT_TAKEOVER",
					"summary": "Confirmed account takeover via credential stuffing",
					"block_entities": [{"entity_type": "USER_ID", "entity_value": "U-100"}],
				},
			)
			assert resolve_res.status_code == 200, resolve_res.text

			# 1. GET /api/v1/reports/overview
			ov = client.get("/api/v1/reports/overview", params={"project_id": str(project_id)})
			assert ov.status_code == 200, ov.text
			ov_data = ov.json()["data"]
			assert ov_data["kpis"]["gross_scanned_volume"] == 1605.0
			assert ov_data["kpis"]["confirmed_fraud_loss_prevented"] == 1500.0
			assert ov_data["kpis"]["false_positive_friction_volume"] == 80.0  # EV-2 via dataset fallback

			# 2. GET /api/v1/reports/effectiveness
			eff = client.get("/api/v1/reports/effectiveness", params={"project_id": str(project_id)})
			assert eff.status_code == 200, eff.text
			eff_data = eff.json()["data"]
			assert eff_data["attribution"]["total_caught_fraud_count"] == 1
			assert eff_data["rule_leaderboard"][0]["rule_code"] == "R_ATO"

			# 3. GET /api/v1/reports/patterns
			pat = client.get("/api/v1/reports/patterns", params={"project_id": str(project_id)})
			assert pat.status_code == 200, pat.text
			pat_data = pat.json()["data"]
			assert pat_data["watchlist_summary"]["active_blacklist_count"] == 1
			assert len(pat_data["hourly_distribution"]) == 24

			# 4. GET /api/v1/reports/sar/{case_id}
			sar = client.get(
				f"/api/v1/reports/sar/{case_1_id}",
				params={"project_id": str(project_id), "prepared_by": "Compliance Lead"},
			)
			assert sar.status_code == 200, sar.text
			sar_data = sar.json()["data"]
			assert sar_data["section_1_identification"]["subject_user_id"] == "U-100"
			assert sar_data["section_5_mitigation_and_audit"]["is_subject_blacklisted"] is True
			assert "SUSPICIOUS ACTIVITY REPORT" in sar_data["markdown_preview"]

			# 5. GET /api/v1/reports/executive-summary & /api/v1/reports/export
			exec_rep = client.get("/api/v1/reports/executive-summary", params={"project_id": str(project_id)})
			assert exec_rep.status_code == 200
			assert "EXECUTIVE FRAUD & POLICY AUDIT REPORT" in exec_rep.json()["data"]["markdown_preview"]

			dl_md = client.get(
				"/api/v1/reports/export",
				params={"project_id": str(project_id), "report_type": "sar", "file_format": "md", "case_id": case_1_id},
			)
			assert dl_md.status_code == 200
			assert "attachment; filename=" in dl_md.headers.get("content-disposition", "")
	finally:
		settings.db_path, settings.storage_dir = old_db, old_storage


def _seed_report_job(project_name: str) -> str:
	"""Project + completed DetectionJob with 3 scanned transactions, via the running app's DB/storage."""
	from usfds_infra.database import SqlUserRepository
	from usfds_server import dependencies

	project_id, job_id = uuid4(), uuid4()
	session = dependencies._session_factory()
	actor_id = SqlUserRepository(session).get_by_username("admin").user_id
	SqliteProjectRepository(session).save(Project(project_id=project_id, user_id=actor_id, project_name=project_name))
	pred_df = pd.DataFrame([
		{"event_id": "EV-1", "user_id": "U-1", "timestamp": "2026-11-02T01:30:00Z", "amount": 1500.0, "model_score": 0.94,
		 "rule_action": "REJECT", "final_action": "REJECT", "is_flagged": 1, "triggered_rules": json.dumps(["R_ATO"]), "label": 1},
		{"event_id": "EV-2", "user_id": "U-2", "timestamp": "2026-11-02T14:00:00Z", "amount": 80.0, "model_score": 0.62,
		 "rule_action": "ALLOW", "final_action": "REVIEW", "is_flagged": 1, "triggered_rules": "[]", "label": 0},
		{"event_id": "EV-3", "user_id": "U-3", "timestamp": "2026-11-02T16:00:00Z", "amount": 25.0, "model_score": 0.05,
		 "rule_action": "ALLOW", "final_action": "ALLOW", "is_flagged": 0, "triggered_rules": "[]", "label": 0},
	])
	output_rel = f"datasets/{project_id}/inferences/{job_id}/predictions.parquet"
	dependencies.get_storage().save_bytes(output_rel, pred_df.to_parquet(index=False))
	SqliteDetectionJobRepository(session).save(DetectionJob(
		job_id=job_id, project_id=project_id, user_id=actor_id, job_name="Queue Scan", output_path=output_rel,
		score_threshold=0.5, status=DetectionJobStatus.COMPLETED, total_records=3, fraud_records=2,
		created_at=datetime(2026, 11, 2, 2, 0, tzinfo=timezone.utc),
	))
	session.commit()
	session.close()
	return str(project_id)


def test_insight_report_runs_on_analytics_worker_queue_in_queue_mode(client_queue_mode):
	from usfds_infra.job_queue import JOB_INSIGHT_REPORT, QUEUE_ANALYTICS

	project_id = _seed_report_job("Queue Insight")
	params = {"project_id": project_id}

	ov = client_queue_mode.get("/api/v1/reports/overview", params=params)
	assert ov.status_code == 200, ov.text
	assert ov.json()["data"]["kpis"]["gross_scanned_volume"] == 1605.0
	eff = client_queue_mode.get("/api/v1/reports/effectiveness", params=params)
	assert eff.status_code == 200, eff.text
	assert eff.json()["data"]["rule_leaderboard"][0]["rule_code"] == "R_ATO"
	pat = client_queue_mode.get("/api/v1/reports/patterns", params=params)
	assert pat.status_code == 200, pat.text
	assert len(pat.json()["data"]["hourly_distribution"]) == 24
	summary = client_queue_mode.get("/api/v1/reports/executive-summary", params=params)
	assert summary.status_code == 200, summary.text
	export = client_queue_mode.get("/api/v1/reports/export", params={**params, "report_type": "executive", "file_format": "csv"})
	assert export.status_code == 200, export.text
	assert b"R_ATO" in export.content and "attachment" in export.headers["content-disposition"]

	jobs = client_queue_mode.job_queue.jobs
	assert [(j["queue"], j["name"], j["state"]) for j in jobs] == [(QUEUE_ANALYTICS, JOB_INSIGHT_REPORT, "completed")] * 5
	assert {j["attempts"] for j in jobs} == {3}  # analytics jobs retry transient failures (ISS-021)
	assert {j["timeout_seconds"] for j in jobs} == {120.0}


def test_insight_report_queue_mode_maps_worker_lookup_error_to_404(client_queue_mode):
	res = client_queue_mode.get("/api/v1/reports/overview", params={"project_id": str(uuid4())})

	assert res.status_code == 404, res.text
	assert client_queue_mode.job_queue.jobs[-1]["failed_reason"].startswith("LookupError:")


def test_api_reports_return_upgraded_payload_and_model_labels(tmp_path):
	"""SUC-22..25, BR-IR-01, ISS-046: API returns new OLAP keys, resolved model labels, structured HTML, and enforces project isolation."""
	old_db, old_storage = settings.db_path, settings.storage_dir
	settings.db_path, settings.storage_dir = str(tmp_path / "upgraded_reports.db"), str(tmp_path / "storage")
	try:
		with TestClient(app) as client:
			from usfds_core.domain.entities.case import Case, CaseStatus
			from usfds_core.domain.entities.enums import RiskLevel, RuleAction
			from usfds_core.domain.entities.model import Model, ModelVersion
			from usfds_infra.database import (
				SqliteModelRepository,
				SqliteModelVersionRepository,
				SqlUserRepository,
			)
			from usfds_infra.database.case_repositories import SqliteCaseRepository

			project_id, other_project_id, job_id = uuid4(), uuid4(), uuid4()
			session_gen = get_db()
			session = next(session_gen)
			actor_id = SqlUserRepository(session).get_by_username("admin").user_id
			SqliteProjectRepository(session).save(
				Project(project_id=project_id, user_id=actor_id, project_name="FDS Upgraded API")
			)
			SqliteProjectRepository(session).save(
				Project(project_id=other_project_id, user_id=actor_id, project_name="Isolated Other Project")
			)

			model = Model(model_name="fraud_gbdt", display_name="FraudNet GBDT", user_id=actor_id, project_id=project_id)
			SqliteModelRepository(session).save(model)
			mv = ModelVersion(
				model_id=model.model_id,
				semver="1.2.0",
				artifact_uri="models/fraudnet.bin",
				project_id=project_id,
				user_id=actor_id,
			)
			SqliteModelVersionRepository(session).save(mv)

			rows = []
			for i in range(24):
				is_fraud = 1 if i < 6 else 0
				score = 0.90 if is_fraud else round(0.05 + (i % 4) * 0.05, 2)
				action = "REJECT" if is_fraud and i < 3 else ("REVIEW" if is_fraud and i < 5 else "ALLOW")
				rows.append({
					"event_id": f"API-EV-{i}",
					"user_id": f"U-API-{i % 5}",
					"timestamp": f"2026-11-{1 + (i // 12):02d}T{i % 24:02d}:00:00Z",
					"amount": 500.0 if is_fraud else 50.0,
					"model_score": score,
					"rule_action": "REJECT" if i == 0 else "ALLOW",
					"final_action": action,
					"is_flagged": 1 if action != "ALLOW" else 0,
					"triggered_rules": json.dumps(["R_VEL"]) if i == 0 else "[]",
					"label": is_fraud,
					"merchant_category": "RETAIL" if i % 2 == 0 else "TRAVEL",
					"device_id": f"DEV-{i % 3}",
				})
			output_rel = f"datasets/{project_id}/inferences/{job_id}/predictions.parquet"
			get_storage().save_bytes(output_rel, pd.DataFrame(rows).to_parquet(index=False))

			SqliteDetectionJobRepository(session).save(DetectionJob(
				job_id=job_id,
				project_id=project_id,
				user_id=actor_id,
				model_version_id=mv.version_id,
				job_name="Upgraded Scan",
				output_path=output_rel,
				score_threshold=0.5,
				status=DetectionJobStatus.COMPLETED,
				total_records=24,
				fraud_records=5,
				created_at=datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc),
			))
			SqliteCaseRepository(session).save(Case(
				project_id=project_id,
				event_id="API-EV-0",
				user_id="U-API-0",
				tx_timestamp=datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc),
				amount=500.0,
				final_action=RuleAction.REJECT,
				dataset_artifact_id=None,
				detection_job_id=job_id,
				model_version_id=mv.version_id,
				case_code="CASE-API-1",
				model_score=0.90,
				status=CaseStatus.RESOLVED_FRAUD,
				priority=RiskLevel.CRITICAL,
				resolution_reason="VELOCITY_ATTACK",
				resolution_summary="Verified",
				created_at=datetime(2026, 11, 1, 1, 0, tzinfo=timezone.utc),
				resolved_at=datetime(2026, 11, 1, 3, 0, tzinfo=timezone.utc),
				resolved_by="analyst_api",
			))
			session.commit()
			session_gen.close()

			params = {"project_id": str(project_id)}
			ov = client.get("/api/v1/reports/overview", params=params)
			assert ov.status_code == 200, ov.text
			ov_data = ov.json()["data"]
			assert "case_sla" in ov_data
			assert ov_data["kpis"]["value_detection_rate"] is not None
			assert ov_data["kpis"]["missed_fraud_amount"] == 500.0

			eff = client.get("/api/v1/reports/effectiveness", params=params)
			assert eff.status_code == 200, eff.text
			eff_data = eff.json()["data"]
			assert "score_drift" in eff_data
			assert "lift_gain_curve" in eff_data
			assert "model_health" in eff_data
			assert len(eff_data["model_comparison"]) == 1
			assert eff_data["model_comparison"][0]["model_name"] == "FraudNet GBDT"
			assert eff_data["model_comparison"][0]["display_label"] == "FraudNet GBDT v1.2.0"

			pat = client.get("/api/v1/reports/patterns", params=params)
			assert pat.status_code == 200, pat.text
			pat_data = pat.json()["data"]
			assert pat_data["segment_analytics"]["merchant_category"]["available"] is True
			assert pat_data["segment_analytics"]["device_id"]["available"] is True

			summary = client.get("/api/v1/reports/executive-summary", params=params)
			assert summary.status_code == 200, summary.text
			assert "case_sla" in summary.json()["data"]["section_2_operations_funnel"]

			exp_html = client.get(
				"/api/v1/reports/export",
				params={**params, "report_type": "executive", "file_format": "html"},
			)
			assert exp_html.status_code == 200, exp_html.text
			assert "<table" in exp_html.text and "@media print" in exp_html.text

			# BR-IR-01 cross-project isolation: other project sees 0 transactions
			other_ov = client.get("/api/v1/reports/overview", params={"project_id": str(other_project_id)})
			assert other_ov.status_code == 200
			assert other_ov.json()["data"]["kpis"]["gross_scanned_count"] == 0
	finally:
		settings.db_path, settings.storage_dir = old_db, old_storage

