# Plan: Resource Owner Display (`owner`) & Cursor Pagination (`ISS-031`)

> **Task ID:** `resource_owner_and_cursor_pagination` (= this file name) · **Issues:** `ISS-031` (kèm mở rộng hiển thị chủ sở hữu từ `ISS-043`) · **Spec:** `docs/issues/11-14-2026.md#ISS-031`, `.plan/own_scope_access_control.md`
> **Conflict verdict:** PARALLEL-SAFE · **Status:** Done <!-- Approved (26-11-22) -->

## 1. Context (facts)
- Toàn bộ 7 response DTO của các resource trong scope (`ProjectResponse` in `project_api_schemas.py:23-38`, `DatasetResponse` in `dataset_api_schemas.py:21-37`, `ModelResponse` in `training_api_schemas.py:62-79`, `ModelVersionResponse` in `training_api_schemas.py:82-100`, `TrainingRunResponse` in `training_api_schemas.py:103-133`, `RuleResponse` in `rule_api_schemas.py:53-65`, `DetectionJobResponse` in `detection_api_schemas.py:36-59`) đã có `user_id`, nhưng chưa trả kèm thông tin người dùng (`username`, `full_name`) từ bảng `users`.
- `UserRepository` (`usfds-infra/src/usfds_infra/database/repos/auth.py:89-103`) mới có `get_by_id`, chưa có `get_by_ids(user_ids)` để batch-lookup tránh N+1.
- Trên `usfds-web`, các màn hình danh sách và chi tiết (`ProjectManagementView`, `ProjectSettingsView`, `DatasetHubView`, `DataPipelineWorkspace`, `DatasetLineageExplorer`, `ModelHubView`, `TrainingRunDetailView`, `RuleCatalogView`, `RuleWorkspace`, `DetectionJobsHubView`, `DetectionResultExplorerView`) mới dùng `record.user_id` cho `canAccessRecord(...)`, chưa hiển thị chủ sở hữu lên UI.
- **`ISS-031`:** Các endpoint `GET` danh sách đều trả mảng phẳng `List[T]` không phân trang (`project_router.py:93`, `dataset_router.py:182`, `training_router.py:354,404,595`, `rule_router.py:119,247`, `detection_router.py:63`). Chỉ có `GET /detection/jobs/{job_id}/results` (`detection_router.py:170-171`) dùng `limit`/`offset`.

## 2. Goal, scope verdict & non-goals
- **Goal:**
  1. Chuẩn hóa **cursor pagination** (`?limit=&cursor=` → `ApiResponse[CursorPage[T]]` với `data: { items: T[], nextCursor: string | null }`) cho 8 endpoint `GET` danh sách thuộc 5 core routers (`projects`, `datasets`, `models`, `models/{id}/versions`, `training-runs`, `rules`, `rules/{id}/versions`, `detection/jobs`) (`ISS-031`).
  2. Batch-join bảng `users` qua `UserRepository.get_by_ids` (1 query `IN (...)` trên trang hiện tại, không N+1) để trả kèm `owner: { user_id, username, full_name }` (giữ nguyên `user_id` top-level cho RBAC) trên toàn bộ API response của 7 resource (`Project`, `Dataset`, `Model`, `ModelVersion`, `TrainingRun`, `Rule`, `DetectionJob`).
  3. Cập nhật `usfds-web` nhận `CursorPage<T>` (hỗ trợ infinite/load-more với `nextCursor`) và hiển thị chủ sở hữu bằng component dùng chung `OwnerBadge` (`full_name || username`, hover xem `@username` + `user_id`, hoặc `Hệ thống` cho built-in model) trên toàn bộ 11 view danh sách & chi tiết.
