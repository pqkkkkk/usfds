# Plan: Project Fact Warehouse (DuckDB), Worker Analytics Queue & Queue Timeout/Retry

> **Task ID:** `large_data_analytics_duckdb` · **Issues:** ISS-012, ISS-021 (chosen by the user) · **Spec:** `docs/features/insight_report/suc-spec.md`, `docs/features/detection/inference/suc-spec.md`
> **Conflict verdict:** PARALLEL-SAFE · **Status:** Done (26-11-22) <!-- [26-11-22] warehouse mỗi job 1 file + gộp định kỳ; phần Investigation tách sang ISS-045 --> <!-- [26-11-22] gộp ISS-021; own_scope_access_control đã merge vào origin/main -->

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
- **ISS-021 — request/reply qua queue bị bỏ dở khi timeout, không retry:**
  - `usfds-infra/src/usfds_infra/job_queue/bullmq_queue.py:104-141` (`enqueue_and_wait`): `attempts: 1` cứng, poll tới `timeout_seconds=300`, rồi `raise TimeoutError` nhưng job vẫn nằm trong queue / tiếp tục chạy trên worker → dataset/model vẫn được tạo, người dùng bấm lại tạo bản trùng.
  - Không router nào bắt `TimeoutError` (6 chỗ gọi: `training_router.py:206,312`, `dataset_router.py:137,298,364`, `rule_router.py:544`) → `500` ngoài envelope `ApiResponse` (`api.py:78-125` chỉ có handler cho `HTTPException`, validation, auth, permission).
  - `bullmq_queue.py:77-100` (`enqueue`): có `attempts`/`backoff_ms` nhưng `dispatchers.py:27,43` dùng mặc định `attempts=1` → backoff không bao giờ có hiệu lực.
  - `usfds-worker/src/usfds_worker/main.py:68-80` (`_make_processor`): mọi lỗi đều bọc thành `RuntimeError` → kể cả khi bật retry, lỗi nghiệp vụ (`ValueError`, `LookupError`, `FileNotFoundError`) cũng sẽ bị chạy lại vô ích.
  - `handlers.py:95-180`: `handle_training_run` / `handle_batch_inference` chỉ chuyển `PENDING → RUNNING`; lỗi thì ghi `FAILED`. Lần retry sau gặp `FAILED` sẽ chạy executor mà không reset trạng thái; gặp `COMPLETED` (worker chết sau commit) sẽ chạy lại toàn bộ.
  - bullmq `3.6.3` (venv `usfds-worker`) có sẵn `bullmq.UnrecoverableError` (`job.py:219` bỏ qua retry) và `Job.remove()` (`job.py:147`).
- **Storage chỉ có `read_bytes`/`save_bytes`/`exists`/`delete`/`save_file`** (`base_storage.py:10-45`): chưa có `list_keys`, `open_local_path`, `upload_file`.

## 2. Goal, scope verdict & non-goals
- **Goal:**
  1. Mỗi `DetectionJob` `COMPLETED` ghi 1 file fact chuẩn hóa, chỉ thêm, `warehouse/{project_id}/fact_transactions/job_{job_id}.parquet`; DuckDB đọc toàn bộ và khử trùng lặp `event_id` lúc đọc (lần quét mới nhất thắng).
  2. Insight & Report chạy trên warehouse theo `tx_timestamp`, thực thi trên `usfds-worker` qua `QUEUE_ANALYTICS` với DuckDB khóa trần RAM/CPU.
  3. Detection Results/Export/Send to Investigation truy vấn/stream chọn lọc bằng DuckDB, không nạp toàn bộ file vào pandas.
  4. (ISS-021) Khi `enqueue_and_wait` hết hạn: job chưa chạy bị xóa khỏi queue, job đang chạy để chạy tiếp; API trả `504` trong envelope `ApiResponse`. Báo cáo analytics được retry với exponential backoff khi lỗi tạm thời, lỗi nghiệp vụ không retry; handler training/batch không chạy lại bản ghi đã ở trạng thái cuối.
