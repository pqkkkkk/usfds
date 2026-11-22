# Plan: Redesign Investigation Flow (Drop Assign/Claim) & DuckDB Workbench on Project Warehouse

> **Task ID:** `investigation_redesign` · **Issues:** ISS-045 · **Spec:** `docs/features/investigation/suc-spec.md` (SUC-17, SUC-18 — cập nhật `[26-11-22]`)
> **Conflict verdict:** PARALLEL-SAFE · **Status:** Done (26-11-22)

## 1. Context (facts)
- **Không có vai trò Fraud Manager:** `seed_rbac.py:78-84, 118-171` chỉ có `project_admin` giữ `case:assign` (`seed_rbac.py:120`) và `fraud_analyst` giữ `case:claim`, `case:manual_review`, `case:escalate`, `case:reopen` (`seed_rbac.py:159-165`). Người chạy detection cũng là người gửi Case và tự mở Workbench.
- **Logic Assign/Claim/Escalate chồng chéo:**
  - `investigation_router.py:232-237` (`claim`) kiểm tra quyền `case:assign` nếu `request.assignee` khác `actor`, ngược lại kiểm tra `case:claim`, nhưng `CaseService.update` (`case_service.py:121-129`) luôn gán `case.assigned_to = actor` và khóa khi `assigned_to != actor`.
  - `CaseService.update` hành động `escalate` (`case_service.py:134-137`) bắt buộc `assignee` rồi gán `case.assigned_to = assignee.strip()`.
  - `assigned_to` lan sang `Case` (`case.py:57`), `CaseModel` (`case_models.py:31`), `CaseResponse` / `CaseActionRequest` (`investigation_api_schemas.py:100, 115`), `SqliteCaseRepository._search_query` (`case_repositories.py:79-83`), `ReportBuilder.build_sar_dossier` / `format_sar_markdown` (`report_builder.py:176, 290`), `ComplianceReportCenterTab.tsx:276-279`, `CaseQueueView.tsx:39, 76-79, 246-255, 347, 405-425`, `WorkbenchResolutionColumn.tsx:219-264, 440-465`, `WorkbenchPanels.tsx:85-90, 206`, `CaseWorkbenchView.tsx:75-81`, và `feature-policy.ts:87-88` (`claimCase`, `assignCase`).
- **Workbench nạp toàn bộ file nguồn vào pandas:**
  - `investigation_router.py:52-92, 182-190` gọi `_source_frame(session, storage, project_id, case.dataset_artifact_id, case.detection_job_id)` không truyền `event_ids`, đọc toàn bộ CSV/Parquet vào pandas rồi truyền sang `build_behavior_profile` (`behavior_profile.py:8-51`), nơi thực hiện `frame.copy()` rồi mới lọc `user_id` và cửa sổ 30/90 ngày.
- **Nền warehouse `ISS-012` đã merge nhưng thiếu 5 cột thực thể phụ:** `ProjectWarehouse` (`project_warehouse.py:35-41`) chuẩn hóa 20 cột fact trong `warehouse/{project_id}/fact_transactions/job_{job_id}.parquet`, chưa lưu 5 cột thực thể mà `behavior_profile.py:33` đang đối chiếu (`device_id`, `ip_address`, `card_id`, `merchant_id`, `merchant_category`).

## 2. Goal, scope verdict & non-goals
- **Goal:** (1) Bỏ hoàn toàn luồng Assign/Claim (`case:assign`, `case:claim`, endpoint `/claim`, cột `fraud_cases.assigned_to` qua Alembic migration) và đổi `escalate` thành chỉ nâng `priority = CRITICAL` kèm lý do (không cần `assignee`); (2) Bổ sung 5 cột thực thể phụ nullable vào `ProjectWarehouse` và chuyển Workbench (behavior profile + timeline) sang truy vấn DuckDB bounded trên warehouse, không nạp full file bằng pandas.
- **Scope:** OK
- **Non-goals / omitted:**
  - Không đổi hành vi `Send to Investigation` (đã đọc chọn lọc bằng DuckDB ở `ISS-012`).
  - Không chuyển quyền `case:*` sang `GrantScope.OWN` (Case thuộc hàng đợi dùng chung cấp `PROJECT`).
  - Không triển khai Graph exploration `SUC-19` (`ISS-041`) hay gộp file (compaction) warehouse.
  - Không đẩy Workbench sang `QUEUE_ANALYTICS` worker (truy vấn theo 1 `user_id` trong cửa sổ 30/90 ngày bằng DuckDB bounded trực tiếp là đủ nhanh, tránh thêm độ trễ round-trip).
