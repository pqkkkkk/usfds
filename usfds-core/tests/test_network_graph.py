"""ISS-041 / SUC-19: Embedded LadybugDB (:memory:) Network Graph Link Analysis tests."""
from datetime import datetime, timedelta, timezone
import io
import json
from uuid import uuid4

import pandas as pd
import pytest

from usfds_core.domain.entities.detection import DetectionJob
from usfds_core.domain.entities.enums import DetectionJobStatus
from usfds_core.services.investigation.network_graph import (
	LadybugNetworkGraphService,
	LiveRiskOverlay,
)
from usfds_core.services.warehouse.project_warehouse import ProjectWarehouse
from usfds_core.storage.base_storage import IFileStorage


class _MemoryStorage(IFileStorage):
	def __init__(self):
		self.files: dict[str, bytes] = {}

	def save_bytes(self, file_path, data):
		self.files[file_path] = data
		return file_path

	def read_bytes(self, file_path):
		return self.files[file_path]

	def exists(self, file_path):
		return file_path in self.files


def _to_parquet_bytes(rows: list[dict]) -> bytes:
	buf = io.BytesIO()
	pd.DataFrame(rows).to_parquet(buf, index=False)
	return buf.getvalue()


def _make_job(project_id, storage: _MemoryStorage, rows: list[dict], created_at: datetime, name: str = "scan") -> DetectionJob:
	job_id = uuid4()
	path = f"datasets/{project_id}/inferences/{job_id}/predictions.parquet"
	storage.save_bytes(path, _to_parquet_bytes(rows))
	job = DetectionJob(
		job_id=job_id,
		project_id=project_id,
		job_name=name,
		output_path=path,
		score_threshold=0.5,
		status=DetectionJobStatus.COMPLETED,
		created_at=created_at,
	)
	ProjectWarehouse(storage).write_job_facts(job)
	return job


def _tx(
	event_id: str,
	user_id: str,
	*,
	ts: str = "2026-11-10T10:00:00Z",
	amount: float = 250.0,
	score: float = 0.1,
	final_action: str = "ALLOW",
	device_id: str | None = None,
	ip_address: str | None = None,
	card_id: str | None = None,
	merchant_id: str | None = None,
	merchant_category: str | None = None,
	rules: list[str] | None = None,
) -> dict:
	return {
		"event_id": event_id,
		"user_id": user_id,
		"timestamp": ts,
		"amount": amount,
		"model_score": score,
		"rule_action": "REJECT" if rules else "ALLOW",
		"final_action": final_action,
		"triggered_rules": json.dumps(rules or []),
		"device_id": device_id,
		"ip_address": ip_address,
		"card_id": card_id,
		"merchant_id": merchant_id,
		"merchant_category": merchant_category,
	}


@pytest.fixture
def no_pandas_parquet_read(monkeypatch):
	def _blocked(*args, **kwargs):
		raise AssertionError("pd.read_parquet must not be used (ISS-012 / ISS-041)")

	monkeypatch.setattr(pd, "read_parquet", _blocked)


def test_ladybug_graph_builds_1hop_2hop_and_detects_hub_and_merchant_ring(no_pandas_parquet_read):
	"""ISS-041 / SUC-19: 1-hop vs 2-hop traversal + DEVICE_IP_CARD_HUB and MERCHANT_RING detection without pd.read_parquet."""
	storage = _MemoryStorage()
	project_id = uuid4()
	t0 = datetime(2026, 11, 10, tzinfo=timezone.utc)
	rows = [
		# 3 users sharing DEV-HUB (1 flagged)
		_tx("E1", "U1", score=0.92, final_action="REJECT", device_id="DEV-HUB", ip_address="10.0.0.1"),
		_tx("E2", "U2", score=0.25, final_action="ALLOW", device_id="DEV-HUB"),
		_tx("E3", "U3", score=0.30, final_action="ALLOW", device_id="DEV-HUB"),
		# 3 flagged users transacting at MERCH-RING
		_tx("E4", "U1", score=0.88, final_action="REVIEW", merchant_id="MERCH-RING", merchant_category="CRYPTO"),
		_tx("E5", "U4", score=0.91, final_action="REJECT", merchant_id="MERCH-RING", merchant_category="CRYPTO"),
		_tx("E6", "U5", score=0.84, final_action="REVIEW", merchant_id="MERCH-RING", merchant_category="CRYPTO"),
	]
	job = _make_job(project_id, storage, rows, t0)
	service = LadybugNetworkGraphService(storage)

	sub_1hop = service.get_subgraph(project_id, [job], "USER_ID", "U1", hops=1, days=90)
	assert sub_1hop["available"] is True
	node_ids_1 = {n["id"] for n in sub_1hop["nodes"]}
	assert node_ids_1 == {
		"USER_ID:U1",
		"DEVICE_ID:DEV-HUB",
		"IP_ADDRESS:10.0.0.1",
		"MERCHANT_ID:MERCH-RING",
	}

	sub_2hop = service.get_subgraph(project_id, [job], "USER_ID", "U1", hops=2, days=90)
	node_ids_2 = {n["id"] for n in sub_2hop["nodes"]}
	assert {"USER_ID:U2", "USER_ID:U3", "USER_ID:U4", "USER_ID:U5"}.issubset(node_ids_2)

	patterns_by_node = {(p["pattern_type"], p["node_id"]) for p in sub_2hop["patterns"]}
	assert ("DEVICE_IP_CARD_HUB", "DEVICE_ID:DEV-HUB") in patterns_by_node
	assert ("MERCHANT_RING", "MERCHANT_ID:MERCH-RING") in patterns_by_node

	hubs = service.list_hubs(project_id, [job], days=90)
	assert hubs["available"] is True
	hub_ids = {h["id"] for h in hubs["hubs"]}
	assert {"DEVICE_ID:DEV-HUB", "MERCHANT_ID:MERCH-RING"}.issubset(hub_ids)


