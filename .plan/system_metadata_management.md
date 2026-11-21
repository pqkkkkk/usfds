# Plan: Quản lý Siêu dữ liệu Hệ thống & Hợp nhất Alias Cột Chuẩn (System Metadata Management)

> **Task ID:** `system_metadata_management` (= this file name) · **Issues:** ISS-007, ISS-027 (chosen by the user) · **Spec:** `docs/features/data_management/user-flow-and-ui-design.md`, `docs/features/project_management/design.md`
> **Conflict verdict:** PARALLEL-SAFE · **Status:** Review

## 1. Context (facts)
- **5 cột hệ thống cốt lõi (`SystemColumn`: `event_id`, `timestamp`, `amount`, `user_id`, `label`)** đang được khai báo tĩnh tại `usfds-core/src/usfds_core/domain/schemas/preprocessing_config.py:63-70` và tập cột phi-ML `NON_ML_COLUMNS` tại `preprocessing_config.py:85-100`.
- **Trùng lặp danh sách alias ở 10+ nơi (`ISS-027`):** Logic tự động dò tìm cột chuẩn qua alias đang bị viết lặp lại và không đồng nhất tại:
  1. `usfds-core/src/usfds_core/domain/schemas/preprocessing_config.py:85-100` (`NON_ML_COLUMNS`)
  2. `usfds-core/src/usfds_core/services/inference/executor.py:51-57` (`canonical_aliases`)
  3. `usfds-core/src/usfds_core/services/inference/inference_service.py:825-828` (`id_col`, `user_col`, `ts_col`, `amt_col`)
  4. `usfds-core/src/usfds_core/services/insight_report/engine.py:160-164` (`id_col`, `user_col`, `ts_col`, `amt_col`, `lbl_col`)
  5. `usfds-core/src/usfds_core/services/rule_engine/executor.py:331-366` (`RuleExecutor.backtest_dataframe`)
  6. `usfds-core/src/usfds_core/services/training/models/builtin_trainer.py:50` (`canonical_targets`)
  7. `usfds-core/src/usfds_core/services/preprocessing/preprocessing_service.py:77` (`_resolve_target_col`)
  8. `usfds-core/src/usfds_core/services/preprocessing/splitters/temporal_splitter.py:54,93` (`split_train_test`, `split_features_target`)
  9. `usfds-core/src/usfds_core/services/preprocessing/feature_engineering/credit_card_engineer.py:39-45` (`_resolve_column`)
  10. `usfds-core/src/usfds_core/services/preprocessing/feature_engineering/velocity_engineer.py:58-60,74-76,93-95` (`fit`, `transform`)
  11. `usfds-web/src/components/modules/data_management/SchemaMappingWorkspace.tsx:53-79` (hardcode tên cột, mô tả, auto-match `includes(...)` và 2 dòng optional mẫu `merch_name -> merchant`, `category -> category`).
- **Thiếu khả năng quản lý System Metadata & thích ứng ở Backend (`ISS-007`):**
  - Không có bảng DB, service hay API để quản lý siêu dữ liệu cột chuẩn (mô tả, danh sách alias gợi ý, trạng thái kích hoạt) hoặc định nghĩa thêm các cột chuẩn nghiệp vụ mở rộng (`Domain Columns` như `merchant`, `category`, `device_id`, `ip_address`, `country`, `channel`).
  - Tại `usfds-core/src/usfds_core/services/data_management/mapping.py:203-204`, các `optional_columns` chỉ sao chép nguyên bản `raw_df[raw_col]` mà không kiểm tra/ép kiểu dữ liệu (`NUMERIC`, `STRING`, `BOOLEAN`, `DATETIME`), không kiểm tra các cột Domain bắt buộc (`is_required=True`), và không phân biệt vai trò ML (`FEATURE` vs `IDENTIFIER`) khiến các cột định danh tùy chọn (vd `device_id`, `merchant_id`) có nguy cơ bị One-Hot Encode ở `PreprocessingExecutionService` (`usfds-core/src/usfds_core/services/preprocessing/pipeline_builder.py:77-92`).

