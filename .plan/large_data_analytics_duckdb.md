# Plan: Tối ưu xử lý dữ liệu lớn bằng DuckDB, Unified Project Fact Warehouse & Worker Analytics Queue

> **Task ID:** `large_data_analytics_duckdb` · **Issues:** ISS-012 (chosen by the user) · **Spec:** `docs/features/insight_report/suc-spec.md`, `docs/features/detection/inference/suc-spec.md`, `docs/features/investigation/suc-spec.md`
> **Conflict verdict:** PARALLEL-SAFE · **Status:** Draft

## 1. Context (facts)
- **Insight & Report đọc rời rạc `N` file Parquet bằng pandas và lặp từng dòng Python trong API process:**
  - `usfds-core/src/usfds_core/services/insight_report/engine.py:126-256` (`DuckDBInsightEngine._build_unified_transactions_df`): trên mỗi request API, hàm đọc toàn bộ `predictions.parquet` của mọi `DetectionJob` `COMPLETED` qua `read_bytes()`, giải mã toàn bộ cột (kể cả hàng chục cột đặc trưng và `raw_attributes`, `triggered_rule_details`) bằng `pd.read_parquet(io.BytesIO(raw_bytes))`, gọi `df.to_dict(orient="records")` (dòng 178), duyệt từng dòng Python, dựng lại `pd.DataFrame(rows)` (dòng 306) rồi mới đăng ký `v_transactions` vào DuckDB.
  - `engine.py:607-641, 673-687, 712-723, 853-879`: lặp `self._tx_df.itertuples(index=False)` trong Python cho `rule_leaderboard` và chạy 34 câu query rời rạc cho `score_calibration`, `threshold_curve`, `amount_brackets`.
  - `usfds-core/src/usfds_core/services/insight_report/service.py:103-120`: bộ lọc `date_from` / `date_to` đang lọc theo `job.created_at` (thời điểm bấm chạy batch job) thay vì `tx_timestamp` (thời gian phát sinh giao dịch), và `ReportScopeToolbar.tsx:36-54` đang tách chọn theo từng phiên batch rời rạc thay vì phân tích trên nguồn dữ liệu hợp nhất của dự án theo mọi khung thời gian giao dịch.
- **DuckDB chưa được giới hạn tài nguyên (RAM/CPU) và chưa tách queue trên `usfds-worker`:**
  - `usfds-core/src/usfds_core/services/insight_report/engine.py:121` gọi `duckdb.connect(":memory:")` với cấu hình mặc định (chiếm tối đa 80% RAM hệ thống và toàn bộ CPU cores).
  - `usfds-worker/src/usfds_worker/main.py:102-118` chạy chung `QUEUE_TRAINING`, `QUEUE_BATCH_INFERENCE`, `QUEUE_DATA_PIPELINE` trong một tiến trình và chưa có `QUEUE_ANALYTICS` hay biến môi trường `USFDS_WORKER_QUEUES` để tách worker theo nhóm queue khi cần.
- **Detection Results, Export & Send-to-Investigation nạp toàn bộ file vào pandas:**
  - `usfds-core/src/usfds_core/services/inference/inference_service.py:795-957` (`get_detection_job_results`): `_load_job_predictions_df` nạp toàn bộ `predictions.parquet` vào pandas, `case_repo.list_by_project` nạp toàn bộ Case của dự án, `df.to_dict(orient="records")` duyệt mọi dòng để lọc/sort trong Python rồi mới cắt `[offset : offset + limit]`.
  - `inference_service.py:965-989` & `usfds-server/src/usfds_server/routers/detection_router.py:215-260`: export CSV hoặc `only_flagged=True` nạp toàn bộ Parquet vào pandas và giữ toàn bộ `file_bytes` trong RAM.
  - `detection_router.py:268-324` (`send_to_investigation`): gọi `_source_frame` (dòng 281) nạp toàn bộ `predictions.parquet` lần 1, rồi gọi `ingest_request` (dòng 314) làm nạp lại toàn bộ `predictions.parquet` lần 2 (`investigation_router.py:102`).
