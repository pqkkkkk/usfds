# Plan: RBAC Feature Visibility Policy, UI Gating & Backend Router Hardening

> **Task ID:** `rbac_feature_visibility` (= this file name) · **Issues:** `ISS-037` · **Spec:** Notion `TASK-88` (`.plan/user_management_rbac.md`), `docs/features/detection/rule_management/suc-spec.md`, `docs/features/investigation/suc-spec.md`, pattern tham chiếu từ `use-actor-context.ts` & `feature-group-policy.ts`
> **Conflict verdict:** PARALLEL-SAFE · **Status:** Done (26-11-16)

## 1. Context (facts)
- Backend RBAC đã có `ActorContext` (`usfds-core/src/usfds_core/domain/entities/auth.py:103-112`) và `GET /api/v1/auth/me` trả về `AuthUserResponse` chứa đầy đủ `is_system_admin`, `system_role_keys`, `system_permissions`, `projects` (`usfds-server/src/usfds_server/routers/auth_router.py:25-50, 99-104`).
- Danh mục quyền chuẩn (`PERMISSION_CATALOG`, 54 permissions) và 5 vai trò mặc định nằm tại `usfds-infra/src/usfds_infra/database/seed_rbac.py:19-161`:
  - Đang có `rule:propose` (`seed_rbac.py:57, 147`) và `rule_router.py:93-97` — user xác nhận **không có permission `rule:propose`**.
  - Các sai lệch khác giữa `PERMISSION_CATALOG` và backend enforcement:
    1. `user_router.py:119, 138, 155` và `authz_service.py:180` đang kiểm tra `"user:manage"` (không có trong `PERMISSION_CATALOG`, vốn chỉ có `user:read`, `user:create`, `user:update`, `user:reset_password`).
    2. `authz_service.py:199-201` (`list_project_members`) đang kiểm tra `"project:read"` thay vì `"project_member:read"`.
    3. `detection_router.py:204-275`: `export_detection_job_results` và `send_to_investigation` chưa có `authz` check (và chưa có quyền riêng `detection:export` hay `case:create` / `case:intake`).
    4. Các endpoint con chưa gắn `authz.require_project_permission(...)`:
       - `dataset_router.py:204-362` (`get_dataset`, `delete_dataset`, `map_schema`, `get_artifact`, `execute_feature_engineering`, `export_normalized_dataset`)
       - `rule_router.py:143-541` (`get_rule`, `update_rule`, `set_rule_status`, `get_rule_versions`, `delete_rule`, `evaluate_single_rule`, `evaluate_project_rules`, `backtest_rule_on_dataset`)
       - `training_router.py:302-536` (`list_models`, `get_model`, `list_model_versions`, `get_model_version`, `get_model_version_lineage`, `activate_model_version`, `start_training_run`, `list_training_runs`, `get_training_run`, `get_training_run_lineage`)
       - `detection_router.py:119-275` (`get_detection_job`, `get_detection_job_results`, `export_detection_job_results`, `send_to_investigation`)
       - `investigation_router.py:153-245` (`kpis`, `feedback`, `get_case`, `workbench`, `draft`, `claim`, `pending`, `escalate`, `reopen`, `resolve`)
       - `insight_report_router.py:43-133` (`get_executive_overview`, `get_effectiveness_analysis`, `get_typology_and_patterns`)
- Trên frontend `usfds-web`:
  - `useAuth` (`usfds-web/src/hooks/useAuth.tsx:86-106`) chỉ có `hasPermission(permission, projectId?)` exact-match, mới dùng ở 3 chỗ (`UserAccountMenu.tsx:14`, `AdminUsersPage.tsx:25`, `ProjectMembersSection.tsx:9`).
  - `Sidebar.tsx:35-78`, `OmnisearchModal.tsx:31-38`, `App.tsx:99-108, 138`, `ProjectManagementView.tsx`, `ProjectSettingsView.tsx` và các màn hình nghiệp vụ đều chưa ẩn tính năng / chặn route theo `ActorContext`.