## 2. Goal, scope verdict & non-goals
- **Goal:** Xây dựng System Metadata Registry lưu trữ trong DB (gồm 5 cột `CORE` khóa cứng khóa/kiểu + các cột `DOMAIN` mở rộng tùy biến được `logical_type`, `is_required`, `ml_role`, `aliases`), hợp nhất toàn bộ logic phân giải alias ở 10 module backend (`ISS-027`), giúp pipeline `DataMappingService` / `PreprocessingExecutionService` thích ứng động với metadata mới và cung cấp giao diện quản trị trên `AdminUsersPage` + tích hợp động vào `SchemaMappingWorkspace` (`ISS-007`).
- **Scope:** OK (gộp `ISS-007` và prerequisite `ISS-027` theo xác nhận của user).
- **Non-goals / omitted:**
  - Không cho phép xóa, tắt (`is_active=False`), bỏ bắt buộc (`is_required=False`) hoặc đổi `column_key` / `logical_type` của 5 cột hệ thống cốt lõi (`event_id`, `timestamp`, `amount`, `user_id`, `label`) để bảo toàn hợp đồng dữ liệu của các thuật toán Temporal Split, Velocity FE, Detection, Investigation và Insight Report.
  - Không làm tính năng lưu Mapping Templates theo từng Project (Phương án C).
- **Assumptions:**
  - Bảng `system_column_metadata` được seed tự động (idempotent) với 5 cột `CORE` (`event_id`, `timestamp`, `amount`, `user_id`, `label`) và 2 cột `DOMAIN` mặc định (`merchant`, `category`) để tương thích ngược 100% với dữ liệu và test hiện có.
  - Quyền quản trị metadata sử dụng permission mới `system_metadata:manage` (scope `SYSTEM`, tự động gán cho `system_admin`), trong khi endpoint đọc danh sách cột chuẩn (`GET /api/v1/system-metadata/columns`) cho phép mọi user đã xác thực truy cập để phục vụ màn hình Data Mapping.
  - **Chính sách với Dataset/Artifact cũ (Forward-only + Snapshot):** `DatasetArtifact` là bất biến theo Lineage DAG; mọi thay đổi metadata của Admin chỉ áp dụng cho các lần ánh xạ mới. `DataMappingService` lưu `datasets/{dataset_id}/mapped/{artifact_id}/mapped.parquet` (không ghi đè file cũ) và ghi `non_ml_columns` + `metadata_snapshot` vào `validation_report` (truyền tiếp qua `FeatureEngineeringExecutionService`) để pipeline cũ và model đã train không bị gãy. UI `SchemaMappingWorkspace` hiển thị cảnh báo lệch lược đồ (Schema Drift Warning) nếu `mappedArtifact` cũ khác metadata hiện tại và cho phép Data Scientist chủ động re-map tạo nhánh mới.