- **Investigation Intake & Workbench nạp toàn bộ file nguồn vào pandas:**
  - `usfds-server/src/usfds_server/routers/investigation_router.py:51-87, 100-131, 176-191` và `usfds-core/src/usfds_core/services/investigation/behavior_profile.py:8-51` nạp toàn bộ CSV/Parquet vào pandas và copy toàn bảng trước khi lọc theo `user_id` và cửa sổ 30/90 ngày.
- **Tầng Storage (`IFileStorage`) chỉ có `read_bytes`/`save_bytes` (`base_storage.py:6-53`):** chưa có `open_local_path` / `upload_file` để DuckDB đọc trực tiếp từ đĩa hoặc stream qua file tạm từ S3.

## 2. Goal, scope verdict & non-goals
- **Goal:** (1) Hợp nhất dữ liệu giao dịch đã quét từ các phiên `DetectionJob` vào một nguồn dữ liệu phân tích chuẩn hóa duy nhất theo dự án (`warehouse/{project_id}/fact_transactions.parquet`) ngay khi job hoàn tất trên worker; (2) Thực thi các truy vấn OLAP của `Insight & Report` theo mọi khung thời gian giao dịch (`tx_timestamp`) trên `usfds-worker` qua `QUEUE_ANALYTICS` với kết nối DuckDB giới hạn cứng RAM/CPU (`threads`, `memory_limit`, `temp_directory`); (3) Chuyển `Detection Results/Export/Send-to-Investigation` và `Investigation Intake/Workbench` sang truy vấn/stream chọn lọc bằng DuckDB thay vì nạp toàn bộ file vào pandas.
- **Scope:** OK (theo Lựa chọn 1 user đã chốt; phần chuyển các bước `Data Management` từ pandas sang DuckDB sẽ được ghi nhận vào issue mới `ISS-042`).
- **Non-goals / omitted:**
  - Không chuyển các bước `Data Management` (`DatasetIngestionService`, `DataProfilingService`, `DataMappingService`, `DataQualityValidationService`, `VelocityFeatureEngineer`) sang DuckDB trong task này (tách thành `ISS-042`).
  - Không nhúng `@duckdb/duckdb-wasm` lên trình duyệt (đặt compute tại `usfds-worker`).
  - Không thay đổi bước tiền xử lý ML (`scikit-learn` / `imblearn` `preprocessor.joblib`) hoặc thuật toán huấn luyện mô hình.
- **Assumptions:**
  - Kết nối DuckDB được khởi tạo qua helper chung `create_bounded_duckdb_connection(threads=2, memory_limit="512MB")` kèm `temp_directory` để tự động spill ra đĩa, bảo vệ tuyệt đối tiến trình `usfds-worker` khi có job Training chạy cùng container.
  - `usfds-worker` hỗ trợ biến môi trường `USFDS_WORKER_QUEUES` (mặc định bật cả 4 queue `training,batch_inference,data_pipeline,analytics` cho demo 1 container, và cho phép tách container ML vs. Data/Analytics khi cần).
  - Nếu một dự án đã có các `DetectionJob` `COMPLETED` cũ từ trước khi có file `warehouse/{project_id}/fact_transactions.parquet`, `DuckDBInsightEngine` tự động bootstrap/đồng bộ các job còn thiếu vào `fact_transactions.parquet` bằng DuckDB (không dùng `pd.read_parquet`) để tương thích ngược 100% với dữ liệu và test hiện có.
  - Trên UI `ReportScopeToolbar.tsx`, bỏ bộ chọn theo từng phiên (`DetectionJob`), giữ bộ lọc khung thời gian giao dịch (`Từ ngày → Đến ngày`) và nút chọn nguồn nhãn chuẩn (`BR-IR-02`); ở backend vẫn chấp nhận tham số `job_ids` tùy chọn để không làm gãy bất kỳ API test cũ nào.

