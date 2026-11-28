# Module 6 — Project Warehouse, Insight & Compliance Reports
<!-- [26-11-27] Created: As-Built module architecture for ProjectWarehouse (DuckDB) and Insight & Report analytics engine. -->

## 1. Trách nhiệm & Ranh giới
- **Làm gì:**
  - Duy trì lớp dữ liệu phân tích chuẩn hóa theo project (`ProjectWarehouse`): chuyển đổi `predictions.parquet` của mỗi `DetectionJob` hoàn tất thành file fact Parquet append-only, loại trùng theo `event_id` khi đọc.
  - Tính toán các bộ chỉ số phân tích FDS bằng bounded DuckDB (`DuckDBInsightEngine`): Executive Overview (`SUC-22`), Effectiveness Analysis (`SUC-23`), Typology & Patterns (`SUC-24`).
  - Sinh và xuất báo cáo tuân thủ (`ComplianceReportBuilder`, `SUC-25`): SAR Dossier (5 phần), Executive Audit Report ở định dạng `.md`, `.json`, `.csv`, `.html`.
- **KHÔNG làm gì:** Không chỉnh sửa `predictions.parquet`, `fraud_cases`, hay `detection_jobs`; không tải toàn bộ file giao dịch bằng pandas trên API process (`INV-007`). Trong chế độ queue, các truy vấn nặng chạy trên BullMQ queue `usfds-analytics` (`attempts=3`, timeout `120s`).

---

## 2. Data Ownership

| Loại tài nguyên | Sở hữu độc quyền | Lưu ý ranh giới |
|---|---|---|
| **Fact Warehouse** | `warehouse/{project_id}/fact_transactions/job_{job_id}.parquet` | Mỗi `DetectionJob` COMPLETED tương ứng đúng 1 file fact append-only. Đọc qua `ProjectWarehouse.load_fact_table()` (tự động `sync_missing_jobs` nếu có job hoàn tất chưa có fact file). |
| **Report Exports** | `exports/reports/{project_id}/{filename}` | File xuất tạm sinh bởi `insight_report_router.py`, tải qua presigned GET (S3) hoặc streaming response (local). |

---

## 3. Shared Contracts

- **Contract `C5` — Schema 25 cột của `fact_transactions` (`project_warehouse.py:63-70`):**
  - 20 cột chuẩn: `job_id`, `job_name`, `job_created_at`, `scanned_at`, `model_version_id`, `score_threshold`, `event_id`, `user_id`, `tx_timestamp`, `hour_utc`, `amount`, `model_score`, `rule_action`, `final_action`, `is_flagged`, `has_rule_hit`, `has_ai_hit`, `rule_codes VARCHAR[]`, `dataset_label` (`-1|0|1`), `has_label_col BOOLEAN`.
  - 5 cột thực thể tùy chọn: `device_id`, `ip_address`, `card_id`, `merchant_id`, `merchant_category` (tự động bổ sung `NULL` qua `ALTER TABLE` khi đọc fact cũ nhờ `union_by_name=true`).
- **Contract Deduplication & Label Precedence (`DuckDBInsightEngine`):**
  - Dedup giao dịch: `QUALIFY row_number() OVER (PARTITION BY event_id ORDER BY scanned_at DESC, job_id DESC) = 1`.
  - Kết hợp `facts` với `v_cases` (kể cả intake-only cases qua `UNION ALL`) thành view `v_transactions`.
  - Ưu tiên nhãn sự thật: `VERIFIED_CASE` (từ `fraud_cases`) > `DATASET_FALLBACK` (`dataset_label` từ dataset) > `UNVERIFIED`.
- **Contract Bounded DuckDB (`INV-007`):** Mọi kết nối phân tích dùng `create_bounded_duckdb_connection(threads=2, memory_limit="512MB", temp_directory=...)` để tránh OOM khi nhiều truy vấn chạy đồng thời.

---

## 4. State Machine & Critical Flows

```mermaid
flowchart LR
    JOB["DetectionJob\n(COMPLETED)"] -->|"20k-row streaming"| WRITE["ProjectWarehouse\nwrite_job_facts()"]
    WRITE --> FACT["warehouse/{pid}/\nfact_transactions/\njob_{jid}.parquet"]
    FACT -->|"read_parquet(union_by_name)\n+ QUALIFY latest event_id"| VIEW["DuckDBInsightEngine\nv_transactions"]
    CASES["fraud_cases\n(v_cases)"] --> VIEW
    VIEW --> METRICS["Overview / Effectiveness\n/ Patterns / Simulator"]
    VIEW --> EXP["ComplianceReportBuilder\n(SAR / Executive Audit\n.md .json .csv .html)"]
```

---

## 5. Known Gotchas & Code/Spec Map
- **Bẫy 1 (Công thức FDS & HTML Export, `ISS-046` đã resolved):** Các chỉ số (`insult_rate`, `verified_fpr`, `VDR`, `Missed Fraud $`, `REJECT` vs `REVIEW`, Case SLA/MTTR, Calibration Brier/ECE, Dual-Threshold Simulator, Model Comparison + PSI) và HTML/Print-to-PDF export đã được chuẩn hóa trong `insight_report/{engine,report_builder}.py` — mọi chỉnh sửa công thức cần giữ bất biến `INV-013`.
- **Bẫy 2 (Chuẩn hóa `dataset_label`, `ISS-047` đã resolved):** `ProjectWarehouse._copy_normalized` sử dụng chung `domain/schemas/label_normalization.py` để đồng bộ nhãn chuỗi/nhị phân với `DataMappingService` và `RuleExecutor`.
- **Bẫy 3 (Queue Retry):** `insight_report` là job duy nhất cấu hình `attempts=3` (vì lỗi đọc S3/DuckDB tạm thời có thể retry an toàn do thao tác chỉ đọc), nhưng mọi `ValueError`/`LookupError` vẫn bị chặn retry nhờ `UnrecoverableError`.
- **Code chính:** `usfds-core/src/usfds_core/services/{warehouse,insight_report}/`, `usfds-server/src/usfds_server/routers/insight_report_router.py`, `usfds-worker/src/usfds_worker/handlers.py` (`handle_insight_report`).
- **Spec:** [`docs/features/insight_report/suc-spec.md`](../../features/insight_report/suc-spec.md).