## 2. Goal, scope verdict & non-goals
- **Goal:** (1) Chuẩn hóa permission matrix (bỏ `rule:propose`, chốt phân quyền Rule & các điểm hở) và siết `authz` trên toàn bộ backend routers; (2) Xây dựng `feature-policy.ts` + `useActorContext` tái sử dụng `AuthUser` từ `/api/v1/auth/me`; (3) Ẩn hoàn toàn module/nút/tab thiếu quyền và bảo vệ route trên `usfds-web`.
- **Scope:** OK
- **Non-goals / omitted:**
  - Không tạo endpoint mới `/v1/access/actor-context` và không cài `zod` (tái sử dụng `useAuth().user` từ `GET /api/v1/auth/me`).
  - Không làm `GROUP_FEATURE` theo quốc gia (`flagCode`).
  - Không thêm bảng DB mới; nếu xóa `rule:propose` / bổ sung permission vào `seed_rbac.py`, có thể cần xử lý idempotent cleanup khi startup trong `seed_rbac` (không đổi schema bảng).
- **Assumptions:**
  - Mọi thành phần UI thiếu quyền sẽ bị **ẩn hoàn toàn** khỏi giao diện (kèm route guard khi truy cập URL trực tiếp).
  - Văn bản UI hoàn toàn bằng tiếng Việt theo `ISS-005` và `docs/design-system.md`.

## 3. Files
| Action | File | Milestone | Note |
|---|---|---|---|
| modify | `usfds-infra/src/usfds_infra/database/seed_rbac.py` | M1 | bỏ `rule:propose`; cập nhật `PERMISSION_CATALOG`/`ROLE_GRANTS` theo quyết định §8 và dọn `rule:propose` idempotent |
| modify | `usfds-core/src/usfds_core/services/auth/authz_service.py` | M1 | sửa `set_system_user_roles` (`user:update`), `list_project_members` (`project_member:read`) |
| modify | `usfds-server/src/usfds_server/routers/{user,dataset,rule,training,detection,investigation,insight_report}_router.py` | M1 | gắn `authz.require_*` cho toàn bộ endpoint còn thiếu; bỏ `rule:propose` trong `rule_router.py:93`; sửa `"user:manage"` trong `user_router.py` |
| modify | `usfds-server/tests/test_auth_and_rbac_api.py` | M1 | thêm tests cho endpoint hardening & permission matrix mới |
| create | `usfds-web/src/lib/feature-policy.ts` | M2 | `ACTOR_FEATURE` registry, `scopesOn`, `scopesFor`, `canOpenActorFeature`, `visibleProjectIds`, `firstAllowedModule` |
| create | `usfds-web/src/hooks/useActorContext.ts` | M2 | `FeatureAccess`, `useActorContext(projectId?)` đọc từ `useAuth()` |
| modify | `usfds-web/src/hooks/index.ts` | M2 | append-only export `useActorContext` |
| create | `usfds-web/src/lib/feature-policy.test.ts` | M2 | unit tests pure policy |
| create | `usfds-web/src/hooks/useActorContext.test.tsx` | M2 | hook tests |
| create | `usfds-web/src/components/layout/FeatureRouteGuard.tsx` | M3 | route guard + fallback UI tiếng Việt |
| modify | `usfds-web/src/components/layout/{Sidebar,OmnisearchModal,Topbar,UserAccountMenu}.tsx` | M3 | lọc module/quickActions/nút theo `features` |
| modify | `usfds-web/src/App.tsx` | M3 | gắn `FeatureRouteGuard` cho routes & fallback landing module |
| create | `usfds-web/src/test/featureVisibilityShell.test.tsx` | M3 | tests shell & route guards |
| modify | `usfds-web/src/components/modules/project_management/{ProjectManagementView,ProjectSchemaDrawer,ProjectSettingsView}.tsx` | M4 | ẩn/hiện thao tác project & `ProjectMembersSection` theo permission |
| create | `usfds-web/src/test/featureVisibilityProjects.test.tsx` | M4 | tests portal & settings |
| modify | `usfds-web/src/components/modules/data_management/{DatasetHubView,DatasetLineageExplorer,DataPipelineWorkspace}.tsx` | M5 | ẩn/hiện `dataset:create/update/delete/export` |
| modify | `usfds-web/src/components/modules/model/{ModelHubView,TrainingRunDetailView}.tsx` | M5 | ẩn/hiện `model:create`, `model_builtin:manage`, `training:create`, `deployment:deploy` |
| modify | `usfds-web/src/components/modules/rule/{RuleCatalogView,RuleWorkspace,RuleDryRunWorkspace}.tsx` | M5 | ẩn/hiện `rule:create/update/delete/dry_run/deploy/undeploy` |
| modify | `usfds-web/src/components/modules/detection/{DetectionJobsHubView,DetectionResultExplorerView}.tsx` | M5 | ẩn/hiện `detection:create`, export, send-to-investigation |
| modify | `usfds-web/src/components/modules/investigation/{CaseQueueView,CaseWorkbenchView,WorkbenchResolutionColumn,PoliciesView}.tsx` | M5 | ẩn/hiện `case:claim/assign/manual_review/escalate/reopen`, `blacklist:manage`, tạo rule nhanh |
| modify | `usfds-web/src/components/modules/{InsightReportModule,reports/ComplianceReportCenterTab}.tsx` | M5 | ẩn/hiện `report:create`, `report:export` |
| modify | `usfds-web/src/pages/AdminUsersPage.tsx` | M5 | ẩn/hiện theo `user:create/update/reset_password`, `role:read/manage` |
| create | `usfds-web/src/test/featureVisibilityModules.test.tsx` | M5 | tests module actions |