- **Assumptions:**
  - Giữ `CaseStatus.IN_PROGRESS` trong enum và check constraint để tương thích ngược dữ liệu cũ và trạng thái sau `reopen`.
  - File fact Parquet cũ thiếu 5 cột thực thể phụ vẫn đọc được (`load_fact_table` tự chuẩn hóa/bổ sung cột `VARCHAR` `NULL` nếu thiếu sau `read_parquet(..., union_by_name = true)`).
  - Case cũ tạo trực tiếp từ `dataset_artifact_id` (chưa có `DetectionJob` trong warehouse) fallback sang DuckDB bounded đọc trực tiếp file artifact qua `storage.open_local_path`, không dùng `pd.read_parquet` / `pd.read_csv`.
  - `seed_rbac` xóa idempotent `case:assign` và `case:claim` khỏi DB (tương tự cơ chế xóa `rule:propose` tại `seed_rbac.py:187-196`).

## 3. Files
| Action | File | Milestone | Note |
|---|---|---|---|
| modify | `usfds-core/src/usfds_core/domain/entities/case.py` | M1 | Bỏ `assigned_to` khỏi `Case` |
| modify | `usfds-core/src/usfds_core/services/investigation/case_service.py` | M1 | Bỏ `claim`, `assignee`, `assigned_to`; `escalate` chỉ nâng `CRITICAL` + lý do; `update` trả `Case` |
| modify | `usfds-core/src/usfds_core/services/warehouse/project_warehouse.py` | M1 | Thêm 5 cột thực thể phụ nullable vào `FACT_COLUMNS_DDL`/`_copy_normalized` + tương thích file fact cũ ở `load_fact_table` |
| modify | `usfds-core/src/usfds_core/services/investigation/behavior_profile.py` | M1 | Bổ sung `build_behavior_profile_from_warehouse` & `build_behavior_profile_from_storage_file` bằng DuckDB bounded |
| modify | `usfds-core/src/usfds_core/services/insight_report/report_builder.py` | M1 | Bỏ `assigned_to` khỏi SAR JSON & Markdown, giữ `resolved_by` |
| modify | `usfds-infra/src/usfds_infra/database/case_models.py` | M1 | Bỏ cột `assigned_to` khỏi `CaseModel` |
| migration | `usfds-infra/src/usfds_infra/database/migrations/versions/<rev>_drop_case_assigned_to.py` | M1 | `batch_alter_table("fraud_cases")` drop cột `assigned_to` |
| modify | `usfds-infra/src/usfds_infra/database/case_repositories.py` | M1 | Bỏ filter `assigned_to`/`unassigned` khỏi `_search_query` |
| modify | `usfds-infra/src/usfds_infra/database/seed_rbac.py` | M1 | Bỏ `case:assign`, `case:claim` khỏi catalog & role grants; dọn idempotent trong `seed_rbac` |
| modify | `usfds-core/tests/test_cases.py` | M1 | Cập nhật test lifecycle cũ bỏ `claim`; thêm test escalate + behavior profile DuckDB |
| modify | `usfds-core/tests/test_project_warehouse.py` | M1 | Test 5 cột thực thể phụ + đọc file fact cũ thiếu cột |
| modify | `usfds-core/tests/test_insight_report_service.py` | M1 | Test SAR bỏ `assigned_to`, dùng `resolved_by` |
| modify | `usfds-infra/tests/test_case_repositories.py` | M1 | Test repo hoạt động không còn `assigned_to` dưới `pg_compat` |
| modify | `usfds-infra/tests/test_auth_repositories.py` | M1 | Cập nhật assert bỏ `case:claim`, thêm test `seed_rbac` xóa quyền cũ |
| modify | `usfds-server/src/usfds_server/schemas/investigation_api_schemas.py` | M2 | Bỏ `assigned_to` khỏi `CaseResponse`, bỏ `assignee` khỏi `CaseActionRequest` |
| modify | `usfds-server/src/usfds_server/routers/investigation_router.py` | M2 | Bỏ `/claim`, param `assigned_to`/`unassigned`, `related_assignees`; `workbench` gọi `ProjectWarehouse` + DuckDB |
| modify | `usfds-server/tests/test_investigation_api.py` | M2 | Cập nhật test API bỏ `/claim`; thêm test `escalate` không assignee & workbench DuckDB không nạp pandas full |
| modify | `usfds-server/tests/test_auth_and_rbac_api.py` | M2 | Cập nhật assert quyền bỏ `case:claim`/`case:assign` |
| modify | `usfds-server/tests/test_insight_report_api.py` | M2 | Cập nhật assert SAR bỏ `assigned_to` nếu có |
| modify | `usfds-web/src/lib/feature-policy.ts` | M3 | Bỏ `claimCase`, `assignCase` khỏi `ACTOR_FEATURE` |
| modify | `usfds-web/src/types/investigation.ts` | M3 | Bỏ `assigned_to` ở `Case`, `assignee` ở `CaseAction` |
| modify | `usfds-web/src/types/insightReport.ts` | M3 | Bỏ `assigned_to` ở `SarDossier` |
| modify | `usfds-web/src/api/investigationApi.ts` | M3 | Cập nhật kiểu trả về của `action` (chỉ `{ case: Case }`) |
| modify | `usfds-web/src/components/modules/investigation/CaseQueueView.tsx` | M3 | Bỏ filter Phân công, cột Assignee, nút Nhận xử lý |
| modify | `usfds-web/src/components/modules/investigation/WorkbenchResolutionColumn.tsx` | M3 | Bỏ Claim, Assign và ô nhập assignee khi Escalate |
| modify | `usfds-web/src/components/modules/investigation/WorkbenchPanels.tsx` | M3 | Bỏ hiển thị `assigned_to` ở cột trái và danh sách hồ sơ liên quan |
| modify | `usfds-web/src/components/modules/investigation/CaseWorkbenchView.tsx` | M3 | Bỏ xử lý thông báo `related_assignees` |
| modify | `usfds-web/src/components/modules/reports/ComplianceReportCenterTab.tsx` | M3 | Hiển thị `resolved_by` thay `assigned_to / resolved_by` |
| modify | `usfds-web/src/lib/feature-policy.test.ts` | M3 | Cập nhật fixture/test bỏ `case:claim` |
| modify | `usfds-web/src/hooks/useActorContext.test.tsx` | M3 | Cập nhật fixture/test bỏ `case:claim` |
| modify | `usfds-web/src/test/featureVisibilityModules.test.tsx` | M3 | Cập nhật fixture/test bỏ `case:claim`, `case:assign` |
| create | `usfds-web/src/components/modules/investigation/CaseWorkflow.test.tsx` | M3 | Test Vitest + MSW cho `CaseQueueView` & `WorkbenchResolutionColumn` |