## 3. Files
| Action | File | Milestone | Note |
|---|---|---|---|
| modify | `usfds-core/src/usfds_core/storage/base_storage.py` | M1 | Thêm `open_local_path` context manager & `upload_file` |
| modify | `usfds-infra/src/usfds_infra/storage/local_storage.py` | M1 | Override `open_local_path` (trả `Path` trực tiếp, zero-copy) & `upload_file` |
| modify | `usfds-infra/src/usfds_infra/storage/s3_storage.py` | M1 | Override `open_local_path` (`download_file` vào file tạm) & `upload_file` |
| modify | `usfds-core/src/usfds_core/repositories/base_case_repo.py` | M1 | Thêm `get_case_ids_by_events(project_id, event_ids)` |
| modify | `usfds-infra/src/usfds_infra/database/case_repositories.py` | M1 | Override `get_case_ids_by_events` bằng SQL `IN` tương thích PostgreSQL |
| modify | `usfds-core/src/usfds_core/services/insight_report/engine.py` | M1 | Thêm `create_bounded_duckdb_connection`, `ProjectWarehouseBuilder` (`warehouse/{project_id}/fact_transactions.parquet`), viết lại `DuckDBInsightEngine` đọc từ warehouse + lọc theo `tx_timestamp` + single-pass SQL |
| modify | `usfds-core/src/usfds_core/services/insight_report/service.py` | M1 | Lọc theo `tx_timestamp` của giao dịch & điều phối đọc từ Unified Warehouse |
| modify | `usfds-core/src/usfds_core/services/inference/inference_service.py` | M1, M2 | Đồng bộ kết quả job hoàn tất vào `warehouse/{project_id}/fact_transactions.parquet` (M1); chuyển `get_detection_job_results`, `export_detection_job_results*` và `fetch_detection_events_for_intake` sang DuckDB (M2) |
| modify | `usfds-infra/tests/test_s3_storage.py` | M1 | Test `open_local_path` & `upload_file` trên `LocalFileStorage` và `S3FileStorage` (moto) |
| modify | `usfds-infra/tests/test_case_repositories.py` | M1 | Test `get_case_ids_by_events` dưới `pg_compat` guard |
| modify | `usfds-core/tests/test_insight_report_service.py` | M1 | Acceptance tests cho Unified Warehouse, DuckDB resource cap, lọc theo `tx_timestamp`, không gọi `pd.read_parquet` |
| modify | `usfds-infra/src/usfds_infra/job_queue/bullmq_queue.py` | M2 | Append `QUEUE_ANALYTICS`, `JOB_INSIGHT_REPORT` (hot-spot: append-only) |
| modify | `usfds-infra/src/usfds_infra/job_queue/__init__.py` | M2 | Export `QUEUE_ANALYTICS`, `JOB_INSIGHT_REPORT` |
| modify | `usfds-worker/src/usfds_worker/config.py` | M2 | Thêm `enabled_queues` (`USFDS_WORKER_QUEUES`) |
| modify | `usfds-worker/src/usfds_worker/handlers.py` | M2 | Thêm `handle_insight_report` thực thi truy vấn/export `InsightReportService` trên worker |
| modify | `usfds-worker/src/usfds_worker/main.py` | M2 | Append `ANALYTICS_QUEUE_HANDLERS` và lọc worker theo `settings.enabled_queues` (hot-spot: append-only) |
| modify | `usfds-worker/src/usfds_worker/testing.py` | M2 | Đăng ký `QUEUE_ANALYTICS: ANALYTICS_QUEUE_HANDLERS` trong `InlineJobQueue` |
| modify | `usfds-server/src/usfds_server/routers/insight_report_router.py` | M2 | Khi `settings.dispatch_backend == "queue"`, đẩy truy vấn qua `QUEUE_ANALYTICS` (`JOB_INSIGHT_REPORT`) tới `usfds-worker` |
| modify | `usfds-server/src/usfds_server/routers/detection_router.py` | M2 | Stream file export từ DuckDB và truy vấn chọn lọc `event_ids` cho `send_to_investigation` |
| modify | `usfds-core/tests/test_inference_service.py` | M2 | Acceptance tests cho `get_detection_job_results` & export bằng DuckDB |
| modify | `usfds-server/tests/test_detection_api.py` | M2 | Acceptance tests cho export streaming & `send-to-investigation` không nạp full file |
| modify | `usfds-server/tests/test_insight_report_api.py` | M2 | Acceptance test chạy `/api/v1/reports/*` ở `client_queue_mode` qua `QUEUE_ANALYTICS` |
| modify | `usfds-core/src/usfds_core/services/investigation/behavior_profile.py` | M3 | Thêm `build_behavior_profile_from_file` & `fetch_source_events_by_ids` bằng DuckDB |
| modify | `usfds-server/src/usfds_server/routers/investigation_router.py` | M3 | Dùng DuckDB selective query trong `ingest_request` và `workbench` thay cho `_source_frame` |
| modify | `usfds-web/src/components/modules/reports/ReportScopeToolbar.tsx` | M3 | Bỏ bộ chọn phiên `DetectionJob`, chuyển sang lọc theo khung thời gian giao dịch (`Từ ngày → Đến ngày`) |
| modify | `usfds-web/src/components/modules/InsightReportModule.tsx` | M3 | Gỡ truy vấn `detection-jobs` dư thừa khỏi `ReportScopeToolbar` |
| modify | `usfds-web/src/components/modules/reports/ExecutiveOverviewTab.tsx` | M3 | Cập nhật mô tả/trục thời gian biểu đồ xu hướng tài chính theo thời gian giao dịch |
| modify | `usfds-core/tests/test_cases.py` | M3 | Acceptance tests cho `build_behavior_profile_from_file` (Parquet & CSV) |
| modify | `usfds-server/tests/test_investigation_api.py` | M3 | Acceptance tests cho `ingest_request` & `workbench` không gọi `pd.read_parquet`/`pd.read_csv` |