## 3. Files
| Action | File | Milestone | Note |
|---|---|---|---|
| modify | `usfds-core/src/usfds_core/domain/entities/enums.py` | M1 | append-only hot spot (`ColumnCategory`, `ColumnMlRole`) |
| create | `usfds-core/src/usfds_core/domain/entities/system_metadata.py` | M1 | `SystemColumnMetadata` entity |
| create | `usfds-core/src/usfds_core/domain/schemas/system_metadata.py` | M1 | `DEFAULT_SYSTEM_COLUMN_ALIASES`, `resolve_canonical_column`, `build_non_ml_columns` |
| modify | `usfds-core/src/usfds_core/domain/schemas/preprocessing_config.py` | M1 | re-export helpers & dùng `DEFAULT_SYSTEM_COLUMN_ALIASES` |
| create | `usfds-core/src/usfds_core/repositories/base_system_metadata_repo.py` | M1 | `ISystemColumnMetadataRepository` port |
| create | `usfds-core/src/usfds_core/services/data_management/system_metadata_service.py` | M1 | `SystemMetadataService` (CRUD + bảo vệ 5 cột `CORE`) |
| modify | `usfds-core/src/usfds_core/services/data_management/mapping.py` | M1 | kiểm tra cột `DOMAIN` `is_required`, ép kiểu theo `logical_type`, lưu `non_ml_columns` |
| modify | `usfds-core/src/usfds_core/services/data_management/service.py` | M1 | truyền `metadata_repo` vào `DataMappingService` |
| modify | `usfds-core/src/usfds_core/services/preprocessing/pipeline_builder.py` | M1 | hỗ trợ `extra_non_ml_columns` từ metadata / artifact report |
| modify | `usfds-core/src/usfds_core/services/preprocessing/preprocessing_service.py` | M1 | dùng `resolve_canonical_column` + đọc `non_ml_columns` động |
| modify | `usfds-core/src/usfds_core/services/preprocessing/splitters/temporal_splitter.py` | M1 | dùng `resolve_canonical_column` (ISS-027) |
| modify | `usfds-core/src/usfds_core/services/preprocessing/feature_engineering/credit_card_engineer.py` | M1 | dùng `resolve_canonical_column` (ISS-027) |
| modify | `usfds-core/src/usfds_core/services/preprocessing/feature_engineering/velocity_engineer.py` | M1 | dùng `resolve_canonical_column` (ISS-027) |
| modify | `usfds-core/src/usfds_core/services/inference/executor.py` | M1 | dùng `DEFAULT_SYSTEM_COLUMN_ALIASES` & `resolve_canonical_column` (ISS-027) |
| modify | `usfds-core/src/usfds_core/services/inference/inference_service.py` | M1 | dùng `resolve_canonical_column` (ISS-027) |
| modify | `usfds-core/src/usfds_core/services/insight_report/engine.py` | M1 | dùng `resolve_canonical_column` (ISS-027) |
| modify | `usfds-core/src/usfds_core/services/rule_engine/executor.py` | M1 | dùng `resolve_canonical_column` (ISS-027) |
| modify | `usfds-core/src/usfds_core/services/training/models/builtin_trainer.py` | M1 | dùng `resolve_canonical_column` (ISS-027) |
| create | `usfds-core/tests/test_system_metadata.py` | M1 | unit tests cho `ISS-007` & `ISS-027` ở tầng core |
| create | `usfds-infra/src/usfds_infra/database/tables/system_metadata.py` | M2 | `SystemColumnMetadataModel` |
| modify | `usfds-infra/src/usfds_infra/database/models.py` | M2 | append-only hot spot |
| create | `usfds-infra/src/usfds_infra/database/repos/system_metadata.py` | M2 | `SqlSystemColumnMetadataRepository` |
| modify | `usfds-infra/src/usfds_infra/database/repositories.py` | M2 | append-only hot spot |
| modify | `usfds-infra/src/usfds_infra/database/__init__.py` | M2 | append-only hot spot |
| create | `usfds-infra/src/usfds_infra/database/seed_system_metadata.py` | M2 | seed idempotent 5 cột `CORE` + 2 cột `DOMAIN` mặc định |
| modify | `usfds-infra/src/usfds_infra/database/seed_rbac.py` | M2 | thêm permission `system_metadata:manage` |
| migration | `usfds-infra/src/usfds_infra/database/migrations/versions/<rev>_add_system_column_metadata.py` | M2 | tạo bảng `system_column_metadata` |
| modify | `usfds-server/src/usfds_server/providers/repos.py` | M2 | append-only hot spot (`get_system_metadata_repo`) |
| modify | `usfds-server/src/usfds_server/providers/data.py` | M2 | `get_system_metadata_service`, gắn `metadata_repo` vào `DataManagementService` |
| modify | `usfds-server/src/usfds_server/dependencies.py` | M2 | append-only hot spot + gọi `seed_system_metadata` khi startup |
| create | `usfds-server/src/usfds_server/schemas/system_metadata_api_schemas.py` | M2 | request/response DTOs |
| create | `usfds-server/src/usfds_server/routers/system_metadata_router.py` | M2 | CRUD API `/api/v1/system-metadata/columns` |
| modify | `usfds-server/src/usfds_server/api.py` | M2 | append-only hot spot (`include_router(system_metadata_router.router)`) |
| modify | `usfds-worker/src/usfds_worker/handlers.py` | M2 | truyền `SqlSystemColumnMetadataRepository(session)` trong `_build_data_management_service` |
| create | `usfds-server/tests/test_system_metadata_api.py` | M2 | API & integration tests cho CRUD + dynamic mapping |
| create | `usfds-web/src/types/systemMetadata.ts` | M3 | TypeScript interfaces cho System Metadata |
| create | `usfds-web/src/api/systemMetadataApi.ts` | M3 | HTTP client gọi `/v1/system-metadata/columns` |
| create | `usfds-web/src/hooks/useSystemMetadata.ts` | M3 | react-query hook (`useSystemMetadata`) |
| modify | `usfds-web/src/hooks/index.ts` | M3 | append-only hot spot |
| modify | `usfds-web/src/lib/feature-policy.ts` | M3 | thêm `manageSystemMetadata` và cập nhật `adminUsers` |
| create | `usfds-web/src/components/modules/data_management/SystemMetadataAdminTab.tsx` | M3 | giao diện quản trị cột hệ thống & cột nghiệp vụ |
| modify | `usfds-web/src/pages/AdminUsersPage.tsx` | M3 | tích hợp tab `Siêu dữ liệu hệ thống` |
| modify | `usfds-web/src/components/modules/data_management/SchemaMappingWorkspace.tsx` | M3 | hiển thị động cột chuẩn, cột `DOMAIN` bắt buộc/tùy chọn & auto-match theo `aliases` |
| create | `usfds-web/src/components/modules/data_management/SystemMetadata.test.tsx` | M3 | vitest + MSW tests cho Admin tab & SchemaMappingWorkspace động |

