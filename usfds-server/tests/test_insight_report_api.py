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
			project_id, actor_id, job_id = uuid4(), uuid4(), uuid4()
			session_gen = get_db()
			session = next(session_gen)
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