## 4. Dependencies & conflicts (with other tasks on BOARD)
| # | Check | Answer |
|---|---|---|
| D1 | Needs unfinished task? | No (toàn bộ task trên `.plan/BOARD.md` đã `Done`) |
| D2 | Needed by unfinished task? | No |
| C1 | Modified files owned by in-progress task? | No (không có task `In progress` trên `.plan/BOARD.md`) |
| C2 | Hot-spot files touched | `usfds-infra/src/usfds_infra/job_queue/bullmq_queue.py`, `usfds-worker/src/usfds_worker/main.py` (append-only) |
| C3 | Schema change | No |
| C4 | Public contract change | No breaking change: giữ nguyên URL & response structure của `/api/v1/reports/*`, `/api/v1/detection/*`, `/api/v1/cases/*`; `date_from`/`date_to` lọc chính xác theo `tx_timestamp` |
| C5 | Shared UI shell change | No (chỉ sửa component con trong `src/components/modules/reports/` và `InsightReportModule.tsx`) |

## 5. Acceptance tests (user reviews this section)
| Milestone | Test | Given | When | Then | Covers |
|---|---|---|---|---|---|
| M1 | `test_storage_open_local_path_zero_copy_local_and_streaming_s3` (`usfds-infra/tests/test_s3_storage.py`) | File Parquet lưu trong `LocalFileStorage` và `S3FileStorage` (moto) | Gọi `storage.open_local_path(key)` và `storage.upload_file(tmp_src, dest_key)` | `LocalFileStorage` trả `Path` gốc không copy; `S3FileStorage` stream qua temp file và tự dọn file tạm khi thoát block `with` | ISS-012 |
| M1 | `test_case_repo_get_case_ids_by_events_is_pg_compatible` (`usfds-infra/tests/test_case_repositories.py`) | DB có nhiều Case thuộc các project khác nhau | Gọi `SqliteCaseRepository(session).get_case_ids_by_events(project_id, ["EV-1", "EV-MISSING"])` dưới `pg_compat` guard | Trả đúng `{"EV-1": case_id}` của project đó và không lỗi `PostgresCompatibilityError` | ISS-012 |
| M1 | `test_unified_warehouse_merges_jobs_filters_by_tx_timestamp_without_pandas` (`usfds-core/tests/test_insight_report_service.py`) | Hai `DetectionJob` `COMPLETED` quét các giao dịch ở các ngày `tx_timestamp` khác nhau (có `event_id` trùng được quét lại ở job sau); `pd.read_parquet` bị monkeypatch ném `AssertionError` | Đồng bộ vào `warehouse/{project_id}/fact_transactions.parquet` và gọi `get_executive_overview`, `get_effectiveness_analysis`, `get_typology_and_patterns` với bộ lọc `date_from` / `date_to` theo ngày giao dịch | File `warehouse/{project_id}/fact_transactions.parquet` được tạo, khử trùng lặp `event_id` (lần quét mới nhất thắng), lọc đúng các giao dịch nằm trong `[date_from, date_to]` theo `tx_timestamp`, kết nối DuckDB bị khóa trần `threads=2` & `memory_limit`, không gọi `pd.read_parquet` | ISS-012 |
| M2 | `test_insight_report_runs_on_analytics_worker_queue_in_queue_mode` (`usfds-server/tests/test_insight_report_api.py`) | Server ở chế độ `client_queue_mode` (`dispatch_backend == "queue"`) với dữ liệu `DetectionJob` và `Case` | Gọi `GET /api/v1/reports/overview`, `/effectiveness`, `/patterns`, `/executive-summary`, `/export` | Các request được ủy quyền qua `QUEUE_ANALYTICS` (`JOB_INSIGHT_REPORT`) tới `usfds-worker` và trả kết quả chính xác; `WorkerSettings` hỗ trợ lọc danh sách queue qua `USFDS_WORKER_QUEUES` | ISS-012 |
| M2 | `test_detection_results_pagination_uses_duckdb_without_pandas_full_load` (`usfds-core/tests/test_inference_service.py`) | `DetectionJob` `COMPLETED` có 100 bản ghi trong `predictions.parquet` và Case đã gán cho một số `event_id`; `pd.read_parquet` bị monkeypatch ném `AssertionError` | Gọi `get_detection_job_results` với `action_filter="FLAGGED"`, `rule_code`, `search`, `min_score`/`max_score`, `limit=10`, `offset=5` | Trả đúng `total_filtered`, thứ tự ưu tiên (`REJECT` > `REVIEW` > `ALLOW`, `model_score DESC`), đúng 10 dòng của trang kèm `case_id` mà không gọi `pd.read_parquet` | ISS-012 |
| M2 | `test_detection_export_and_send_to_investigation_use_duckdb_without_full_frame_load` (`usfds-server/tests/test_detection_api.py`) | `DetectionJob` `COMPLETED` có giao dịch flagged và allow; `pd.read_parquet` bị monkeypatch ném `AssertionError` | Gọi `GET /api/v1/detection/jobs/{job_id}/export?only_flagged=true&file_format=csv` và `POST /api/v1/detection/jobs/{job_id}/send-to-investigation` | Export stream đúng các dòng flagged; `send-to-investigation` chỉ đọc các `event_ids` được chọn 1 lần qua DuckDB để tạo Case (và từ chối `400` nếu event không flagged/không tồn tại) mà không gọi `pd.read_parquet` | ISS-012 |
| M3 | `test_behavior_profile_from_parquet_and_csv_matches_window_and_cold_start` (`usfds-core/tests/test_cases.py`) | File nguồn Parquet và CSV có giao dịch trong/ngoài cửa sổ 30 & 90 ngày, cột tùy chọn (`device_id`, `merchant_category`) và Case cho cả user cũ lẫn user cold-start | Gọi `build_behavior_profile_from_file` | Kết quả `avg_amount`, `max_amount`, `common_hours_utc`, `comparison`, `timeline`, `source` (`USER` vs `POPULATION`) khớp chính xác mà không nạp toàn bảng vào pandas | ISS-012 |
| M3 | `test_investigation_intake_and_workbench_query_source_without_pandas_full_load` (`usfds-server/tests/test_investigation_api.py`) | Artifact `MAPPED` và Case đã tạo; `pd.read_parquet` & `pd.read_csv` bị monkeypatch ném `AssertionError` | Gọi `ingest_request` và `GET /api/v1/cases/{case_id}/workbench?project_id=...&days=30` | `ingest_request` tạo Case hợp lệ (báo `400` khi snapshot sai) và `workbench` trả profile + timeline đầy đủ mà không gọi `pd.read_parquet` / `pd.read_csv` | ISS-012 |