## 4. Dependencies & conflicts (with other tasks on BOARD)
| # | Check | Answer |
|---|---|---|
| D1 | Needs unfinished task? | No — `large_data_analytics_duckdb` (`ISS-012`) đã `Done (26-11-22)` và merge vào `origin/main` |
| D2 | Needed by unfinished task? | Yes: `ISS-041` (Graph exploration dùng lại 5 cột thực thể phụ trong `ProjectWarehouse`) |
| C1 | Modified files owned by in-progress task? | No — BOARD hiện không có task `In progress` |
| C2 | Hot-spot files touched | — (không sửa hot-spot registry nào; `seed_rbac.py` và `feature-policy.ts` không thuộc hot-spot list) |
| C3 | Schema change | Yes — drop cột `fraud_cases.assigned_to` bằng Alembic migration riêng (`batch_alter_table`, tương thích SQLite + PostgreSQL) |
| C4 | Public contract change | Yes — bỏ `POST /api/v1/cases/{case_id}/claim`, bỏ `assigned_to`/`unassigned` khỏi `GET /api/v1/cases` & `CaseResponse`, bỏ `assignee` khỏi `CaseActionRequest`, bỏ `related_assignees` khỏi action response, bỏ `assigned_to` khỏi SAR `section_1_identification` → consumers: `usfds-web` (cập nhật đồng bộ trong M3) |
| C5 | Shared UI shell change | No |