- **Scope:** OK.
- **Non-goals / omitted:**
  - (ISS-021) Không chuyển request/reply sang `202` + polling, không idempotency key (người dùng chọn phương án hủy-nếu-chưa-chạy + `504`). Không retry training/batch inference (executor đã ghi `FAILED`, xem Assumptions). Không retry cho job request/reply tạo dữ liệu (`data_pipeline`, `plugin_dry_run`, `rule_backtest`): giữ `attempts=1` vì người dùng đang chờ và có nguy cơ tạo bản trùng. Không hủy job đang `active` (bullmq không hỗ trợ dừng job đang chạy; trùng với ISS-011).
  - Mọi thay đổi chức năng của module Investigation (bỏ Assign, Workbench/behavior profile đọc warehouse, snapshot bằng chứng Case) → `ISS-045`. Send to Investigation giữ nguyên hành vi và API; task này chỉ đổi cách đọc dữ liệu.
  - Đồ thị liên kết SUC-19 → `ISS-041`.
  - Chuyển các bước `Data Management` sang DuckDB → `ISS-044`.
  - DuckDB-wasm trên trình duyệt; thay đổi tiền xử lý ML / huấn luyện.
- **Assumptions:**
  - **Chưa gộp file (user, 26-11-22):** không có compaction trong task này; số file `job_*.parquet` tăng theo số job, DuckDB đọc bằng glob và khử trùng lặp `event_id` lúc đọc (`QUALIFY row_number() OVER (PARTITION BY event_id ORDER BY scanned_at DESC, job_id DESC) = 1`). Gộp file là việc tiếp theo nếu số job/dự án lớn.
  - **Tương thích ngược:** job `COMPLETED` cũ chưa có file fact được bổ sung bằng DuckDB khi đồng bộ (so `job_id` có trong warehouse với job `COMPLETED` trong DB), không dùng `pd.read_parquet`.
  - **Send to Investigation:** `detection_router.send_to_investigation` đọc đúng các `event_ids` được chọn 1 lần từ `predictions.parquet` của job bằng DuckDB; `ingest_request` nhận thêm tham số tùy chọn `source_rows` để dùng lại dữ liệu đó thay vì gọi `_source_frame` lần 2. Hành vi, response và mã lỗi (`400` khi event không flagged/không tồn tại) giữ nguyên.
  - DuckDB qua helper `create_bounded_duckdb_connection(threads=2, memory_limit="512MB", temp_directory=...)`.
  - `USFDS_WORKER_QUEUES` mặc định bật cả `training,batch_inference,data_pipeline,analytics`.
  - **(ISS-021) Timeout:** `enqueue_and_wait` hết hạn → `getState()`; nếu `waiting|delayed|prioritized` thì `job.remove()` (job chưa chạy hoặc đang chờ retry) → `QueueWaitTimeoutError(job_id, cancelled=True)`; nếu `active` → `QueueWaitTimeoutError(job_id, cancelled=False)`. `QueueWaitTimeoutError` kế thừa `TimeoutError`, đặt trong `usfds_infra.job_queue`. Server thêm 1 exception handler → `504`, message tiếng Việt: "Tác vụ quá thời gian chờ và đã bị hủy, vui lòng thử lại" / "Tác vụ vẫn đang chạy nền, vui lòng tải lại danh sách sau ít phút". `job_id` ở đây là id BullMQ (router tự sinh dạng `ingest-{uuid4()}`, `plugin-{uuid4()}`, `backtest-{uuid4()}`, không phải id nghiệp vụ) → chỉ ghi vào log và `data.job_id` của envelope để đối chiếu, không đưa vào message cho người dùng.
  - **(ISS-021) Timeout theo queue:** `ServerSettings.queue_wait_timeout_seconds` (`USFDS_QUEUE_WAIT_TIMEOUT_SECONDS`, mặc định 300) cho 6 chỗ gọi hiện tại; `analytics_wait_timeout_seconds` (`USFDS_ANALYTICS_WAIT_TIMEOUT_SECONDS`, mặc định 120) cho `JOB_INSIGHT_REPORT`.
  - **(ISS-021) Retry (chỉ analytics):** `attempts=3`, backoff exponential 5s cho `JOB_INSIGHT_REPORT` (handler ném lỗi thật nên BullMQ retry được). `enqueue_and_wait` nhận thêm tham số `attempts` (mặc định 1). `JOB_TRAINING_RUN` / `JOB_BATCH_INFERENCE` giữ `attempts=1`: `TrainingRunExecutor.run` và `BatchInferenceExecutor.run` bắt mọi exception, ghi `FAILED` vào bảng nghiệp vụ và trả kết quả bình thường (`training/executor.py:216-224`, `inference/executor.py:653-661`) → BullMQ coi job là `completed`, retry không có tác dụng và `FAILED` là kết cục đúng (user xác nhận 26-11-22). Worker `_make_processor` ném `UnrecoverableError("<Type>: <msg>")` cho `ValueError`, `LookupError`, `FileNotFoundError`, `TypeError`, `MemoryError` (giữ format `failedReason` cho `raise_from_failed_reason`); lỗi khác (`OSError`, lỗi DB/S3, …) ném `RuntimeError` như cũ → được retry.
  - **(ISS-021) Idempotency handler:** `handle_training_run` / `handle_batch_inference`: bản ghi đã ở trạng thái cuối (`COMPLETED` hoặc `FAILED`) → return ngay, không chạy executor (chống chạy lại khi worker crash sau khi commit nhưng trước khi ack, hoặc job stalled bị giao lại).
  - Backend vẫn chấp nhận tham số `job_ids` tùy chọn ở `/api/v1/reports/*`; UI bỏ chọn theo phiên.