def test_ladybug_graph_enforces_top50_expand_cap_200_canvas_limit_and_super_node_filter(no_pandas_parquet_read):
	"""ISS-041 / SUC-19 4a / BR-IV-05: expand caps at Top 50 riskiest neighbors, honors 200-node canvas limit, and filters super-nodes."""
	storage = _MemoryStorage()
	project_id = uuid4()
	t0 = datetime(2026, 11, 10, tzinfo=timezone.utc)
	rows = []
	for idx in range(80):
		uid = f"U-{idx:03d}"
		is_high = idx < 10
		rows.append(
			_tx(
				f"EV-{idx:03d}",
				uid,
				score=0.95 if is_high else 0.05 + idx * 0.001,
				final_action="REJECT" if is_high else "ALLOW",
				merchant_id="MERCH-SUPER",
				merchant_category="RETAIL",
			)
		)
	# Also connect U-000 to a normal device so subgraph(hide_super_nodes=True) has non-super links
	rows.append(_tx("EV-DEV", "U-000", score=0.90, final_action="REJECT", device_id="DEV-SMALL"))
	job = _make_job(project_id, storage, rows, t0)
	service = LadybugNetworkGraphService(storage, super_node_degree_threshold=50)

	overlay = LiveRiskOverlay(
		blacklisted={("USER_ID", "U-079")},
		open_case_counts={"U-078": 1},
	)
	expanded = service.expand_node(
		project_id,
		[job],
		"MERCHANT_ID",
		"MERCH-SUPER",
		existing_node_ids=["MERCHANT_ID:MERCH-SUPER"],
		overlay=overlay,
		hide_super_nodes=False,
	)
	assert len(expanded["added_nodes"]) == 50
	assert expanded["truncated_neighbors"] is True
	assert expanded["total_neighbors"] == 80
	added_ids = {n["id"] for n in expanded["added_nodes"]}
	assert "USER_ID:U-079" in added_ids  # CRITICAL blacklisted user kept first
	assert "USER_ID:U-078" in added_ids  # WARNING open-case user kept near top
	assert "USER_ID:U-000" in added_ids  # flagged user kept over normal low-score users

	# Canvas cap 200: 190 existing nodes -> at most 10 new nodes added
	existing_190 = ["MERCHANT_ID:MERCH-SUPER"] + [f"USER_ID:DUMMY-{i}" for i in range(189)]
	capped = service.expand_node(
		project_id,
		[job],
		"MERCHANT_ID",
		"MERCH-SUPER",
		existing_node_ids=existing_190,
		overlay=overlay,
		hide_super_nodes=False,
	)
	assert len(capped["added_nodes"]) == 10
	assert capped["canvas_limit_reached"] is True

	# Super-node filter hides MERCH-SUPER (degree 80 > 50) from U-000's 2-hop subgraph
	filtered = service.get_subgraph(
		project_id,
		[job],
		"USER_ID",
		"U-000",
		hops=2,
		hide_super_nodes=True,
	)
	filtered_ids = {n["id"] for n in filtered["nodes"]}
	assert "MERCHANT_ID:MERCH-SUPER" not in filtered_ids
	assert "DEVICE_ID:DEV-SMALL" in filtered_ids