## 5. Acceptance tests (user reviews this section)
| Milestone | Test | Given | When | Then | Covers |
|---|---|---|---|---|---|
| M1 | `test_case_escalate_without_assignee_and_claim_rejected` (`usfds-core/tests/test_cases.py`) | Case ở trạng thái `OPEN` | Gọi `CaseService.update(..., "escalate", actor, summary="High velocity risk...")` và thử `update(..., "claim", actor)` | `escalate` nâng `priority = CRITICAL` và ghi audit log không cần `assignee`; `claim` ném `ValueError`; `Case` không có field `assigned_to` | ISS-045, SUC-18 |
| M1 | `test_warehouse_fact_includes_optional_entity_columns_and_reads_legacy_files` (`usfds-core/tests/test_project_warehouse.py`) | 1 `DetectionJob` có 5 cột thực thể phụ và 1 file fact cũ thiếu 5 cột này | `write_job_facts` rồi `load_fact_table` qua cả 2 job | Fact mới giữ đủ `device_id`, `ip_address`, `card_id`, `merchant_id`, `merchant_category`; `load_fact_table` gộp không lỗi và trả `NULL` cho file cũ | ISS-045, SUC-18 |
| M1 | `test_behavior_profile_from_warehouse_uses_duckdb_with_five_entity_dimensions` (`usfds-core/tests/test_cases.py`) | Project có fact warehouse chứa lịch sử 30/90 ngày và 5 thực thể của `user_id`; `pd.read_parquet` / `pd.read_csv` bị monkeypatch ném lỗi | Gọi `build_behavior_profile_from_warehouse` cho user có lịch sử và cold-start user | Trả đúng `avg_amount`, `max_amount`, `transactions_per_day`, `common_hours_utc`, `comparison` đủ 5 chiều thực thể, `timeline` tối đa 500 điểm, fallback `POPULATION` khi cold-start; không gọi pandas đọc file | ISS-045, SUC-18 |
| M1 | `test_sar_dossier_omits_assigned_to_and_uses_resolved_by` (`usfds-core/tests/test_insight_report_service.py`) | Case đã resolve bởi `analyst1` | `ReportBuilder.build_sar_dossier` và `format_sar_markdown` | `section_1_identification` không có khóa `assigned_to`, giữ `resolved_by = "analyst1"`; Markdown chỉ hiển thị `Resolved Analyst` | ISS-045 |
| M1 | `test_seed_rbac_removes_case_assign_and_claim_permissions` (`usfds-infra/tests/test_auth_repositories.py`) | DB đã có sẵn `case:assign` và `case:claim` gắn vào role | Chạy `seed_rbac(session)` | `case:assign` và `case:claim` bị xóa khỏi `permissions` và `role_permissions`; `project_admin`/`fraud_analyst` không còn 2 quyền này | ISS-045, SUC-17 |
| M1 | `test_case_repo_works_without_assigned_to_under_pg_compat` (`usfds-infra/tests/test_case_repositories.py`) | DB sau Alembic migration mới | Lưu, truy vấn `search`/`kpis` qua `SqliteCaseRepository` dưới `pg_compat` | Hoạt động bình thường, không `PostgresCompatibilityError`, bảng `fraud_cases` không còn cột `assigned_to` | ISS-045 |
| M2 | `test_investigation_api_removes_claim_and_escalates_without_assignee` (`usfds-server/tests/test_investigation_api.py`) | Project có Case `OPEN` qua API | `POST /api/v1/cases/{id}/claim` và `POST /api/v1/cases/{id}/escalate` chỉ với `expected_version` + `summary` | `/claim` trả `404`/`405` (không tồn tại trong OpenAPI); `/escalate` trả `200`, `priority = CRITICAL`, response không còn `assigned_to` và `related_assignees` | ISS-045, SUC-17, SUC-18 |
| M2 | `test_workbench_queries_warehouse_via_duckdb_without_pandas_full_load` (`usfds-server/tests/test_investigation_api.py`) | Project có `DetectionJob` `COMPLETED` (đã ghi hoặc tự sync fact warehouse) và Case liên kết; `pd.read_parquet`/`pd.read_csv` bị chặn | `GET /api/v1/cases/{id}/workbench?days=30` | Trả `200` với đầy đủ `profile` (avg/max/hours/comparison/timeline) từ warehouse qua DuckDB; không nạp full file bằng pandas | ISS-045, SUC-18 |
| M3 | `CaseQueueView & WorkbenchResolutionColumn: no assign/claim UI and escalate requires only note` (`usfds-web/src/components/modules/investigation/CaseWorkflow.test.tsx`) | MSW trả danh sách Case + Workbench không có `assigned_to` | Render `CaseQueueView` và `WorkbenchResolutionColumn`, nhập ghi chú >= 10 ký tự và bấm leo thang | Không hiển thị bộ lọc Phân công, cột Assignee, nút Nhận xử lý, form Phân công hay ô nhập người được giao leo thang; request `POST /escalate` gửi chỉ `{ expected_version, summary }` | ISS-045, SUC-17, SUC-18 |