## 6. Milestones & to-do (checkpoints, not stop points: all tests green at each)

- [ ] **M1 — Resource-bounded DuckDB, Storage streaming & Unified Project Fact Warehouse** (`usfds-core`, `usfds-infra`): Hợp nhất dữ liệu các phiên quét vào `warehouse/{project_id}/fact_transactions.parquet`, giới hạn RAM/CPU cho DuckDB và lọc theo `tx_timestamp`.
  - [ ] [tests] Viết các test M1 trong §5 (`test_s3_storage.py`, `test_case_repositories.py`, `test_insight_report_service.py`); xác nhận fail trước khi sửa
  - [ ] [core] Thêm `open_local_path` & `upload_file` vào `IFileStorage` (`base_storage.py`); thêm `get_case_ids_by_events` vào `ICaseRepository` (`base_case_repo.py`)
  - [ ] [infra] Cài đặt `open_local_path` & `upload_file` trong `LocalFileStorage`, `S3FileStorage`; cài đặt `get_case_ids_by_events` trong `SqliteCaseRepository`
  - [ ] [core] Tạo `create_bounded_duckdb_connection` và `ProjectWarehouseBuilder` (`warehouse/{project_id}/fact_transactions.parquet`); tích hợp đồng bộ warehouse khi `DetectionJob` hoàn tất và viết lại `DuckDBInsightEngine` + `InsightReportService` lọc theo `tx_timestamp`
  - [ ] [verify] `./scripts/test.sh core infra`