## 3. Files
| Action | File | Milestone | Note |
|---|---|---|---|
| modify | `usfds-core/src/usfds_core/storage/base_storage.py` | M1 | Thêm `open_local_path` (context manager), `upload_file` (không thêm `list_keys`: engine biết danh sách job từ DB nên tính khóa fact và dùng `exists()`; không compaction) <!-- [26-11-22] --> |
| modify | `usfds-infra/src/usfds_infra/storage/local_storage.py` | M1 | Override: `Path` trực tiếp (zero-copy), `upload_file` |
| modify | `usfds-infra/src/usfds_infra/storage/s3_storage.py` | M1 | Override: `download_file` vào file tạm, `upload_file` |
| create | `usfds-core/src/usfds_core/services/warehouse/__init__.py` | M1 | Package mới |
| create | `usfds-core/src/usfds_core/services/warehouse/project_warehouse.py` | M1 | `create_bounded_duckdb_connection`, `ProjectWarehouse` (`write_job_facts`, `sync_missing_jobs`, `fact_view` có khử trùng lặp) |
| modify | `usfds-core/src/usfds_core/services/inference/inference_service.py` | M1, M2 | M1: `handle_job_completion` ghi file fact; M2: `get_detection_job_results`, `export_detection_job_results*`, `fetch_job_events(job_id, event_ids)` bằng DuckDB |
| modify | `usfds-core/src/usfds_core/services/insight_report/engine.py` | M1 | Đọc `fact_view`, lọc `tx_timestamp`, gộp query thành single-pass SQL, dùng connection khóa trần |
| modify | `usfds-core/src/usfds_core/services/insight_report/service.py` | M1 | `date_from`/`date_to` theo `tx_timestamp` |
| modify | `usfds-core/src/usfds_core/repositories/base_case_repo.py` | M1 | `get_case_ids_by_events(project_id, event_ids)` (thay `list_by_project` khi gắn `case_id` cho trang kết quả) |
| modify | `usfds-infra/src/usfds_infra/database/case_repositories.py` | M1 | Cài đặt bằng SQL `IN` tương thích PostgreSQL |
| modify | `usfds-infra/tests/test_s3_storage.py` | M1 | Test storage (`open_local_path`/`upload_file`) |
| modify | `usfds-infra/tests/test_case_repositories.py` | M1 | Test repo dưới `pg_compat` |
| create | `usfds-core/tests/test_project_warehouse.py` | M1 | Test warehouse |
| modify | `usfds-core/tests/test_insight_report_service.py` | M1 | Test lọc `tx_timestamp`, không `pd.read_parquet` |
| modify | `usfds-infra/src/usfds_infra/job_queue/bullmq_queue.py` | M2 | Append `QUEUE_ANALYTICS`, `JOB_INSIGHT_REPORT` (hot-spot: append-only) |
| modify | `usfds-infra/src/usfds_infra/job_queue/__init__.py` | M2 | Export hằng mới + `QueueWaitTimeoutError` (hot-spot: append-only) |
| modify | `usfds-infra/src/usfds_infra/job_queue/bullmq_queue.py` | M0 | (ISS-021) `QueueWaitTimeoutError`; `enqueue_and_wait(attempts=...)`, hủy job chưa chạy khi timeout |
| modify | `usfds-infra/tests/test_job_queue.py` | M0 | (ISS-021) Test timeout/hủy/attempts |
| modify | `usfds-worker/src/usfds_worker/main.py` | M0 | (ISS-021) `_make_processor` phân loại lỗi → `UnrecoverableError` |
| modify | `usfds-worker/src/usfds_worker/handlers.py` | M0 | (ISS-021) Idempotency `handle_training_run`, `handle_batch_inference` |
| create | `usfds-worker/tests/test_retry_policy.py` | M0 | (ISS-021) Test phân loại lỗi + idempotency |
| modify | `usfds-server/src/usfds_server/api.py` | M0 | (ISS-021) Append exception handler `QueueWaitTimeoutError` → `504` (hot-spot: append-only) |
| modify | `usfds-server/src/usfds_server/config.py` | M0 | (ISS-021) Append `queue_wait_timeout_seconds`, `analytics_wait_timeout_seconds` (hot-spot: append-only) |
| modify | `usfds-server/src/usfds_server/routers/{training,dataset,rule}_router.py` | M0 | (ISS-021) Truyền `timeout_seconds=settings.queue_wait_timeout_seconds` |
| create | `usfds-server/tests/test_queue_timeout_api.py` | M0 | (ISS-021) Test `504` envelope |
| modify | `deploy/.env.example` | M0 | (ISS-021) Append 2 biến timeout (hot-spot: append-only) |
| modify | `usfds-worker/src/usfds_worker/config.py` | M2 | `enabled_queues` (`USFDS_WORKER_QUEUES`) |
| modify | `usfds-worker/src/usfds_worker/handlers.py` | M2 | `handle_insight_report` |
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
| D1 | Needs unfinished task? | No — `own_scope_access_control` đã merge vào `origin/main` (`917d80b`) |
| D2 | Needed by unfinished task? | Yes: `ISS-045` (Investigation đọc warehouse), `ISS-041` (bảng cạnh đồ thị dựng từ warehouse) |
| C1 | Modified files owned by in-progress task? | No — BOARD không có task `In progress` |
| C2 | Hot-spot files touched | `bullmq_queue.py`, `job_queue/__init__.py`, `usfds-worker/main.py`, `usfds-server/api.py`, `usfds-server/config.py`, `deploy/.env.example` (append-only; riêng `enqueue_and_wait` và `_make_processor` là sửa thân hàm — không có task nào khác đang mở) |
| C3 | Schema change | No |
| C4 | Public contract change | Yes (không phá vỡ): `date_from`/`date_to` của `/api/v1/reports/*` đổi nghĩa sang `tx_timestamp` → consumer: `usfds-web` (sửa trong M3). URL & response của `/reports/*`, `/detection/*`, `/cases/*` giữ nguyên. (ISS-021) Endpoint request/reply: lỗi timeout đổi từ `500` thô sang `504` + envelope `ApiResponse` → `usfds-web/src/api/client.ts` đã hiển thị `message` của envelope lỗi (ISS-028), không cần sửa web |
| C5 | Shared UI shell change | No |