## 4. Dependencies & conflicts (with other tasks on BOARD)
| # | Check | Answer |
|---|---|---|
| D1 | Needs unfinished task? | No (cả `ISS-025`, `ISS-006`, `ISS-037` đều đã `Done` trên `.plan/BOARD.md`) |
| D2 | Needed by unfinished task? | No |
| C1 | Modified files owned by in-progress task? | No (không có task nào đang ở trạng thái `In progress` trên `.plan/BOARD.md`) |
| C2 | Hot-spot files touched | `domain/entities/enums.py`, `database/models.py`, `database/repositories.py`, `database/__init__.py`, `providers/repos.py`, `server/dependencies.py`, `server/api.py`, `web/src/hooks/index.ts` (append-only) |
| C3 | Schema change | Yes: bảng mới `system_column_metadata` (1 Alembic revision riêng) |
| C4 | Public contract change | Yes: thêm `/api/v1/system-metadata/columns` (GET/POST/PATCH/DELETE) → consumers: `AdminUsersPage.tsx`, `SchemaMappingWorkspace.tsx` |
| C5 | Shared UI shell change | No (tích hợp tab vào `AdminUsersPage.tsx`, không sửa `App.tsx`, `Sidebar.tsx`, `navigation.ts`) |

## 5. Acceptance tests (user reviews this section)
| Milestone | Test | Given | When | Then | Covers |
|---|---|---|---|---|---|
| M1 | `test_resolve_canonical_column_unifies_aliases_across_modules` (`usfds-core/tests/test_system_metadata.py`) | DataFrame chứa các tên cột thô khác nhau (`TransactionID`, `TransactionDT`, `TransactionAmt`, `CLIENTNUM`, `isFraud`) | Gọi `resolve_canonical_column` và chạy qua `prepare_and_validate_input`, `TemporalDataSplitter`, `CreditCardFeatureEngineer`, `VelocityFeatureEngineer`, `RuleExecutor.backtest_dataframe` | Tất cả các module đều phân giải đúng về 5 `SystemColumn` từ một nguồn `DEFAULT_SYSTEM_COLUMN_ALIASES` duy nhất | ISS-027 |
| M1 | `test_core_system_columns_are_immutable_while_aliases_are_editable` (`usfds-core/tests/test_system_metadata.py`) | `SystemMetadataService` khởi tạo với 5 cột `CORE` | Thử xóa cột `event_id` hoặc đổi `is_required=False` / `logical_type="NUMERIC"` trên `event_id`; sau đó cập nhật `aliases=["tx_id", "ma_gd"]` cho `event_id` | Thao tác xóa hoặc sửa trường khóa của cột `CORE` ném `ValueError`; thao tác cập nhật `aliases` và `description` thành công và luôn giữ `"event_id"` trong `aliases` | ISS-007 |
| M1 | `test_mapping_adapts_to_dynamic_domain_columns_and_identifier_role` (`usfds-core/tests/test_system_metadata.py`) | Admin thêm cột `DOMAIN` `device_id` (`logical_type="STRING"`, `is_required=True`, `ml_role="IDENTIFIER"`) và `risk_hint` (`logical_type="NUMERIC"`, `is_required=False`, `ml_role="FEATURE"`) | Gọi `DataMappingService.map_dataset` thiếu `device_id` -> lỗi; gọi lại khi đã ánh xạ `device_id` và `risk_hint`, sau đó chạy `PreprocessingPipelineBuilder` | Khi thiếu `device_id` ném `ValueError`; khi ánh xạ đủ thì `risk_hint` được ép kiểu float64, còn `device_id` được ghi vào `validation_report["non_ml_columns"]` và tự động bị loại khỏi danh sách cột One-Hot Encoding của Tabular ML | ISS-007 |
| M1 | `test_existing_mapped_artifact_remains_valid_after_metadata_change` (`usfds-core/tests/test_system_metadata.py`) | Dataset cũ đã hoàn tất `MAPPED` với `device_id` (`IDENTIFIER`) trong snapshot; sau đó Admin thêm cột `channel` (`is_required=True`) và vô hiệu hóa `device_id` | Chạy `FeatureEngineeringExecutionService` + `PreprocessingPipelineBuilder` trên artifact cũ; sau đó re-map dataset mới với `channel` | Artifact cũ vẫn chạy FE + Preprocessing thành công theo `non_ml_columns` trong snapshot mà không bị ghi đè file `mapped.parquet` cũ | ISS-007 |
| M2 | `test_system_metadata_crud_api_and_rbac_enforcement` (`usfds-server/tests/test_system_metadata_api.py`) | DB đã migrate và seed 5 cột `CORE` + 2 cột `DOMAIN` (`merchant`, `category`) | User thường (`data_scientist`) gọi `GET /api/v1/system-metadata/columns` và `POST /api/v1/system-metadata/columns`; `system_admin` gọi `POST`, `PATCH`, `DELETE` cột `DOMAIN` và thử `DELETE` cột `CORE` | `data_scientist` đọc `GET` được `200 OK` nhưng gọi `POST` bị `403 Forbidden`; `system_admin` tạo/sửa/xóa cột `DOMAIN` thành công (`201`/`200`), xóa cột `CORE` nhận `400 Bad Request` | ISS-007 |
| M2 | `test_schema_mapping_endpoint_enforces_required_domain_column` (`usfds-server/tests/test_system_metadata_api.py`) | `system_admin` tạo cột `DOMAIN` `channel` với `is_required=True` qua API | Gọi `POST /api/v1/datasets/{id}/schema-mapping` không có `channel` trong `optional_columns`, sau đó gọi lại có `channel` | Lần 1 trả `400 Bad Request` báo thiếu trường bắt buộc `channel`; lần 2 trả `201 Created` với `channel` trong `MAPPED` artifact | ISS-007 |
| M3 | `test_admin_system_metadata_tab_renders_and_manages_columns` (`usfds-web/src/components/modules/data_management/SystemMetadata.test.tsx`) | Admin mở `AdminUsersPage` và chuyển sang tab `Siêu dữ liệu hệ thống` | Thêm cột chuẩn mở rộng `device_id` (`IDENTIFIER`, bắt buộc) và cập nhật alias cho `event_id` | UI hiển thị 5 cột `CORE` (khóa nút xóa) và danh sách cột `DOMAIN`, gửi đúng payload tới `POST /api/v1/system-metadata/columns` và cập nhật bảng | ISS-007 |
| M3 | `test_schema_mapping_workspace_uses_dynamic_metadata_and_aliases` (`usfds-web/src/components/modules/data_management/SystemMetadata.test.tsx`) | API `/v1/system-metadata/columns` trả về alias tùy chỉnh `ma_giao_dich` cho `event_id` và cột `DOMAIN` bắt buộc `device_id` (`raw` có cột `ma_giao_dich`, `dev_hash`) | Render `SchemaMappingWorkspace` | `event_id` tự động khớp với cột nguồn `ma_giao_dich`, `device_id` xuất hiện trong nhóm bắt buộc và tự khớp với `dev_hash` | ISS-007, ISS-027 |