def test_ladybug_graph_handles_missing_entity_columns_and_lru_cache_invalidation(no_pandas_parquet_read):
	"""ISS-041 / SUC-19 2a: missing secondary entity columns return available=False; cache hits reuse DB and new job invalidates."""
	storage = _MemoryStorage()
	service = LadybugNetworkGraphService(storage)

	# (a) Project with only core columns (no device/ip/card/merchant)
	p_empty = uuid4()
	t0 = datetime(2026, 11, 10, tzinfo=timezone.utc)
	job_empty = _make_job(p_empty, storage, [_tx("E0", "U0", score=0.8, final_action="REVIEW")], t0)
	res_empty = service.get_subgraph(p_empty, [job_empty], "USER_ID", "U0")
	assert res_empty["available"] is False
	assert "user_id" in res_empty["message"]

	# (b) Cache hit & invalidation on new job
	p_live = uuid4()
	builds_before = service.cache_builds
	hits_before = service.cache_hits
	job_1 = _make_job(p_live, storage, [_tx("E1", "U1", device_id="DEV-1")], t0, name="j1")
	first = service.get_subgraph(p_live, [job_1], "USER_ID", "U1")
	assert first["available"] is True
	assert service.cache_builds == builds_before + 1
	assert service.cache_hits == hits_before

	second = service.get_subgraph(p_live, [job_1], "USER_ID", "U1")
	assert second["available"] is True
	assert service.cache_builds == builds_before + 1
	assert service.cache_hits == hits_before + 1

	job_2 = _make_job(
		p_live,
		storage,
		[_tx("E2", "U1", ip_address="8.8.8.8")],
		t0 + timedelta(hours=1),
		name="j2",
	)
	third = service.get_subgraph(p_live, [job_1, job_2], "USER_ID", "U1")
	assert service.cache_builds == builds_before + 2
	assert "IP_ADDRESS:8.8.8.8" in {n["id"] for n in third["nodes"]}


def test_ladybug_graph_edge_transactions_and_artifact_fallback(no_pandas_parquet_read):
	"""ISS-041 / SUC-19: edge inspector returns deduplicated transactions with job_id & case_id; legacy artifact fallback builds graph."""
	storage = _MemoryStorage()
	project_id = uuid4()
	t0 = datetime(2026, 11, 10, tzinfo=timezone.utc)

	# (a) Same event_id scanned by old & new job -> latest scan wins; 2 distinct events on edge (U1, DEV-1)
	job_old = _make_job(
		project_id,
		storage,
		[
			_tx("EV-1", "U1", ts="2026-11-09T10:00:00Z", amount=100.0, score=0.2, final_action="ALLOW", device_id="DEV-1"),
			_tx("EV-2", "U1", ts="2026-11-10T11:00:00Z", amount=550.0, score=0.9, final_action="REJECT", device_id="DEV-1", rules=["R_VEL"]),
		],
		t0,
		name="old",
	)
	job_new = _make_job(
		project_id,
		storage,
		[
			_tx("EV-1", "U1", ts="2026-11-09T10:00:00Z", amount=100.0, score=0.85, final_action="REVIEW", device_id="DEV-1"),
		],
		t0 + timedelta(hours=2),
		name="new",
	)
	service = LadybugNetworkGraphService(storage)
	overlay = LiveRiskOverlay(event_case_ids={"EV-2": "case-uuid-2"})
	edge_res = service.get_edge_transactions(
		project_id,
		[job_old, job_new],
		"U1",
		"DEVICE_ID",
		"DEV-1",
		overlay=overlay,
		days=90,
	)
	assert edge_res["available"] is True
	assert edge_res["total"] == 2
	by_ev = {item["event_id"]: item for item in edge_res["transactions"]}
	assert by_ev["EV-1"]["job_id"] == str(job_new.job_id)
	assert by_ev["EV-1"]["model_score"] == pytest.approx(0.85)
	assert by_ev["EV-2"]["case_id"] == "case-uuid-2"
	assert by_ev["EV-2"]["rule_codes"] == ["R_VEL"]

	# (b) Artifact fallback when project has no COMPLETED DetectionJob
	p_legacy = uuid4()
	artifact_key = f"datasets/{p_legacy}/mapped.parquet"
	storage.save_bytes(
		artifact_key,
		_to_parquet_bytes([
			{"event_id": "A1", "user_id": "U-LEG-1", "timestamp": "2026-11-01T00:00:00Z", "amount": 200.0, "device": "DEV-LEG"},
			{"event_id": "A2", "user_id": "U-LEG-2", "timestamp": "2026-11-02T00:00:00Z", "amount": 300.0, "device": "DEV-LEG"},
		]),
	)
	fallback_sub = service.get_subgraph(
		p_legacy,
		[],
		"USER_ID",
		"U-LEG-1",
		hops=2,
		artifact_path=artifact_key,
	)
	assert fallback_sub["available"] is True
	assert {"USER_ID:U-LEG-1", "DEVICE_ID:DEV-LEG", "USER_ID:U-LEG-2"}.issubset({n["id"] for n in fallback_sub["nodes"]})