## 5. Acceptance tests (user reviews this section)
| Milestone | Test | Given | When | Then | Covers |
|---|---|---|---|---|---|
| M0 | `test_enqueue_and_wait_timeout_removes_job_not_yet_started` (`usfds-infra/tests/test_job_queue.py`) | Stub job luôn ở `waiting` | `enqueue_and_wait(timeout_seconds=0.05)` | Ném `QueueWaitTimeoutError(cancelled=True, job_id=...)`; `job.remove()` được gọi đúng 1 lần | ISS-021 |
| M0 | `test_enqueue_and_wait_timeout_keeps_active_job_running` (`usfds-infra/tests/test_job_queue.py`) | Stub job luôn ở `active` | `enqueue_and_wait(timeout_seconds=0.05)` | Ném `QueueWaitTimeoutError(cancelled=False)`; không gọi `remove()` | ISS-021 |
| M0 | `test_processor_marks_business_errors_unrecoverable_and_retries_transient` (`usfds-worker/tests/test_retry_policy.py`) | Handler ném lần lượt `ValueError("x")`, `FileNotFoundError("y")`, `OSError("s3 down")` | Gọi processor từ `_make_processor` | 2 lỗi đầu → `bullmq.UnrecoverableError` với message `"ValueError: x"` / `"FileNotFoundError: y"`; `OSError` → `RuntimeError("OSError: s3 down")` (retry được) | ISS-021 |
| M0 | `test_training_and_batch_handlers_skip_records_already_in_terminal_state` (`usfds-worker/tests/test_retry_policy.py`) | Run `COMPLETED` và DetectionJob `FAILED` (giao lại sau crash) | Gọi lại `handle_training_run` / `handle_batch_inference` | Return ngay, executor không được gọi, trạng thái và `error_message` giữ nguyên, không tạo `ModelVersion` mới | ISS-021 |
| M0 | `test_queue_wait_timeout_returns_504_envelope` (`usfds-server/tests/test_queue_timeout_api.py`) | `client_queue_mode`, `enqueue_and_wait` bị patch ném `QueueWaitTimeoutError(cancelled=True/False)` | `POST` dataset ingest | `504`, body `ApiResponse` `success=false`, message tiếng Việt tương ứng (không chứa `job_id`), `data.job_id` có mặt | ISS-021 |
| M1 | `test_storage_open_local_path_and_upload_file_local_and_s3` (`usfds-infra/tests/test_s3_storage.py`) | File Parquet trong `LocalFileStorage` và `S3FileStorage` (moto) | `open_local_path(key)`, `upload_file(src, key)` | Local trả `Path` gốc không copy; S3 tải về file tạm và tự dọn khi thoát `with`; khóa không tồn tại ném `FileNotFoundError` | ISS-012 |
| M1 | `test_case_repo_get_case_ids_by_events_is_pg_compatible` (`usfds-infra/tests/test_case_repositories.py`) | Case thuộc nhiều project | `get_case_ids_by_events(p, ["EV-1","EV-MISSING"])` dưới `pg_compat` | Chỉ trả `{"EV-1": case_id}` của project `p`, không `PostgresCompatibilityError` | ISS-012 |
| M1 | `test_warehouse_writes_one_file_per_job_and_dedupes_latest_scan` (`usfds-core/tests/test_project_warehouse.py`) | 2 job `COMPLETED`, job sau quét lại 1 `event_id` với điểm khác; `pd.read_parquet` bị monkeypatch ném lỗi | `handle_job_completion` cho từng job rồi đọc `fact_view` | Có 2 file `job_{id}.parquet`; `event_id` trùng chỉ còn bản của job mới hơn; connection có `threads=2` & `memory_limit` | ISS-012 |
| M1 | `test_warehouse_bootstraps_legacy_completed_jobs` (`usfds-core/tests/test_project_warehouse.py`) | Job `COMPLETED` cũ chỉ có `predictions.parquet` | `sync_missing_jobs(project_id)` | File fact được tạo bằng DuckDB; gọi lại lần 2 không tạo thêm | ISS-012 |
| M1 | `test_insight_report_filters_by_tx_timestamp_on_warehouse_without_pandas` (`usfds-core/tests/test_insight_report_service.py`) | Giao dịch ở các ngày `tx_timestamp` khác nhau, job tạo cùng ngày; `pd.read_parquet` bị chặn | `get_executive_overview`, `get_effectiveness_analysis`, `get_typology_and_patterns` với `date_from`/`date_to` | Chỉ tính giao dịch có `tx_timestamp` trong khoảng; số liệu khớp giá trị kỳ vọng | ISS-012 |
| M2 | `test_insight_report_runs_on_analytics_worker_queue_in_queue_mode` (`usfds-server/tests/test_insight_report_api.py`) | `client_queue_mode` có dữ liệu job + Case | Gọi `/api/v1/reports/overview`, `/effectiveness`, `/patterns`, `/executive-summary`, `/export` | Được ủy quyền qua `QUEUE_ANALYTICS` (`JOB_INSIGHT_REPORT`, `attempts=3`, `timeout_seconds=analytics_wait_timeout_seconds`) và trả đúng kết quả; `WorkerSettings` lọc queue theo `USFDS_WORKER_QUEUES` | ISS-012, ISS-021 |
| M2 | `test_detection_results_pagination_uses_duckdb_without_pandas_full_load` (`usfds-core/tests/test_inference_service.py`) | Job 100 dòng, một số `event_id` có Case; `pd.read_parquet` bị chặn | `get_detection_job_results(action_filter="FLAGGED", rule_code, search, min/max_score, limit=10, offset=5)` | Đúng `total_filtered`, thứ tự `REJECT > REVIEW > ALLOW` rồi `model_score DESC`, đúng 10 dòng kèm `case_id` | ISS-012 |
| M2 | `test_detection_export_and_send_to_investigation_use_duckdb_without_full_frame_load` (`usfds-server/tests/test_detection_api.py`) | Job có dòng flagged & allow; `pd.read_parquet` bị chặn | `GET /api/v1/detection/jobs/{id}/export?only_flagged=true&file_format=csv` và `POST /api/v1/detection/jobs/{id}/send-to-investigation` | CSV stream chỉ gồm các dòng flagged; send-to-investigation tạo Case với response như cũ, từ chối `400` nếu event không flagged/không tồn tại | ISS-012 |
| M3 | `ReportScopeToolbar: filters by transaction date range without job picker` (`usfds-web/src/components/modules/reports/ReportScopeToolbar.test.tsx`) | MSW trả dữ liệu report | Chọn `Từ ngày → Đến ngày` | Request `/reports/*` mang `date_from`/`date_to`, không còn bộ chọn phiên `DetectionJob` | ISS-012 |