- [ ] **M2 — Worker Analytics Queue (`QUEUE_ANALYTICS`) & DuckDB pushdown cho Detection Results/Export/Dispatch** (`usfds-core`, `usfds-infra`, `usfds-worker`, `usfds-server`): Đưa compute `Insight & Report` sang `usfds-worker` ở chế độ queue, hỗ trợ `USFDS_WORKER_QUEUES`, và đẩy truy vấn/export của `DetectionJob` xuống DuckDB.
  - [ ] [tests] Viết các test M2 trong §5 (`test_insight_report_api.py`, `test_inference_service.py`, `test_detection_api.py`); xác nhận fail trước khi sửa
  - [ ] [infra] Append `QUEUE_ANALYTICS` và `JOB_INSIGHT_REPORT` vào `bullmq_queue.py` & `job_queue/__init__.py`
  - [ ] [worker] Thêm `enabled_queues` (`USFDS_WORKER_QUEUES`) vào `worker/config.py`, `handle_insight_report` vào `worker/handlers.py`, đăng ký `ANALYTICS_QUEUE_HANDLERS` trong `worker/main.py` và `worker/testing.py`
  - [ ] [core] Viết lại `InferenceService.get_detection_job_results`, `export_detection_job_results*` và `fetch_detection_events_for_intake` bằng DuckDB
  - [ ] [server] Cập nhật `insight_report_router.py` (dispatch qua `QUEUE_ANALYTICS` khi `dispatch_backend == "queue"`) và `detection_router.py` (stream export + `send_to_investigation` đọc chọn lọc 1 lần)
  - [ ] [verify] `./scripts/test.sh core infra worker server`
- [ ] **M3 — DuckDB pushdown cho Investigation Intake/Workbench & Cập nhật UI Insight & Report theo khung thời gian** (`usfds-core`, `usfds-server`, `usfds-web`): Loại bỏ `_source_frame` full-file pandas và bỏ bộ chọn phiên trên `ReportScopeToolbar.tsx`.
  - [ ] [tests] Viết các test M3 trong §5 (`test_cases.py`, `test_investigation_api.py`); xác nhận fail trước khi sửa
  - [ ] [core] Thêm `build_behavior_profile_from_file` và `fetch_source_events_by_ids` dùng DuckDB trong `behavior_profile.py`
  - [ ] [server] Cập nhật `ingest_request` và `workbench` trong `investigation_router.py` dùng DuckDB helpers
  - [ ] [web] Cập nhật `ReportScopeToolbar.tsx`, `InsightReportModule.tsx`, `ExecutiveOverviewTab.tsx` bỏ chọn theo phiên `DetectionJob`, phân tích theo khung thời gian giao dịch
  - [ ] [verify] `./scripts/test.sh core infra worker server web`

Checkpoint log (the agent appends one line per finished milestone):
- —

## 7. Review hotspots (filled in after implementation)
- —

## 8. Open questions
- — (Đã chốt Lựa chọn 1 với user: hợp nhất dữ liệu vào `warehouse/{project_id}/fact_transactions.parquet`, chạy compute phân tích trên `usfds-worker` qua `QUEUE_ANALYTICS` với DuckDB khóa trần RAM/CPU, bỏ chọn theo phiên trên UI `Insight & Report`, và tách phần chuyển đổi `Data Management` sang issue mới `ISS-042`).