## 6. Milestones & to-do (checkpoints, not stop points: all tests green at each)
The agent ticks items as it works. This is the task's only to-do list (`TODO.md` is no longer used for new work).

- [x] **M1 — Core, Warehouse & Infra Schema Redesign** (`usfds-core`, `usfds-infra`): bỏ `assigned_to`/`claim`, nâng cấp `ProjectWarehouse` + `behavior_profile` dùng DuckDB, xóa `case:assign`/`case:claim` khỏi RBAC, tạo Alembic migration.
  - [x] [tests] Viết & cập nhật các test M1 trong §5; xác nhận fail đúng lý do
  - [x] [core] Sửa `case.py`, `case_service.py`, `report_builder.py`
  - [x] [core] Sửa `project_warehouse.py` (5 cột thực thể phụ + tương thích file cũ) và `behavior_profile.py` (DuckDB queries)
  - [x] [infra] Sửa `case_models.py`, `case_repositories.py`, `seed_rbac.py`; tạo Alembic revision drop `fraud_cases.assigned_to`
  - [x] [verify] `./scripts/test.sh core infra`
- [x] **M2 — Server API & DuckDB Workbench Endpoint** (`usfds-server`): bỏ `/claim`, `assigned_to`, `assignee`, `related_assignees`; chuyển `workbench` sang truy vấn `ProjectWarehouse` bằng DuckDB.
  - [x] [tests] Viết & cập nhật các test M2 trong §5; xác nhận fail đúng lý do
  - [x] [server] Sửa `investigation_api_schemas.py`, `investigation_router.py`
  - [x] [verify] `./scripts/test.sh core infra server`
- [x] **M3 — Web UI Cleanup & Workflow Verification** (`usfds-web`): dọn toàn bộ UI/policy/types liên quan đến Assign/Claim/Assignee và xác nhận Vitest + build.
  - [x] [tests] Viết `CaseWorkflow.test.tsx` và cập nhật các test policy/visibility trong §3; xác nhận fail đúng lý do
  - [x] [web] Sửa `feature-policy.ts`, `types/*`, `investigationApi.ts`, `CaseQueueView.tsx`, `WorkbenchResolutionColumn.tsx`, `WorkbenchPanels.tsx`, `CaseWorkbenchView.tsx`, `ComplianceReportCenterTab.tsx`
  - [x] [verify] `./scripts/test.sh core infra worker cli server web`