## 6. Milestones & to-do (checkpoints, not stop points: all tests green at each)

- [x] **M0 — Queue timeout & retry policy (ISS-021)** (`usfds-infra`, `usfds-worker`, `usfds-server`): làm trước vì M2 dựa vào nó cho `QUEUE_ANALYTICS`.
  - [x] [tests] Viết các test M0 trong §5; xác nhận fail đúng lý do
  - [x] [infra] `QueueWaitTimeoutError`; `enqueue_and_wait(attempts, timeout)` hủy job chưa chạy
  - [x] [worker] `_make_processor` phân loại lỗi → `UnrecoverableError`; 2 handler bỏ qua bản ghi ở trạng thái cuối
  - [x] [server] Exception handler `504`; 2 setting timeout; 6 chỗ gọi truyền `timeout_seconds`; `deploy/.env.example`
  - [x] [verify] `./scripts/test.sh infra worker server`
- [x] **M1 — Storage streaming, DuckDB bounded & Project Fact Warehouse** (`usfds-core`, `usfds-infra`): mỗi job ghi 1 file fact, Insight đọc warehouse theo `tx_timestamp`.
  - [x] [tests] Viết các test M1 trong §5; xác nhận fail đúng lý do
  - [x] [core] `IFileStorage.list_keys/open_local_path/upload_file`; `ICaseRepository.get_case_ids_by_events` (chuyển sang M2, nơi duy nhất dùng nó)
  - [x] [infra] Cài đặt trong `LocalFileStorage`, `S3FileStorage`, `SqliteCaseRepository`
  - [x] [core] `services/warehouse/project_warehouse.py`: `create_bounded_duckdb_connection`, `write_job_facts`, `sync_missing_jobs`, `fact_view`
  - [x] [core] `handle_job_completion` gọi `write_job_facts`; viết lại `DuckDBInsightEngine` + `InsightReportService` trên `fact_view` theo `tx_timestamp`
  - [x] [verify] `./scripts/test.sh core infra`