## 4. Dependencies & conflicts (with other tasks on BOARD)
| # | Check | Answer |
|---|---|---|
| D1 | Needs unfinished task? | No (`.plan/user_management_rbac.md` đã `Done (26-11-15)`) |
| D2 | Needed by unfinished task? | No |
| C1 | Modified files owned by in-progress task? | No |
| C2 | Hot-spot files touched | `usfds-web/src/App.tsx`, `usfds-web/src/components/layout/Sidebar.tsx`, `usfds-web/src/hooks/index.ts` (append-only / minimal diff) |
| C3 | Schema change | No |
| C4 | Public contract change | No (bổ sung enforcement 403 trên routers hiện có; bỏ `rule:propose`) |
| C5 | Shared UI shell change | Yes: `App.tsx`, `Sidebar.tsx`, `Topbar.tsx`, `OmnisearchModal.tsx` |

## 5. Acceptance tests (user reviews this section)
| Milestone | Test | Given | When | Then | Covers |
|---|---|---|---|---|---|
| M1 | `test_all_project_routers_enforce_permissions_without_rule_propose` (`usfds-server/tests/test_auth_and_rbac_api.py`) | User có role không đủ quyền (vd. `fraud_analyst` gọi `DELETE /datasets/{id}`, `POST /training/runs`, `POST /rules/{id}/backtest`; `data_scientist` gọi `GET /cases/kpis`, `GET /reports/sar/{id}`) | Gọi trực tiếp các endpoint con đã vá | Server trả `403 Forbidden`; `rule:propose` không còn trong catalog; `user:update`/`user:reset_password` hoạt động đúng trên `user_router` | `ISS-037` / `TASK-88` |
| M2 | `test_feature_policy_prefix_exact_and_visible_projects` (`usfds-web/src/lib/feature-policy.test.ts`) | `ActorContext` có các project roles khác nhau & `is_system_admin` | Gọi `canOpenActorFeature`, `visibleProjectIds`, `firstAllowedModule` | Prefix & exact key khớp chuẩn; `visibleProjectIds` trả đúng danh sách project hoặc `null` cho `system_admin` | `ISS-037` / Pattern `feature-group-policy` |
| M2 | `test_use_actor_context_resolves_project_features` (`usfds-web/src/hooks/useActorContext.test.tsx`) | User `analyst1` đang chọn Project 1 | Render `useActorContext(PROJECT_1_ID)` | Trả `features.<key>.allowed` đúng theo `AuthUser` từ `useAuth()` | `ISS-037` / Pattern `use-actor-context` |
| M3 | `test_sidebar_omnisearch_and_route_guard_by_role` (`usfds-web/src/test/featureVisibilityShell.test.tsx`) | User đăng nhập `fraud_analyst` vs `data_scientist` | Render `WorkspaceShell`, mở `OmnisearchModal`, truy cập URL bị cấm (`/models`, `/investigation`, `/admin/users`) | Ẩn module không có quyền khỏi Sidebar & Omnisearch; truy cập URL bị chặn hiển thị thông báo tiếng Việt | `ISS-037` / `TASK-88` |
| M4 | `test_project_portal_and_settings_gates` (`usfds-web/src/test/featureVisibilityProjects.test.tsx`) | User là `fraud_analyst` ở Project 1 và `project_admin` ở Project 2 | Render `/projects` và `/settings` | Ẩn hoàn toàn nút tạo/sửa/lưu trữ/xóa/reset schema và `ProjectMembersSection` khi thiếu quyền | `ISS-037` / `SUC-24..26` |
| M5 | `test_module_actions_hidden_for_insufficient_permissions` (`usfds-web/src/test/featureVisibilityModules.test.tsx`) | Render các module dưới 3 role `fraud_analyst`, `data_scientist`, `project_admin` | Kiểm tra sự hiện diện của nút/tab theo permission matrix | Ẩn hoàn toàn nút/tab thiếu quyền ở Datasets, Models, Rules, Detection, Investigation, Reports, Admin Users | `ISS-037` / `seed_rbac.py` |

