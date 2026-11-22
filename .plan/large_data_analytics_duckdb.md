# Plan: Project Fact Warehouse (DuckDB) & Worker Analytics Queue

> **Task ID:** `large_data_analytics_duckdb` · **Issues:** ISS-012 (chosen by the user) · **Spec:** `docs/features/insight_report/suc-spec.md`, `docs/features/detection/inference/suc-spec.md`
> **Conflict verdict:** NEEDS-SEQUENCING (bắt đầu sau khi `own_scope_access_control` merge) · **Status:** Draft <!-- [26-11-22] warehouse mỗi job 1 file + gộp định kỳ; phần Investigation tách sang ISS-045 -->

## 1. Context (facts)
- **Insight & Report đọc rời rạc `N` file Parquet bằng pandas trong API process:**
  - `usfds-core/src/usfds_core/services/insight_report/engine.py:126-256` (`DuckDBInsightEngine._build_unified_transactions_df`): mỗi request đọc toàn bộ `predictions.parquet` của mọi `DetectionJob` `COMPLETED` qua `read_bytes()` + `pd.read_parquet`, `df.to_dict(orient="records")` (dòng 178), duyệt từng dòng Python, dựng lại `pd.DataFrame(rows)` (dòng 306) rồi mới đăng ký vào DuckDB.
  - `engine.py:607-641, 673-687, 712-723, 853-879`: lặp `itertuples` cho `rule_leaderboard`, 34 query rời rạc cho `score_calibration`, `threshold_curve`, `amount_brackets`.
  - `usfds-core/src/usfds_core/services/insight_report/service.py:103-120`: `date_from`/`date_to` lọc theo `job.created_at` thay vì `tx_timestamp`; `ReportScopeToolbar.tsx:36-54` chọn theo từng phiên `DetectionJob`.
- **DuckDB không giới hạn tài nguyên, worker không tách queue:** `engine.py:121` `duckdb.connect(":memory:")` mặc định (≈80% RAM, mọi core); `usfds-worker/src/usfds_worker/main.py:99-120` chạy chung 3 queue, chưa có `QUEUE_ANALYTICS` / `USFDS_WORKER_QUEUES`.
- **Detection Results/Export/Send nạp toàn bộ file vào pandas:**
  - `inference_service.py:799-957` (`_load_job_predictions_df`, `get_detection_job_results`): nạp toàn bộ `predictions.parquet`, lọc/sort bằng Python rồi mới cắt trang.
  - `inference_service.py:969+` & `detection_router.py:240-280`: export giữ toàn bộ `file_bytes` trong RAM.
  - `detection_router.py:290-350` (`send_to_investigation`): nạp toàn bộ `predictions.parquet` lần 1 qua `_source_frame` (dòng 308), rồi `ingest_request` (dòng 341 → `investigation_router.py:102`) nạp lại lần 2 chỉ để kiểm tra vài `event_id`.
- **Storage chỉ có `read_bytes`/`save_bytes`/`exists`/`delete`/`save_file`** (`base_storage.py:10-45`): chưa có `list_keys`, `open_local_path`, `upload_file`.

## 2. Goal, scope verdict & non-goals
- **Goal:**
  1. Mỗi `DetectionJob` `COMPLETED` ghi 1 file fact chuẩn hóa, chỉ thêm, `warehouse/{project_id}/fact_transactions/job_{job_id}.parquet`; worker gộp định kỳ thành `compacted_{uuid}.parquet`; DuckDB đọc toàn bộ và khử trùng lặp `event_id` lúc đọc (lần quét mới nhất thắng).
  2. Insight & Report chạy trên warehouse theo `tx_timestamp`, thực thi trên `usfds-worker` qua `QUEUE_ANALYTICS` với DuckDB khóa trần RAM/CPU.
  3. Detection Results/Export/Send to Investigation truy vấn/stream chọn lọc bằng DuckDB, không nạp toàn bộ file vào pandas.