## 6. Milestones & to-do (checkpoints, not stop points: all tests green at each)
The agent ticks items as it works. This is the task's only to-do list (`TODO.md` is no longer used for new work).

- [x] **M1 — Core Metadata Registry, Alias Consolidation & Dynamic Pipeline Adaptation** (`usfds-core`): hợp nhất `DEFAULT_SYSTEM_COLUMN_ALIASES` ở 10 module (`ISS-027`), bổ sung thực thể `SystemColumnMetadata`, `SystemMetadataService`, và nâng cấp `DataMappingService` + `PreprocessingExecutionService` thích ứng động với `DOMAIN` columns (`ISS-007`).
  - [x] [tests] Viết các unit test M1 trong `usfds-core/tests/test_system_metadata.py`; chạy thử để xác nhận fail đúng lý do
  - [x] [core] Thêm `ColumnCategory`, `ColumnMlRole` vào `enums.py` và tạo `domain/entities/system_metadata.py`, `domain/schemas/system_metadata.py`, `repositories/base_system_metadata_repo.py`
  - [x] [core] Tạo `SystemMetadataService` và tích hợp kiểm tra/ép kiểu cột `DOMAIN` + `non_ml_columns` vào `DataMappingService`, `PreprocessingPipelineBuilder`, `PreprocessingExecutionService`
  - [x] [core] Thay thế danh sách alias trùng lặp ở `inference/executor.py`, `inference_service.py`, `insight_report/engine.py`, `rule_engine/executor.py`, `builtin_trainer.py`, `temporal_splitter.py`, `credit_card_engineer.py`, `velocity_engineer.py`
  - [x] [verify] `./scripts/test.sh core`