- **Scope:** OK
- **Non-goals / omitted:**
  - **Ngoài scope:** Investigation (`fraud_cases`, `entity_blacklist`) và Insight Report (`insight_report_router.py` — gồm N+1 trong `insight_report/service.py:125-131`), chờ user thiết kế lại 2 module này.
  - Không đổi `GET /detection/jobs/{job_id}/results` (đã có `limit`/`offset`), cũng như các endpoint admin/membership (`users`, `roles`, `projects/{id}/members`).
  - Cursor pagination cắt trang trên tập kết quả đã lọc/sắp xếp ở tầng server bằng keyset cursor ổn định `(sort_key, id)` trước khi batch-resolve `owner` cho đúng `items` của trang hiện tại; tối ưu `LIMIT` xuống SQL từng repo có thể bổ sung sau mà không đổi API contract.
- **Assumptions:**
  - Mặc định `limit = 50` (`ge=1, le=200`); `cursor` là chuỗi opaque base64url; `cursor` sai định dạng trả `400`.
  - Built-in `Model` (`user_id = None`) trả `owner = None` và UI hiển thị badge `Hệ thống`.

## 3. Files
| Action | File | Milestone | Note |
|---|---|---|---|
| modify | `usfds-core/src/usfds_core/repositories/base_user_repo.py` | M1 | thêm `get_by_ids(user_ids)` trên `IUserRepository` |
| modify | `usfds-infra/src/usfds_infra/database/repos/auth.py` | M1 | cài đặt `get_by_ids(user_ids)` bằng 1 query `WHERE user_id IN (...)` |
| modify | `usfds-infra/tests/test_auth_repositories.py` | M1 | test `get_by_ids` |
| modify | `usfds-server/src/usfds_server/schemas/base_response.py` | M2 | thêm `ResourceOwnerDto` và `CursorPage[T]` (`items`, `nextCursor`) |
| create | `usfds-server/src/usfds_server/schemas/pagination.py` | M2 | helper `paginate_cursor(...)` & `resolve_owners(...)` dùng chung |
| modify | `usfds-server/src/usfds_server/schemas/{project,dataset,training,rule,detection}_api_schemas.py` | M2 | thêm `owner: Optional[ResourceOwnerDto] = None` trên 7 response DTO |
| modify | `usfds-server/src/usfds_server/routers/{project,dataset,training,rule,detection}_router.py` | M2 | thêm `limit`/`cursor`, trả `CursorPage`, và batch-resolve `owner` cho list/detail/mutate |
| modify | `usfds-server/tests/{test_auth_and_rbac_api,test_dataset_api,test_training_api,test_detection_api,test_rule_api}.py` | M2 | acceptance tests `CursorPage` + `owner` và cập nhật các test đọc `data["items"]` |
| modify | `usfds-web/src/types/{api,project,dataset,model,rule,detection}.ts` | M3 | thêm `CursorPage<T>`, `ResourceOwner`, `owner?: ResourceOwner | null` |
| modify | `usfds-web/src/api/{projectApi,datasetApi,trainingApi,ruleApi,detectionApi}.ts` | M3 | hỗ trợ `limit`/`cursor` và kiểu trả về `ApiResponse<CursorPage<...>>` |
| modify | `usfds-web/src/hooks/{useProjects,useDatasetList}.ts*` | M3 | đọc `data.items` và hỗ trợ `nextCursor` / `loadMore` |
| create | `usfds-web/src/components/common/OwnerBadge.tsx` | M3 | hiển thị `full_name || username`, tooltip `@username` + `user_id`, `Hệ thống` khi `null` |
| modify | `usfds-web/src/components/modules/project_management/{ProjectManagementView,ProjectSettingsView}.tsx` | M3 | hiển thị `project.owner` + nút tải thêm khi có `nextCursor` |
| modify | `usfds-web/src/components/modules/data_management/{DatasetHubView,DataPipelineWorkspace,DatasetLineageExplorer}.tsx` | M3 | hiển thị `dataset.owner` + tải thêm khi có `nextCursor` |
| modify | `usfds-web/src/components/modules/model/{ModelHubView,TrainingRunDetailView,TrainingWizardView}.tsx` | M3 | đọc `data.items`, tải thêm khi có `nextCursor`, hiển thị `model.owner` / `version.owner` / `run.owner` |
| modify | `usfds-web/src/components/modules/rule/{RuleCatalogView,RuleWorkspace,RuleVersionHistoryModal}.tsx` | M3 | đọc `data.items`, tải thêm khi có `nextCursor`, hiển thị `rule.owner` |
| modify | `usfds-web/src/components/modules/detection/{DetectionJobsHubView,DetectionResultExplorerView,DetectionJobWizardView}.tsx` | M3 | đọc `data.items`, tải thêm khi có `nextCursor`, hiển thị `job.owner` |
| modify | `usfds-web/src/test/{featureVisibilityModules,mswHandlers}.test.tsx` & module `.test.tsx` | M3 | cập nhật mock `CursorPage` và acceptance tests hiển thị `owner` + `nextCursor` |