## 6. Milestones & to-do (checkpoints, not stop points: all tests green at each)
The agent ticks items as it works. This is the task's only to-do list (`TODO.md` is no longer used for new work).

- [x] **M1 — Permission Matrix Cleanup & Backend Router Hardening** (`usfds-core`, `usfds-infra`, `usfds-server`):
  - [x] [tests] Viết M1 tests trong `usfds-server/tests/test_auth_and_rbac_api.py` (kiểm tra 403 cho các endpoint con & quyền rule/user/member)
  - [x] [infra] Cập nhật `seed_rbac.py` (bỏ `rule:propose`, dọn bản ghi cũ nếu có, bổ sung/điều chỉnh quyền theo §8)
  - [x] [core] Cập nhật `authz_service.py` (`user:update`, `project_member:read`)
  - [x] [server] Gắn `authz.require_*` trên `user`, `dataset`, `rule`, `training`, `detection`, `investigation`, `insight_report` routers
  - [x] [verify] `./scripts/test.sh core infra server`
- [x] **M2 — `ActorContext` Policy Layer & `useActorContext` Hook** (`usfds-web`):
  - [x] [tests] Viết `feature-policy.test.ts` và `useActorContext.test.tsx`
  - [x] [web] Tạo `usfds-web/src/lib/feature-policy.ts` và `usfds-web/src/hooks/useActorContext.ts`, export trong `hooks/index.ts`
  - [x] [verify] `./scripts/test.sh web`
- [x] **M3 — Shell Navigation, Omnisearch & Route Guards** (`usfds-web`):
  - [x] [tests] Viết `featureVisibilityShell.test.tsx`
  - [x] [web] Tạo `FeatureRouteGuard.tsx`; cập nhật `App.tsx`, `Sidebar.tsx`, `OmnisearchModal.tsx`, `Topbar.tsx`, `UserAccountMenu.tsx`
  - [x] [verify] `./scripts/test.sh web`
- [x] **M4 — Project Portal & Project Settings Gating** (`usfds-web`):
  - [x] [tests] Viết `featureVisibilityProjects.test.tsx`
  - [x] [web] Cập nhật `ProjectManagementView.tsx`, `ProjectSchemaDrawer.tsx`, `ProjectSettingsView.tsx`
  - [x] [verify] `./scripts/test.sh web`
- [x] **M5 — Domain Modules Intra-Feature Action Gating & Full Regression** (`usfds-web`, `all`):
  - [x] [tests] Viết `featureVisibilityModules.test.tsx`
  - [x] [web] Ẩn hành động thiếu quyền trên Data Management, Model & Training, Rule Engine, Detection, Investigation, Insight & Reports, `AdminUsersPage.tsx`
  - [x] [verify] `./scripts/test.sh` + `cd usfds-web && npm run build && npm run lint`