- **Scope:** OK.
- **Non-goals / omitted:**
  - Mọi thay đổi chức năng của module Investigation (bỏ Assign, Workbench/behavior profile đọc warehouse, snapshot bằng chứng Case) → `ISS-045`. Send to Investigation giữ nguyên hành vi và API; task này chỉ đổi cách đọc dữ liệu.
  - Đồ thị liên kết SUC-19 → `ISS-041`.
  - Chuyển các bước `Data Management` sang DuckDB → `ISS-044`.
  - DuckDB-wasm trên trình duyệt; thay đổi tiền xử lý ML / huấn luyện.
- **Assumptions:**
  - **Gộp định kỳ không cần khóa:** job compaction đọc tập file hiện có → ghi `compacted_{uuid}.parquet` → chỉ xóa các file đầu vào nó đã đọc. Hai lần gộp song song chỉ tạo bản trùng, được khử khi đọc (`QUALIFY row_number() OVER (PARTITION BY event_id ORDER BY scanned_at DESC, job_id DESC) = 1`). Ngưỡng mặc định: gộp khi > 20 file/dự án (`USFDS_WAREHOUSE_COMPACT_THRESHOLD`).
  - **Tương thích ngược:** job `COMPLETED` cũ chưa có file fact được bổ sung bằng DuckDB khi đồng bộ (so `job_id` có trong warehouse với job `COMPLETED` trong DB), không dùng `pd.read_parquet`.
  - **Send to Investigation:** `detection_router.send_to_investigation` đọc đúng các `event_ids` được chọn 1 lần từ `predictions.parquet` của job bằng DuckDB; `ingest_request` nhận thêm tham số tùy chọn `source_rows` để dùng lại dữ liệu đó thay vì gọi `_source_frame` lần 2. Hành vi, response và mã lỗi (`400` khi event không flagged/không tồn tại) giữ nguyên.
  - DuckDB qua helper `create_bounded_duckdb_connection(threads=2, memory_limit="512MB", temp_directory=...)`.
  - `USFDS_WORKER_QUEUES` mặc định bật cả `training,batch_inference,data_pipeline,analytics`.
  - Backend vẫn chấp nhận tham số `job_ids` tùy chọn ở `/api/v1/reports/*`; UI bỏ chọn theo phiên.