- [x] **M2 — Database Persistence, Migration, Seed & REST API** (`usfds-infra`, `usfds-server`, `usfds-worker`): lưu trữ `system_column_metadata`, tạo migration Alembic, seed mặc định và cung cấp API `/api/v1/system-metadata/columns`.
  - [x] [tests] Viết các API/integration test M2 trong `usfds-server/tests/test_system_metadata_api.py`
  - [x] [infra] Tạo `SystemColumnMetadataModel`, `SqlSystemColumnMetadataRepository`, `seed_system_metadata.py`, cập nhật `seed_rbac.py` (`system_metadata:manage`) và sinh Alembic migration
  - [x] [server] Tạo `system_metadata_api_schemas.py`, `system_metadata_router.py`, đăng ký providers (`repos.py`, `data.py`, `dependencies.py`), `api.py` và cập nhật `usfds-worker/src/usfds_worker/handlers.py`
  - [x] [verify] `./scripts/test.sh core infra server worker`
- [x] **M3 — Admin UI Tab & Dynamic Schema Mapping Workspace** (`usfds-web`): xây dựng tab quản trị `Siêu dữ liệu hệ thống` và kết nối động vào `SchemaMappingWorkspace`.
  - [x] [tests] Viết component tests M3 với MSW trong `usfds-web/src/components/modules/data_management/SystemMetadata.test.tsx`
  - [x] [web] Tạo `types/systemMetadata.ts`, `api/systemMetadataApi.ts`, `hooks/useSystemMetadata.ts` và cập nhật `lib/feature-policy.ts`
  - [x] [web] Tạo `SystemMetadataAdminTab.tsx`, gắn vào `AdminUsersPage.tsx`, và nâng cấp `SchemaMappingWorkspace.tsx` dùng metadata + alias động từ API
  - [x] [verify] `./scripts/test.sh` (toàn bộ 6 package + `npm run build` & `npm run lint` trong `usfds-web`)