- [x] **M2 — Worker Analytics Queue & DuckDB pushdown cho Detection Results/Export/Send** (`usfds-infra`, `usfds-worker`, `usfds-core`, `usfds-server`)
  - [x] [tests] Viết các test M2 trong §5; xác nhận fail
  - [x] [infra] Append `QUEUE_ANALYTICS`, `JOB_INSIGHT_REPORT`
  - [x] [worker] `enabled_queues`, `handle_insight_report`, đăng ký `ANALYTICS_QUEUE_HANDLERS` (main + testing)
  - [x] [core] `get_detection_job_results`, `export_detection_job_results*`, `fetch_job_events` bằng DuckDB
  - [x] [server] `insight_report_router.py` dispatch qua `QUEUE_ANALYTICS` (`attempts=3`, `analytics_wait_timeout_seconds`); `detection_router.py` stream export + `send_to_investigation` đọc chọn lọc 1 lần; `ingest_request` nhận `source_rows`
  - [x] [verify] `./scripts/test.sh core infra worker server`
- [x] **M3 — UI Insight & Report theo khung thời gian giao dịch** (`usfds-web`)
  - [x] [tests] Viết test M3 trong §5; xác nhận fail
  - [x] [web] `ReportScopeToolbar.tsx`, `InsightReportModule.tsx`, `ExecutiveOverviewTab.tsx`
  - [x] [verify] `./scripts/test.sh core infra worker server web`