## 3. Files
| Action | File | Milestone | Note |
|---|---|---|---|
| modify | `usfds-core/src/usfds_core/storage/base_storage.py` | M1 | Thêm `list_keys(prefix)`, `open_local_path` (context manager), `upload_file` |
| modify | `usfds-infra/src/usfds_infra/storage/local_storage.py` | M1 | Override: `Path` trực tiếp (zero-copy), `upload_file`, `list_keys` |
| modify | `usfds-infra/src/usfds_infra/storage/s3_storage.py` | M1 | Override: `download_file` vào file tạm, `upload_file`, `list_objects_v2` phân trang |
| create | `usfds-core/src/usfds_core/services/warehouse/__init__.py` | M1 | Package mới |
| create | `usfds-core/src/usfds_core/services/warehouse/project_warehouse.py` | M1 | `create_bounded_duckdb_connection`, `ProjectWarehouse` (`write_job_facts`, `sync_missing_jobs`, `compact`, `fact_view` có khử trùng lặp) |
| modify | `usfds-core/src/usfds_core/services/inference/inference_service.py` | M1, M2 | M1: `handle_job_completion` ghi file fact; M2: `get_detection_job_results`, `export_detection_job_results*`, `fetch_job_events(job_id, event_ids)` bằng DuckDB |
| modify | `usfds-core/src/usfds_core/services/insight_report/engine.py` | M1 | Đọc `fact_view`, lọc `tx_timestamp`, gộp query thành single-pass SQL, dùng connection khóa trần |
| modify | `usfds-core/src/usfds_core/services/insight_report/service.py` | M1 | `date_from`/`date_to` theo `tx_timestamp` |
| modify | `usfds-core/src/usfds_core/repositories/base_case_repo.py` | M1 | `get_case_ids_by_events(project_id, event_ids)` (thay `list_by_project` khi gắn `case_id` cho trang kết quả) |
| modify | `usfds-infra/src/usfds_infra/database/case_repositories.py` | M1 | Cài đặt bằng SQL `IN` tương thích PostgreSQL |
| modify | `usfds-infra/tests/test_s3_storage.py` | M1 | Test storage |
| modify | `usfds-infra/tests/test_case_repositories.py` | M1 | Test repo dưới `pg_compat` |
| create | `usfds-core/tests/test_project_warehouse.py` | M1 | Test warehouse |
| modify | `usfds-core/tests/test_insight_report_service.py` | M1 | Test lọc `tx_timestamp`, không `pd.read_parquet` |
| modify | `usfds-infra/src/usfds_infra/job_queue/bullmq_queue.py` | M2 | Append `QUEUE_ANALYTICS`, `JOB_INSIGHT_REPORT`, `JOB_WAREHOUSE_COMPACT` (hot-spot: append-only) |
| modify | `usfds-infra/src/usfds_infra/job_queue/__init__.py` | M2 | Export hằng mới (hot-spot: append-only) |
| modify | `usfds-worker/src/usfds_worker/config.py` | M2 | `enabled_queues` (`USFDS_WORKER_QUEUES`) |
| modify | `usfds-worker/src/usfds_worker/handlers.py` | M2 | `handle_insight_report`, `handle_warehouse_compact` |
| modify | `usfds-worker/src/usfds_worker/main.py` | M2 | Append `ANALYTICS_QUEUE_HANDLERS`, lọc worker theo `enabled_queues` (hot-spot: append-only) |
| modify | `usfds-worker/src/usfds_worker/testing.py` | M2 | Đăng ký `QUEUE_ANALYTICS` trong `InlineJobQueue` |
| modify | `usfds-server/src/usfds_server/routers/insight_report_router.py` | M2 | Ở `dispatch_backend == "queue"` đẩy qua `QUEUE_ANALYTICS` |
| modify | `usfds-server/src/usfds_server/routers/detection_router.py` | M2 | Stream export từ DuckDB; `send_to_investigation` đọc chọn lọc 1 lần qua `fetch_job_events` |
| modify | `usfds-server/src/usfds_server/routers/investigation_router.py` | M2 | Chỉ thêm tham số tùy chọn `source_rows` cho `ingest_request` (không đổi hành vi khác) |
| modify | `usfds-core/tests/test_inference_service.py` | M2 | Test results bằng DuckDB |
| modify | `usfds-server/tests/test_detection_api.py` | M2 | Test export streaming + send-to-investigation không nạp full file |
| modify | `usfds-server/tests/test_insight_report_api.py` | M2 | Test queue mode |
| modify | `usfds-web/src/components/modules/reports/ReportScopeToolbar.tsx` | M3 | Bỏ chọn phiên, lọc theo khung thời gian giao dịch |
| modify | `usfds-web/src/components/modules/InsightReportModule.tsx` | M3 | Gỡ truy vấn `detection-jobs` dư thừa |
| modify | `usfds-web/src/components/modules/reports/ExecutiveOverviewTab.tsx` | M3 | Trục thời gian theo `tx_timestamp` |
| create | `usfds-web/src/components/modules/reports/ReportScopeToolbar.test.tsx` | M3 | Vitest + MSW |
| migration | — | — | Không đổi schema |

## 4. Dependencies & conflicts (with other tasks on BOARD)
| # | Check | Answer |
|---|---|---|
| D1 | Needs unfinished task? | Yes: `own_scope_access_control` (ISS-043, ISS-023) — plan ghi Done nhưng chưa merge; sửa `inference_service.py`, `detection_router.py` |
| D2 | Needed by unfinished task? | Yes: `ISS-045` (Investigation đọc warehouse), `ISS-041` (bảng cạnh đồ thị dựng từ warehouse) |
| C1 | Modified files owned by in-progress task? | Yes: `inference_service.py`, `detection_router.py`, `test_detection_api.py`, `test_insight_report_api.py` → `own_scope_access_control` |
| C2 | Hot-spot files touched | `bullmq_queue.py`, `job_queue/__init__.py`, `usfds-worker/main.py` (append-only) |
| C3 | Schema change | No |
| C4 | Public contract change | Yes (không phá vỡ): `date_from`/`date_to` của `/api/v1/reports/*` đổi nghĩa sang `tx_timestamp` → consumer: `usfds-web` (sửa trong M3). URL & response của `/reports/*`, `/detection/*`, `/cases/*` giữ nguyên |
| C5 | Shared UI shell change | No |