## 4. Dependencies & conflicts (with other tasks on BOARD)
| # | Check | Answer |
|---|---|---|
| D1 | Needs unfinished task? | No (`own_scope_access_control` M1–M3 đã xong trên nhánh hiện tại) |
| D2 | Needed by unfinished task? | No |
| C1 | Modified files owned by in-progress task? | No |
| C2 | Hot-spot files touched | No |
| C3 | Schema change | No |
| C4 | Public contract change | Yes: 8 `GET` list endpoints đổi `data` từ `T[]` sang `{ items: T[], nextCursor: string | null }` và 7 resource DTO thêm `owner`; đã bao gồm cập nhật toàn bộ consumers trong `usfds-web` |
| C5 | Shared UI shell change | No |

## 5. Acceptance tests (user reviews this section)
| Milestone | Test | Given | When | Then | Covers |
|---|---|---|---|---|---|
| M1 | `test_user_repo_get_by_ids_returns_map_without_duplicates` (`usfds-infra/tests/test_auth_repositories.py`) | DB có 3 users `u1`, `u2`, `u3` | Gọi `user_repo.get_by_ids([u1.user_id, u1.user_id, u2.user_id, uuid4()])` | Trả về dict `{u1.user_id: u1, u2.user_id: u2}` (2 phần tử, bỏ qua ID không tồn tại) | `ISS-043` |
| M2 | `test_list_endpoints_support_cursor_pagination_and_return_owner` (`usfds-server/tests/test_auth_and_rbac_api.py`) | Project có 3 datasets do `u1` (`username`, `full_name`) tạo, plus project, custom model, training run, model version, rule, detection job và built-in model | Gọi `GET /datasets?project_id=...&limit=2`, lấy `nextCursor` gọi tiếp trang 2; và gọi `GET` trên cả 8 list endpoints + detail endpoints | Trang 1 trả 2 `items` + `nextCursor != null`; trang 2 trả 1 `items` + `nextCursor == null` không trùng item; mọi item có `user_id` + `owner: {user_id, username, full_name}` (riêng built-in model có `user_id=None, owner=None`); cursor rác trả `400` | `ISS-031`, `ISS-043` |
| M3 | `test_module_views_display_owner_and_load_more_with_cursor` (`usfds-web/src/test/featureVisibilityModules.test.tsx`) | Render `ProjectManagementView`, `DatasetHubView`, `ModelHubView`, `RuleCatalogView`, `DetectionJobsHubView` với dữ liệu `CursorPage` có `owner` (`full_name`, `username`), built-in model (`owner: null`), và `nextCursor: "c1"` | Kiểm tra nội dung cột Chủ sở hữu & bấm nút "Tải thêm" | Hiển thị `full_name` (tooltip chứa `@username` & `user_id`) cho resource có chủ, `Hệ thống` cho built-in model; bấm "Tải thêm" gọi API với `cursor=c1` và nối thêm items trang 2 | `ISS-031`, `ISS-043` |

## 6. Milestones & to-do (checkpoints, not stop points: all tests green at each)
The agent ticks items as it works. This is the task's only to-do list (`TODO.md` is no longer used for new work).