Checkpoint log (the agent appends one line per finished milestone):
- 26-11-21 · M1: `core`: `156 passed, 15 skipped in 6.58s` · deviations: also updated `feature_engineering_service.py` to propagate `non_ml_columns` & `metadata_snapshot` per plan §2/§5.
- 26-11-21 · M2: `core`: 156 passed · `infra`: 37 passed · `server`: 35 passed · `worker`: 3 passed · Alembic rev `adb5e69392ae` (`down_revision=b1b7b507e88d`) with `if_not_exists=True` for legacy DB compatibility.
- 26-11-21 · M3: `web`: `19 test files, 35 passed` · `npm run build` OK · `npm run lint` 0 errors · full `./scripts/test.sh` all 6 packages green.

## 7. Review hotspots (filled in after implementation)
1. `usfds-core/src/usfds_core/services/data_management/system_metadata_service.py:100-181` (M1): Khóa bất biến 5 cột `CORE` (cấm xóa, cấm đổi `column_key`/`logical_type`/`is_required`/`is_active`/`ml_role`), vẫn cho phép cập nhật `aliases`/`description`/`display_name` và luôn giữ `column_key` trong `aliases`; covered by `test_core_system_columns_are_immutable_while_aliases_are_editable`.
2. `usfds-core/src/usfds_core/services/data_management/mapping.py:243-348` (M1): Kiểm tra bắt buộc cột `DOMAIN` có `is_required=True`, ép kiểu theo `LogicalDataType`, tách đường dẫn bất biến `datasets/{dataset_id}/mapped/{artifact_id}/mapped.parquet` (không ghi đè artifact cũ), ghi `non_ml_columns` + `metadata_snapshot` vào `validation_report`; covered by `test_mapping_adapts_to_dynamic_domain_columns_and_identifier_role` & `test_existing_mapped_artifact_remains_valid_after_metadata_change`.
3. `usfds-core/src/usfds_core/domain/schemas/system_metadata.py:165-248` (M1): Hợp nhất cơ chế phân giải alias `resolve_canonical_column` (ưu tiên exact → case-insensitive → normalized kèm guard `strict_requested`) và `build_non_ml_columns` cho toàn bộ 10 module; covered by `test_resolve_canonical_column_unifies_aliases_across_modules`.
4. `usfds-infra/src/usfds_infra/database/migrations/versions/adb5e69392ae_add_system_column_metadata.py:21-57` (M2): Migration tạo bảng `system_column_metadata` + 3 index với `if_not_exists=True` bảo toàn dữ liệu legacy SQLite và tương thích PostgreSQL; covered by `test_migrations.py`.
5. `usfds-server/src/usfds_server/routers/system_metadata_router.py:39-145` (M2): Phân quyền RBAC (`GET` cho user đã xác thực qua `get_actor_context`, `POST`/`PATCH`/`DELETE` yêu cầu `system_metadata:manage`) và map `LookupError` → 404 / `ValueError` → 400; covered by `test_system_metadata_crud_api_and_rbac_enforcement` & `test_schema_mapping_endpoint_enforces_required_domain_column`.
6. `usfds-web/src/components/modules/data_management/SchemaMappingWorkspace.tsx:161-319` (M3): Auto-match cột `CORE` và `DOMAIN` (bắt buộc + tùy chọn) theo `aliases` động từ API, tính tổng slot bắt buộc (`5 + requiredDomainColumns.length`) và phát hiện Schema Drift so với `metadata_snapshot` của `mappedArtifact`; covered by `test_schema_mapping_workspace_uses_dynamic_metadata_and_aliases`.

## 8. Open questions
- —