Checkpoint log (the agent appends one line per finished milestone):
- 26-11-16 M1 done: core 149 passed, 15 skipped · infra 35 passed, 1 xfailed · server 31 passed; notes: —
- 26-11-16 M2 done: web 14 files, 25 tests passed; notes: —
- 26-11-16 M3 done: web 15 files, 26 tests passed; notes: —
- 26-11-16 M4 done: web 16 files, 27 tests passed; notes: —
- 26-11-16 M5 done: all green (core 149 passed, 15 skipped · infra 35 passed, 1 xfailed · server 31 passed · worker 3 passed · cli 5 passed · web 17 files, 28 tests passed · build & lint 0 errors); notes: —

## 7. Review hotspots (filled in after implementation)
- [usfds-infra/src/usfds_infra/database/seed_rbac.py](file:///Users/pqkkkkk/hcmus/thesis/usfds/usfds-infra/src/usfds_infra/database/seed_rbac.py#L53-L75) và [#L182-L192](file:///Users/pqkkkkk/hcmus/thesis/usfds/usfds-infra/src/usfds_infra/database/seed_rbac.py#L182-L192) — bỏ `rule:propose` (và xóa idempotent khỏi DB cũ), bổ sung `detection:export` và `case:create`, giữ PA-A cho `fraud_analyst` (`rule:read` only).
- [usfds-server/src/usfds_server/routers/investigation_router.py](file:///Users/pqkkkkk/hcmus/thesis/usfds/usfds-server/src/usfds_server/routers/investigation_router.py#L226-L257) — tách kiểm tra `case:assign` vs `case:claim` theo người nhận và khóa quyền trên mọi action điều tra; cùng Pattern hardening trên `user`, `dataset`, `rule`, `training`, `detection`, `insight_report` routers.
- [usfds-web/src/lib/feature-policy.ts](file:///Users/pqkkkkk/hcmus/thesis/usfds/usfds-web/src/lib/feature-policy.ts#L33-L100) — bảng `ACTOR_FEATURE` & `MODULE_FEATURE_MAP` tập trung quy tắc ẩn/hiện toàn hệ thống theo `ActorContext`.
- [usfds-web/src/hooks/useActorContext.ts](file:///Users/pqkkkkk/hcmus/thesis/usfds/usfds-web/src/hooks/useActorContext.ts#L39-L69) — hook `useActorContext(projectId?)` tái sử dụng `useAuth()` (`/api/v1/auth/me`) trả về `{ actor, loading, error, features, can }`.
- [usfds-web/src/components/layout/FeatureRouteGuard.tsx](file:///Users/pqkkkkk/hcmus/thesis/usfds/usfds-web/src/components/layout/FeatureRouteGuard.tsx#L14-L56) và [usfds-web/src/App.tsx](file:///Users/pqkkkkk/hcmus/thesis/usfds/usfds-web/src/App.tsx#L83-L177) — guard route trực tiếp, chờ `authLoading || isLoading` trước khi điều hướng, fallback về `defaultRoute` đầu tiên user có quyền.
- [usfds-web/src/pages/AdminUsersPage.tsx](file:///Users/pqkkkkk/hcmus/thesis/usfds/usfds-web/src/pages/AdminUsersPage.tsx#L25-L85) — tách quyền `user:read` / `role:read` / `user:create` / `user:update` / `user:reset_password`, tránh gọi API 403 khi thiếu quyền tab.

## 8. Open questions
- — (đã chốt với user 26-11-16: bỏ `rule:propose`; `fraud_analyst` chỉ giữ `rule:read` [PA-A]; `data_scientist` giữ 7 quyền rule; bổ sung `detection:export` và `case:create`; tách `case:assign` vs `case:claim`; sửa `user:manage` -> `user:update`/`user:reset_password` và `list_project_members` -> `project_member:read`; tái sử dụng `/api/v1/auth/me`; ẩn hoàn toàn UI thiếu quyền; tạo `ISS-037`).