- [x] **M1 — Batch User Lookup** (`usfds-core`, `usfds-infra`): `UserRepository.get_by_ids` sẵn sàng cho batch-join owner.
  - [x] [tests] Viết M1 test trong `test_auth_repositories.py`; xác nhận fail
  - [x] [core/infra] Thêm `get_by_ids` vào `ports/auth.py` và `repos/auth.py`
  - [x] [verify] `./scripts/test.sh core infra`
- [x] **M2 — Cursor Pagination (`ISS-031`) & `owner` DTOs** (`usfds-server`): 8 `GET` list endpoints trả `{ items, nextCursor }` và 7 resource DTO trả kèm `owner`.
  - [x] [tests] Viết M2 acceptance test trong `test_auth_and_rbac_api.py`; xác nhận fail
  - [x] [server] Tạo `CursorPage`, `ResourceOwnerDto`, `pagination.py` (`paginate_cursor`, `resolve_owners`); cập nhật 5 schemas & 5 routers; cập nhật test assertions hiện có đọc `data["items"]`
  - [x] [verify] `./scripts/test.sh core infra server worker cli`
- [x] **M3 — Frontend `CursorPage` Consumers & `OwnerBadge` Display** (`usfds-web`, `all`): toàn bộ API clients, hooks, 11 module views và tests cập nhật sang `CursorPage` + hiển thị chủ sở hữu.
  - [x] [tests] Viết M3 acceptance test trong `featureVisibilityModules.test.tsx`; xác nhận fail
  - [x] [web] Cập nhật `types/*`, `api/*`, `hooks/*`, tạo `OwnerBadge.tsx`, gắn cột/nhãn chủ sở hữu và nút tải thêm `nextCursor` trên các views
  - [x] [verify] `./scripts/test.sh` + `cd usfds-web && npm run build && npm run lint`

Checkpoint log (the agent appends one line per finished milestone):
- 26-11-22 M1 done: `IUserRepository.get_by_ids` + `SqlUserRepository.get_by_ids` verified (`./scripts/test.sh core infra` — 162 passed, 15 skipped core; 43 passed infra); notes: `IUserRepository` lives in `usfds-core/src/usfds_core/repositories/base_user_repo.py`.
- 26-11-22 M2 done: `CursorPage` (`limit`, `cursor` -> `{items, nextCursor}`) on 8 list endpoints & `ResourceOwnerDto` batch-joined via `UserRepository.get_by_ids` on 7 resource DTOs (162 core, 43 infra, 42 server, 3 worker, 5 cli passed); notes: `test_list_endpoints_support_cursor_pagination_and_return_owner` passed after fixing `UUID` import.
- 26-11-22 M3 done: `OwnerBadge`, `CursorPage<T>` consumers (`useInfiniteQuery` / load-more), and 11 module views updated; `vitest` (20 files, 38 tests), `npm run build`, and `npm run lint` (0 errors) passed.

## 7. Review hotspots (filled in after implementation)
- `usfds-core/src/usfds_core/repositories/base_user_repo.py:21-24` & `usfds-infra/src/usfds_infra/database/repos/auth.py:93-100` — `get_by_ids(user_ids)` truy vấn lô bằng 1 câu `SELECT ... WHERE user_id IN (...)` và loại trùng thứ tự.
- `usfds-server/src/usfds_server/schemas/pagination.py:1-68` — `paginate_cursor` (cursor opaque base64url, trả `400` khi cursor sai định dạng) và `resolve_owners` (chỉ batch-join `owner` cho đúng `items` trên trang hiện tại).
- `usfds-server/src/usfds_server/routers/{project,dataset,training,rule,detection}_router.py` — 8 `GET` list endpoints trả `ApiResponse[CursorPage[...]]` và 7 resource DTO trả kèm `owner` (`None` cho built-in `Model`).
- `usfds-web/src/components/common/OwnerBadge.tsx` & `usfds-web/src/hooks/{useProjects,useDatasetList}.ts*` — component hiển thị `full_name || username` (tooltip `@username` + `user_id`, `Hệ thống` khi `null`) và `useInfiniteQuery` nối trang theo `nextCursor`.

## 8. Open questions
- —