Checkpoint log (the agent appends one line per finished milestone):
- 26-11-22 M0 done: infra 47 passed · worker 8 passed · server 44 passed; notes: bỏ `attempts=3` cho training/batch (executor đã ghi `FAILED`, user xác nhận), retry chỉ áp dụng cho `JOB_INSIGHT_REPORT` (M2); handler bỏ qua bản ghi ở trạng thái cuối gồm cả `CANCELLED`; thêm 2 test `attempts/backoff` ở `test_job_queue.py`
- 26-11-22 M1 done: core 166 passed (15 skipped, có sẵn) · infra 48 passed · worker 8 · server 44 · cli 5; notes: không thêm `list_keys`, không compaction; `get_case_ids_by_events` chuyển sang M2; thêm test `test_warehouse_load_filters_by_tx_timestamp_not_job_date`; chưa gộp 34 query `score_calibration`/`threshold_curve` thành single-pass (chỉ đổi nguồn dữ liệu sang warehouse + rule leaderboard bằng SQL)
- 26-11-22 M2 done: core 167 passed (15 skipped, có sẵn) · infra 49 · worker 10 · server 47 · cli 5; notes: thêm `prediction_results.py` (DuckDB cho Results/Export/Fetch events); `export_detection_job_results_to_file` + `FileResponse` stream; `_source_frame(event_ids)` và `ingest_request(source_rows)`; thêm `usfds-worker/tests/test_worker_config.py` và 1 test queue-mode `LookupError → 404`; `InlineJobQueue` ghi `attempts`/`timeout_seconds` để kiểm tra; Behavior profile (`investigation_router.py` dòng gọi `_source_frame` không có `event_ids`) vẫn đọc full file — thuộc ISS-045
- 26-11-22 M3 done: web 39 passed (21 files), build OK, lint chỉ còn cảnh báo có sẵn; notes: KHÔNG đổi trục thời gian `ExecutiveOverviewTab` sang `tx_timestamp` vì `financial_trends` hiện nhóm theo job (`engine.py` trend query) và đổi sang theo ngày cần đổi shape response backend (ngoài plan) → đề xuất follow-up