## 5. Acceptance tests (user reviews this section)
| Milestone | Test | Given | When | Then | Covers |
|---|---|---|---|---|---|
| M1 | `test_storage_open_local_path_list_keys_and_upload_local_and_s3` (`usfds-infra/tests/test_s3_storage.py`) | File Parquet trong `LocalFileStorage` và `S3FileStorage` (moto) | `list_keys(prefix)`, `open_local_path(key)`, `upload_file(src, key)` | Local trả `Path` gốc không copy; S3 stream qua file tạm và tự dọn khi thoát `with`; `list_keys` trả đủ khóa theo prefix (kể cả > 1 trang) | ISS-012 |
| M1 | `test_case_repo_get_case_ids_by_events_is_pg_compatible` (`usfds-infra/tests/test_case_repositories.py`) | Case thuộc nhiều project | `get_case_ids_by_events(p, ["EV-1","EV-MISSING"])` dưới `pg_compat` | Chỉ trả `{"EV-1": case_id}` của project `p`, không `PostgresCompatibilityError` | ISS-012 |
| M1 | `test_warehouse_writes_one_file_per_job_and_dedupes_latest_scan` (`usfds-core/tests/test_project_warehouse.py`) | 2 job `COMPLETED`, job sau quét lại 1 `event_id` với điểm khác; `pd.read_parquet` bị monkeypatch ném lỗi | `handle_job_completion` cho từng job rồi đọc `fact_view` | Có 2 file `job_{id}.parquet`; `event_id` trùng chỉ còn bản của job mới hơn; connection có `threads=2` & `memory_limit` | ISS-012 |
| M1 | `test_warehouse_compaction_is_safe_when_run_twice_concurrently` (`usfds-core/tests/test_project_warehouse.py`) | 25 file job trong warehouse | Gọi `compact()` hai lần trên cùng tập file (mô phỏng chạy song song) | Không mất dòng nào, `fact_view` giống hệt trước khi gộp, số file giảm | ISS-012 |
| M1 | `test_warehouse_bootstraps_legacy_completed_jobs` (`usfds-core/tests/test_project_warehouse.py`) | Job `COMPLETED` cũ chỉ có `predictions.parquet` | `sync_missing_jobs(project_id)` | File fact được tạo bằng DuckDB; gọi lại lần 2 không tạo thêm | ISS-012 |
| M1 | `test_insight_report_filters_by_tx_timestamp_on_warehouse_without_pandas` (`usfds-core/tests/test_insight_report_service.py`) | Giao dịch ở các ngày `tx_timestamp` khác nhau, job tạo cùng ngày; `pd.read_parquet` bị chặn | `get_executive_overview`, `get_effectiveness_analysis`, `get_typology_and_patterns` với `date_from`/`date_to` | Chỉ tính giao dịch có `tx_timestamp` trong khoảng; số liệu khớp giá trị kỳ vọng | ISS-012 |
| M2 | `test_insight_report_runs_on_analytics_worker_queue_in_queue_mode` (`usfds-server/tests/test_insight_report_api.py`) | `client_queue_mode` có dữ liệu job + Case | Gọi `/api/v1/reports/overview`, `/effectiveness`, `/patterns`, `/executive-summary`, `/export` | Được ủy quyền qua `QUEUE_ANALYTICS` (`JOB_INSIGHT_REPORT`) và trả đúng kết quả; `WorkerSettings` lọc queue theo `USFDS_WORKER_QUEUES` | ISS-012 |
| M2 | `test_detection_results_pagination_uses_duckdb_without_pandas_full_load` (`usfds-core/tests/test_inference_service.py`) | Job 100 dòng, một số `event_id` có Case; `pd.read_parquet` bị chặn | `get_detection_job_results(action_filter="FLAGGED", rule_code, search, min/max_score, limit=10, offset=5)` | Đúng `total_filtered`, thứ tự `REJECT > REVIEW > ALLOW` rồi `model_score DESC`, đúng 10 dòng kèm `case_id` | ISS-012 |
| M2 | `test_detection_export_and_send_to_investigation_use_duckdb_without_full_frame_load` (`usfds-server/tests/test_detection_api.py`) | Job có dòng flagged & allow; `pd.read_parquet` bị chặn | `GET /api/v1/detection/jobs/{id}/export?only_flagged=true&file_format=csv` và `POST /api/v1/detection/jobs/{id}/send-to-investigation` | CSV stream chỉ gồm các dòng flagged; send-to-investigation tạo Case với response như cũ, từ chối `400` nếu event không flagged/không tồn tại | ISS-012 |
| M3 | `ReportScopeToolbar: filters by transaction date range without job picker` (`usfds-web/src/components/modules/reports/ReportScopeToolbar.test.tsx`) | MSW trả dữ liệu report | Chọn `Từ ngày → Đến ngày` | Request `/reports/*` mang `date_from`/`date_to`, không còn bộ chọn phiên `DetectionJob` | ISS-012 |