Checkpoint log (the agent appends one line per finished milestone):
- 26-11-22 M1 done: core 171 passed (15 skipped, pre-existing) · infra 51 passed; notes: Alembic revision `40b0ea924c41` (`down_revision='f232fc1f5c13'`), `migrate check` exit 0.
- 26-11-22 M2 done: core 171 passed (15 skipped) · infra 51 passed · server 49 passed; notes: `/claim`, `assigned_to`, `assignee`, `related_assignees` removed; `workbench` queries `ProjectWarehouse` + artifact fallback via DuckDB.
- 26-11-22 M3 done: core 171 passed (15 skipped) · infra 51 passed · worker 10 passed · cli 5 passed · server 49 passed · web 41 passed (22 files) + build/lint 0 errors; notes: `test_insight_report_api.py` không cần sửa vì không chứa `assigned_to`.

## 7. Review hotspots (filled in after implementation)
- `usfds-core/src/usfds_core/services/investigation/case_service.py:101-151` (M1): Bỏ nhánh `claim` và `assignee` ở `escalate`, đổi `update()` trả về `Case` trực tiếp; `escalate` chỉ nâng `priority = CRITICAL` khi note >= 10 ký tự. Test: `test_case_escalate_without_assignee_and_claim_rejected`.
- `usfds-core/src/usfds_core/services/warehouse/project_warehouse.py:35-65, 160-249` (M1): Mở rộng DDL `ProjectWarehouse` thêm 5 cột thực thể phụ nullable (`VARCHAR`) và `ALTER TABLE ... ADD COLUMN` cho file fact Parquet cũ thiếu cột khi chạy `load_fact_table`. Test: `test_warehouse_fact_includes_optional_entity_columns_and_reads_legacy_files`.
- `usfds-core/src/usfds_core/services/investigation/behavior_profile.py:41-290` (M1): Toàn bộ baseline 30/90 ngày, cold-start fallback `POPULATION`, 5 chiều thực thể và timeline <= 500 điểm chuyển sang SQL DuckDB bounded (`build_behavior_profile_from_duckdb` / `_from_warehouse` / `_from_storage_file`); xử lý ép kiểu timestamp TZ về UTC naive để khớp warehouse. Test: `test_behavior_profile_from_warehouse_uses_duckdb_with_five_entity_dimensions`.
- `usfds-infra/src/usfds_infra/database/migrations/versions/40b0ea924c41_drop_case_assigned_to.py:21-40` + `usfds-infra/src/usfds_infra/database/seed_rbac.py:183-194` (M1): Migration kiểm tra `context.is_offline_mode()` / cột `assigned_to` hiện hữu trước khi `drop_column` (tránh lỗi ở legacy `create_all` upgrade); `seed_rbac` xóa idempotent `case:assign` và `case:claim` khỏi `permissions` và `role_permissions`. Test: `test_migrations.py`, `test_seed_rbac_removes_case_assign_and_claim_permissions`, `test_case_repo_works_without_assigned_to_under_pg_compat`.
- `usfds-server/src/usfds_server/routers/investigation_router.py:187-261` (M2): Gỡ bỏ `POST /{case_id}/claim`, filter `assigned_to`/`unassigned`, và `related_assignees`; `_workbench_profile` ưu tiên `ProjectWarehouse` (tự sync job `COMPLETED` thiếu fact) khi `case.detection_job_id` có hoặc không có artifact fallback, ngược lại fallback DuckDB đọc file artifact. Test: `test_investigation_api_removes_claim_and_escalates_without_assignee`, `test_workbench_queries_warehouse_via_duckdb_without_pandas_full_load`.
- `usfds-web/src/components/modules/investigation/CaseQueueView.tsx` & `WorkbenchResolutionColumn.tsx:361-401` (M3): Gỡ bỏ bộ lọc Phân công, cột Assignee, nút Nhận xử lý, form Phân công và ô nhập assignee khi leo thang; giữ `escalate` gửi `{ expected_version, summary }`. Test: `CaseWorkflow.test.tsx`.

## 8. Open questions
—