## 7. Review hotspots (filled in after implementation)
- `usfds-core/src/usfds_core/services/insight_report/engine.py` `_build_unified_transactions_table` (M1): SQL thay cho vòng lặp Python; join Case (case thắng: user, amount, final_action, hợp rule codes, nhãn xác minh) và nhánh `UNION ALL` cho Case không có trong facts. Sai lệch ở đây làm lệch mọi KPI nhưng vẫn qua test nhỏ; được test bởi `test_insight_report_end_to_end_metrics_and_sar_export` và `test_insight_report_api_endpoints_and_exports`.
- `usfds-core/src/usfds_core/services/warehouse/project_warehouse.py` `write_job_facts`/`load_fact_table` (M1): fact ghi 1 lần khi job hoàn tất, job cũ bootstrapped khi đọc (`sync_missing_jobs`); khử trùng `event_id` bằng `QUALIFY` theo `scanned_at DESC, job_id DESC`; lỗi ghi fact chỉ log, không làm hỏng job (`inference_service.handle_job_completion`). Fact cũ không tự cập nhật nếu logic chuẩn hóa đổi.
- `usfds-infra/.../bullmq_queue.py` `enqueue_and_wait` (M0): hủy job `waiting/delayed` khi timeout (`job.remove()`), job `active` để chạy tiếp; lỗi `remove()` coi như không hủy được.
- `usfds-worker/src/usfds_worker/main.py` `_make_processor` + `handlers.py` (M0): `UnrecoverableError` cho lỗi nghiệp vụ; `handle_training_run`/`handle_batch_inference` bỏ qua bản ghi đã ở trạng thái cuối. Retry `attempts=3` chỉ cho analytics vì executor training/batch tự ghi `FAILED` và không ném lỗi.
- `usfds-core/src/usfds_core/services/inference/prediction_results.py` (M2): biểu thức SQL dựng động theo cột có trong file (final_action, triggered_rules dạng JSON/list, score, amount); thứ tự REJECT > REVIEW > ALLOW, `round(score,4)`, `round(amount,2)`; `file_row_number` làm `row_index`. Test: `test_detection_results_pagination_uses_duckdb_without_pandas_full_load`.
- `usfds-server/.../investigation_router.py` `_source_frame(event_ids)` + `ingest_request(source_rows)` và `detection_router.py` export (M2): chỉ đọc đúng các event được chọn; export ghi file tạm rồi stream/upload và dọn thư mục tạm.

## 8. Open questions
- (ISS-021) Mặc định `attempts=3`, backoff 5s; timeout 300s (chung) / 120s (analytics) có phù hợp không?