## 6. Milestones & to-do (checkpoints, not stop points: all tests green at each)

- [ ] **M1 — Storage streaming, DuckDB bounded & Project Fact Warehouse** (`usfds-core`, `usfds-infra`): mỗi job ghi 1 file fact, gộp không cần khóa, Insight đọc warehouse theo `tx_timestamp`.
  - [ ] [tests] Viết các test M1 trong §5; xác nhận fail đúng lý do
  - [ ] [core] `IFileStorage.list_keys/open_local_path/upload_file`; `ICaseRepository.get_case_ids_by_events`
  - [ ] [infra] Cài đặt trong `LocalFileStorage`, `S3FileStorage`, `SqliteCaseRepository`
  - [ ] [core] `services/warehouse/project_warehouse.py`: `create_bounded_duckdb_connection`, `write_job_facts`, `sync_missing_jobs`, `compact`, `fact_view`
  - [ ] [core] `handle_job_completion` gọi `write_job_facts`; viết lại `DuckDBInsightEngine` + `InsightReportService` trên `fact_view` theo `tx_timestamp`
  - [ ] [verify] `./scripts/test.sh core infra`
- [ ] **M2 — Worker Analytics Queue & DuckDB pushdown cho Detection Results/Export/Send** (`usfds-infra`, `usfds-worker`, `usfds-core`, `usfds-server`)
  - [ ] [tests] Viết các test M2 trong §5; xác nhận fail
  - [ ] [infra] Append `QUEUE_ANALYTICS`, `JOB_INSIGHT_REPORT`, `JOB_WAREHOUSE_COMPACT`
  - [ ] [worker] `enabled_queues`, `handle_insight_report`, `handle_warehouse_compact`, đăng ký `ANALYTICS_QUEUE_HANDLERS` (main + testing); job completion đẩy `JOB_WAREHOUSE_COMPACT` khi vượt ngưỡng (inline mode gọi trực tiếp)
  - [ ] [core] `get_detection_job_results`, `export_detection_job_results*`, `fetch_job_events` bằng DuckDB
  - [ ] [server] `insight_report_router.py` dispatch qua `QUEUE_ANALYTICS`; `detection_router.py` stream export + `send_to_investigation` đọc chọn lọc 1 lần; `ingest_request` nhận `source_rows`
  - [ ] [verify] `./scripts/test.sh core infra worker server`
- [ ] **M3 — UI Insight & Report theo khung thời gian giao dịch** (`usfds-web`)
  - [ ] [tests] Viết test M3 trong §5; xác nhận fail
  - [ ] [web] `ReportScopeToolbar.tsx`, `InsightReportModule.tsx`, `ExecutiveOverviewTab.tsx`
  - [ ] [verify] `./scripts/test.sh core infra worker server web`

Checkpoint log (the agent appends one line per finished milestone):
- —

## 7. Review hotspots (filled in after implementation)
- —

## 8. Open questions
- Ngưỡng gộp định kỳ 20 file/dự án có phù hợp không?
