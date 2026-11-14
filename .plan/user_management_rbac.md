# Plan: User Management, Authentication & 3-Scope RBAC (`SYSTEM`, `PROJECT`, `OWN`)

> **Task ID:** `user_management_rbac` (= this file name) · **Issues:** ISS-006 · **Spec:** Notion `TASK-88` (*Thiết kế chính sách kiểm soát truy cập cho FDS*), reference RBAC pattern from `src.zip` (`domain/access.ts`, `features/admin/rbac/rules.ts`)
> **Conflict verdict:** PARALLEL-SAFE · **Status:** Draft

## 1. Context (facts)
- Hệ thống hiện tại chưa có authentication hay RBAC: `User` chỉ là dataclass tối giản không có `password_hash`/`status` (`usfds-core/src/usfds_core/domain/entities/system.py:10-15`), chưa có bảng `users` hay các bảng RBAC trong schema baseline (`usfds-infra/src/usfds_infra/database/migrations/versions/0001_baseline_baseline_schema.py`).
- Backend hiện hardcode định danh giả: `get_actor() -> "local-analyst"` (`usfds-server/src/usfds_server/routers/investigation_router.py:33`), `"mock_user"` (`usfds-server/src/usfds_server/routers/training_router.py:174,189,255,269`), `prepared_by: str = "local-analyst"` (`usfds-server/src/usfds_server/routers/insight_report_router.py:141,170,205`).
- Frontend hiện hardcode `DEFAULT_USER_ID = '00000000-0000-0000-0000-000000000000'` (`usfds-web/src/hooks/useProjects.tsx:20,105`) và `'local-analyst'` (`usfds-web/src/components/modules/investigation/CaseQueueView.tsx:250`, `usfds-web/src/components/modules/reports/ComplianceReportCenterTab.tsx:36`).
- Sau Phase 0 (F2, F3), ORM và repository được tách theo domain tại `usfds-infra/src/usfds_infra/database/tables/` và `usfds-infra/src/usfds_infra/database/repos/`, FastAPI dependencies được tách tại `usfds-server/src/usfds_server/providers/`.
- Pattern RBAC trong `src.zip` (`domain/access.ts`, `features/admin/rbac/rules.ts`):
  - Entity trung tâm là `ActorContext` (gồm `projects: list[ProjectPermissions]`, `system_role_keys`, `system_permissions`, `is_system_admin`), được load qua `get_actor_context` và sanitize scope theo nhánh (`keep_scopes`: project branch chỉ giữ `OWN`/`PROJECT`, system branch chỉ giữ `SYSTEM`).
  - Enforcement xoay quanh 4 hàm thống nhất: `can_list`, `can_read`, `can_create`, `can_mutate`.
  - Management chống leo thang quyền qua `delegation_refusal`, `super_admin_refusal`, `assert_grant_scopes`, `assert_scope_change_allowed`.

## 2. Goal, scope verdict & non-goals
- **Goal:** Triển khai User Management, Authentication (`required` với JWT + Refresh Token và `local_auto` cho Desktop) và 3-Scope Data-Driven RBAC (`SYSTEM`, `PROJECT`, `OWN`) theo mô hình `ActorContext` + `can_list`/`can_read`/`can_create`/`can_mutate` trên `usfds-core`, `usfds-infra`, `usfds-server`, `usfds-web`.
- **Scope:** OK
- **Non-goals / omitted:**
  - Không tạo bảng `organizations` (Single-Tenant self-hosted; `platform` + `organization` gộp thành `SYSTEM`).
  - Không tạo bảng `authz_audit` (giữ tối giản 7 bảng Auth/RBAC).
  - Không dùng Supabase Auth / `platform_accounts` như `src.zip`; USFDS dùng username + password (`Argon2id`/`bcrypt`) + JWT nội bộ.
  - Không làm giao diện quản lý API keys (giữ cấu hình trong `.env.example` và `config.py`).
  - Không sửa `usfds-cli` hoặc `usfds-agent` trong task này.
- **Assumptions:**
  - Ánh xạ từ `src.zip`: `own` -> `OWN`, `market` -> `PROJECT`, `global` -> `SYSTEM`; `Market` -> `Project`.
  - Bảng `project_members` dùng khóa chính phức hợp `(project_id, user_id, role_id)` để **hỗ trợ 1 user giữ nhiều role trong cùng 1 project** mà không cần thêm bảng trung gian.
  - `project_admin` được phép quản lý `project_members` trong project của mình (bị chặn leo thang quyền bởi `delegation_refusal`); chỉ `system_admin` mới quản lý định nghĩa `roles`/`role_permissions` và `users`.
  - Toàn bộ migration/query tương thích cả SQLite (Desktop) và PostgreSQL (Client-Server), tuân thủ PG-compat guards.

## 3. Files
| Action | File | Milestone | Note |
|---|---|---|---|
| modify | `usfds-core/src/usfds_core/domain/entities/enums.py` | M1 | append-only: `UserStatus`, `RoleScope`, `GrantScope`, `AuthMode` |
| modify | `usfds-core/src/usfds_core/domain/entities/system.py` | M1 | mở rộng `User` (`full_name`, `password_hash`, `status`, `last_login_at`, `updated_at`) |
| create | `usfds-core/src/usfds_core/domain/entities/auth.py` | M1 | `Role`, `Permission`, `RolePermission`, `ProjectMember`, `UserSession`, `ProjectPermissions`, `ActorContext`, `AccessTarget`, `BaseQueryFilter`, `PermissionDeniedError` |
| create | `usfds-core/src/usfds_core/repositories/base_user_repo.py` | M1 | `IUserRepository` |
| create | `usfds-core/src/usfds_core/repositories/base_rbac_repo.py` | M1 | `IRoleRepository`, `IPermissionRepository`, `IProjectMemberRepository` (kèm `load_actor_context`) |
| create | `usfds-core/src/usfds_core/repositories/base_session_repo.py` | M1 | `IUserSessionRepository` |
| modify | `usfds-core/src/usfds_core/repositories/__init__.py` | M1 | append-only exports |
| create | `usfds-infra/src/usfds_infra/database/tables/auth.py` | M1 | 7 ORM tables: `users`, `user_sessions`, `roles`, `permissions`, `role_permissions`, `system_user_roles`, `project_members` (PK `(project_id, user_id, role_id)`) |
| modify | `usfds-infra/src/usfds_infra/database/tables/__init__.py` | M1 | append-only |
| create | `usfds-infra/src/usfds_infra/database/repos/auth.py` | M1 | `SqlUserRepository`, `SqlRoleRepository`, `SqlPermissionRepository`, `SqlProjectMemberRepository`, `SqlUserSessionRepository` |
| modify | `usfds-infra/src/usfds_infra/database/repos/__init__.py` | M1 | append-only |
| modify | `usfds-infra/src/usfds_infra/database/__init__.py` | M1 | append-only |
| create | `usfds-infra/src/usfds_infra/database/seed_rbac.py` | M1 | seed idempotent 5 roles, permissions, role_permissions, bootstrap admin & backfill `project_members` |
| migration | `usfds-infra/src/usfds_infra/database/migrations/versions/<rev>_add_auth_and_rbac.py` | M1 | 1 Alembic revision duy nhất |
| create | `usfds-core/src/usfds_core/services/auth/security.py` | M2 | `IPasswordHasher`, `ITokenProvider` |
| create | `usfds-core/src/usfds_core/services/auth/auth_service.py` | M2 | `login`, `refresh`, `logout`, `change_password`, `update_own_profile`, `create_user`, `list_users`, `get_user`, `update_user`, `set_user_status`, `reset_password` |
| create | `usfds-infra/src/usfds_infra/security/__init__.py` | M2 | `PasswordHasher` (`pwdlib[argon2]`/`bcrypt`) & `JwtTokenProvider` (`PyJWT`) |
| modify | `usfds-server/pyproject.toml` | M2 | thêm `pyjwt`, `pwdlib[argon2]` (hoặc `bcrypt`) |
| modify | `usfds-server/src/usfds_server/config.py` | M2 | append-only: `auth_mode`, `jwt_secret`, `access_token_expire_minutes`, `refresh_token_expire_days`, `bootstrap_admin_*`, `cors_origins` |
| modify | `deploy/.env.example` | M2 | append-only auth env vars |
| modify | `deploy/docker-compose.yml` | M2 | set `USFDS_AUTH_MODE=required` |
| create | `usfds-server/src/usfds_server/providers/auth.py` | M2 | `get_current_user` (`required` & `local_auto`), `get_auth_service`, `get_authz_service` |
| modify | `usfds-server/src/usfds_server/dependencies.py` | M2 | gọi `seed_rbac` trong `setup_infrastructure()` |
| create | `usfds-server/src/usfds_server/schemas/auth_schemas.py` | M2 | schemas cho auth, users, rbac, project members |
| create | `usfds-server/src/usfds_server/routers/auth_router.py` | M2 | `/api/v1/auth` (`mode`, `login`, `refresh`, `logout`, `me`, `me/password`) |
| modify | `usfds-server/src/usfds_server/api.py` | M2 | append-only router registration |
| create | `usfds-core/src/usfds_core/services/auth/access_logic.py` | M3 | port từ `src.zip`: `get_actor_context`, `held_scope`, `broadest_scope`, `effective_scope`, `scope_covers`, `can_list`, `can_read`, `can_create`, `can_mutate`, `group_by_owner` |
| create | `usfds-core/src/usfds_core/services/auth/authz_service.py` | M3 | `AuthzService` (M3: enforcement `get_actor_context`, `can_list`, `can_read`, `can_create`, `can_mutate`; M4: thêm management methods) |
| modify | `usfds-core/src/usfds_core/services/project_management/project_service.py` | M3 | lọc `list_projects_for_user` theo `can_list` / `ActorContext`, auto-add creator làm `project_admin` |
| modify | `usfds-server/src/usfds_server/providers/auth.py` | M3 | thêm `get_actor_context`, `require_permission(...)` |
| modify | `usfds-server/src/usfds_server/routers/*.py` | M3 | enforce `can_list`/`can_read`/`can_create`/`can_mutate` trên toàn bộ routers, bỏ `mock_user`/`local-analyst`, siết `storage_router.py` |
| modify | `usfds-core/src/usfds_core/services/auth/access_logic.py` | M4 | bổ sung anti-escalation từ `src.zip`: `delegation_refusal`, `super_admin_refusal`, `role_change_refusal`, `assert_grant_scopes`, `assert_scope_change_allowed`, `is_valid_role_key` |
| modify | `usfds-core/src/usfds_core/services/auth/authz_service.py` | M4 | quản lý `project_members` (kèm bảo vệ `project_admin` cuối cùng), `system_user_roles`, `roles`, `role_permissions` |
| create | `usfds-server/src/usfds_server/routers/user_router.py` | M4 | `/api/v1/users` (SYSTEM scope) |
| create | `usfds-server/src/usfds_server/routers/rbac_router.py` | M4 | `/api/v1/rbac` (`roles`, `permissions`, `roles/{id}/permissions`) |
| modify | `usfds-server/src/usfds_server/routers/project_router.py` | M4 | thêm `/api/v1/projects/{project_id}/members` |
| create | `usfds-web/src/types/auth.ts` | M5 | `AuthUser`, `AuthModeResponse`, `LoginRequest`, `RoleDto`, `PermissionDto`, `ProjectMemberDto`, `AdminUserDto` |
| create | `usfds-web/src/api/authApi.ts` | M5 | auth endpoints |
| create | `usfds-web/src/api/userAdminApi.ts` | M5 | admin user & rbac endpoints |
| create | `usfds-web/src/api/projectMemberApi.ts` | M5 | project members endpoints |
| modify | `usfds-web/src/api/client.ts` | M5 | gắn `Authorization: Bearer`, single-flight refresh khi `401` |
| create | `usfds-web/src/hooks/useAuth.tsx` | M5 | `AuthProvider`, `hasPermission(code, projectId?)`, `isSystemAdmin`, `logout` |
| create | `usfds-web/src/pages/LoginPage.tsx` | M5 | màn hình đăng nhập (ẩn khi `local_auto`) |
| create | `usfds-web/src/pages/AdminUsersPage.tsx` | M5 | quản lý Users & Role-Permission Matrix |
| create | `usfds-web/src/components/modules/auth/ProfileModal.tsx` | M5 | thông tin tài khoản + đổi mật khẩu |
| modify | `usfds-web/src/components/modules/project_management/ProjectSettingsView.tsx` | M5 | thêm tab Members & Access |
| modify | `usfds-web/src/components/layout/Topbar.tsx` | M5 | hiển thị user thật, menu Profile / Admin / Logout |
| modify | `usfds-web/src/App.tsx` | M5 | route `/login`, `/admin/users`, AuthProvider guard |
| modify | `usfds-web/src/hooks/useProjects.tsx`, `CaseQueueView.tsx`, `ComplianceReportCenterTab.tsx`, `insightReportApi.ts` | M5 | bỏ `DEFAULT_USER_ID` và `'local-analyst'` |

## 4. Dependencies & conflicts (with other tasks on BOARD)
| # | Check | Answer |
|---|---|---|
| D1 | Needs unfinished task? | No (Phase 0 đã Done) |
| D2 | Needed by unfinished task? | No |
| C1 | Modified files owned by in-progress task? | No |
| C2 | Hot-spot files touched | `enums.py`, `repositories/__init__.py`, `database/__init__.py`, `tables/__init__.py`, `repos/__init__.py`, `api.py`, `dependencies.py`, `config.py`, `deploy/.env.example`, `App.tsx`, `client.ts` (append-only) |
| C3 | Schema change | Yes: 7 bảng Auth/RBAC trong 1 Alembic revision riêng |
| C4 | Public contract change | Yes: thêm `Authorization: Bearer` khi `USFDS_AUTH_MODE=required`; bỏ `user_id`/`created_by` từ payload -> `usfds-web` cập nhật cùng task trong M5 |
| C5 | Shared UI shell change | Yes: `usfds-web/src/App.tsx`, `Topbar.tsx`, `client.ts` |

## 5. Acceptance tests (user reviews this section)
| Milestone | Test | Given | When | Then | Covers |
|---|---|---|---|---|---|
| M1 | `test_schema_supports_multi_role_per_project_and_idempotent_seed` (`usfds-infra/tests/test_auth_repositories.py`) | DB sạch có 1 project cũ chưa có member | Chạy `seed_rbac` 2 lần, rồi gán 2 roles (`data_scientist`, `fraud_analyst`) cho cùng 1 user trên project đó | Seed không trùng lặp; `project_members` lưu được cả 2 roles và `load_actor_context` gộp đủ permissions của cả 2 | ISS-006 |
| M2 | `test_required_mode_auth_lifecycle` (`usfds-server/tests/test_auth_and_rbac_api.py`) | `USFDS_AUTH_MODE=required`, user active đã seed | `POST /auth/login` -> `GET /auth/me` -> `POST /auth/refresh` -> `POST /auth/logout` | Trả JWT + refresh token; token sau logout bị `401`; user `DISABLED` bị từ chối login và thu hồi session | ISS-006 |
| M2 | `test_local_auto_mode_bootstraps_admin` (`usfds-server/tests/test_auth_and_rbac_api.py`) | `USFDS_AUTH_MODE=local_auto` | Gọi `GET /api/v1/auth/mode` và `GET /api/v1/auth/me` không kèm Bearer | `mode == local_auto`; `/auth/me` trả về bootstrap local `system_admin` | ISS-006 |
| M3 | `test_actor_context_and_four_access_checks` (`usfds-core/tests/test_authz_enforcement.py`) | `ActorContext` có `fraud_analyst` (`OWN` cho `rule:update`) ở Project A và không thuộc Project B | Gọi `can_list`, `can_read`, `can_create`, `can_mutate` trên A (owner=self/other) và B | `can_list` trả filter `owner_id=self` cho A, `403` nếu đòi B; `can_mutate` allow A(self), deny A(other) & B | ISS-006 |
| M3 | `test_router_rbac_isolation_and_storage_guard` (`usfds-server/tests/test_auth_and_rbac_api.py`) | `USFDS_AUTH_MODE=required`, User A thuộc Project 1, không thuộc Project 2 | User A gọi API của Project 2 hoặc `storage/presigned-download` với `object_key` của Project 2 | Server trả `403 Forbidden`; không còn endpoint nào nhận `mock_user`/`local-analyst` | ISS-006 |
| M4 | `test_delegation_and_system_only_refusal` (`usfds-core/tests/test_authz_management.py`) | `project_admin` chỉ giữ quyền trong Project A | Gọi `assign_project_member` với `system_admin` hoặc role có quyền vượt quá quyền của caller | Bị từ chối (`PermissionDeniedError`), chống leo thang quyền | ISS-006 |
| M4 | `test_cannot_remove_last_project_admin` (`usfds-core/tests/test_authz_management.py`) | Project A chỉ còn 1 `project_admin` | Gọi xóa hoặc hạ quyền `project_admin` cuối cùng | Raise lỗi nghiệp vụ không cho xóa/hạ quyền | ISS-006 |
| M4 | `test_admin_user_and_rbac_endpoints` (`usfds-server/tests/test_auth_and_rbac_api.py`) | `system_admin` và `fraud_analyst` | Cả 2 gọi `/api/v1/users`, `/api/v1/rbac/roles/{id}/permissions`, `/api/v1/projects/{id}/members` | `system_admin` thành công (`200`/`201`); `fraud_analyst` bị `403` | ISS-006 |
| M5 | `test_login_and_permission_gated_ui` (`usfds-web/src/test/authRbac.test.tsx`) | MSW mock `mode=required`, user login với role `fraud_analyst` | Render App, đăng nhập, điều hướng Project Settings & Admin | Ẩn menu Admin Users; tab Members chỉ hiển thị đúng quyền; `401` kích hoạt single-flight refresh | ISS-006 |

## 6. Milestones & to-do (checkpoints, not stop points: all tests green at each)
The agent ticks items as it works. This is the task's only to-do list.

- [ ] **M1 — Entities, ORM Tables, Repos, Alembic & Seed** (`usfds-core`, `usfds-infra`):
  - [ ] [tests] Viết M1 tests trong `usfds-infra/tests/test_auth_repositories.py`; xác nhận fail đúng lý do
  - [ ] [core] Thêm enums, mở rộng `User`, tạo `entities/auth.py` (kèm `ActorContext`, `ProjectPermissions`, `AccessTarget`, `BaseQueryFilter`), tạo repository interfaces (`base_user_repo.py`, `base_rbac_repo.py`, `base_session_repo.py`)
  - [ ] [infra] Tạo `tables/auth.py` (PK `(project_id, user_id, role_id)` trên `project_members`), `repos/auth.py`, `seed_rbac.py`, và 1 Alembic migration revision
  - [ ] [verify] `./scripts/test.sh core infra`
- [ ] **M2 — Auth: Sign-in, User Lifecycle, JWT & Session Operations** (`usfds-core`, `usfds-infra`, `usfds-server`, `deploy/`):
  - [ ] [tests] Viết M2 tests trong `usfds-server/tests/test_auth_and_rbac_api.py` (login, refresh, logout, disable, `local_auto`)
  - [ ] [core] Tạo `security.py` (`IPasswordHasher`, `ITokenProvider`) và `auth_service.py`
  - [ ] [infra] Tạo `usfds_infra/security/` (`PasswordHasher`, `JwtTokenProvider`)
  - [ ] [server] Cập nhật `config.py`, `pyproject.toml`, `deploy/`, `dependencies.py` (gọi `seed_rbac`), tạo `providers/auth.py`, `auth_schemas.py`, `auth_router.py`
  - [ ] [verify] `./scripts/test.sh core infra server`
- [ ] **M3 — Authz Enforcement (`ActorContext` + `can_list`/`can_read`/`can_create`/`can_mutate`)** (`usfds-core`, `usfds-server`):
  - [ ] [tests] Viết M3 tests (`usfds-core/tests/test_authz_enforcement.py` và router isolation tests trong `usfds-server/tests/test_auth_and_rbac_api.py`)
  - [ ] [core] Port `access_logic.py` (`get_actor_context`, `can_list`, `can_read`, `can_create`, `can_mutate`, `group_by_owner`), tạo `authz_service.py` (enforcement), cập nhật `project_service.py`
  - [ ] [server] Thêm `get_actor_context` & `require_permission` vào `providers/auth.py`; gắn enforcement lên toàn bộ routers hiện có; bỏ `mock_user`/`local-analyst`; siết `storage_router.py`
  - [ ] [verify] `./scripts/test.sh core infra server`
- [ ] **M4 — Authz Management (Admin Users, Roles, Project Members & Anti-Escalation)** (`usfds-core`, `usfds-server`):
  - [ ] [tests] Viết M4 tests (`usfds-core/tests/test_authz_management.py` và admin/member API tests trong `usfds-server/tests/test_auth_and_rbac_api.py`)
  - [ ] [core] Bổ sung `delegation_refusal`, `super_admin_refusal`, `role_change_refusal`, `assert_grant_scopes`, `assert_scope_change_allowed` vào `access_logic.py` và các hàm quản lý vào `authz_service.py` (kèm bảo vệ `project_admin` cuối cùng)
  - [ ] [server] Tạo `user_router.py`, `rbac_router.py`, mở rộng `project_router.py` (`/members`)
  - [ ] [verify] `./scripts/test.sh core infra server`
- [ ] **M5 — Frontend Auth, Admin & Project Members UI** (`usfds-web`):
  - [ ] [tests] Viết M5 tests (`usfds-web/src/test/authRbac.test.tsx`) với vitest + MSW
  - [ ] [web] Tạo `types/auth.ts`, `authApi.ts`, `userAdminApi.ts`, `projectMemberApi.ts`, cập nhật `client.ts` (single-flight refresh) và `useAuth.tsx`
  - [ ] [web] Tạo `LoginPage.tsx`, `AdminUsersPage.tsx`, `ProfileModal.tsx`, mở rộng `ProjectSettingsView.tsx`, cập nhật `Topbar.tsx`, `App.tsx`, xóa `DEFAULT_USER_ID` & `'local-analyst'`
  - [ ] [verify] `./scripts/test.sh web` + build/lint
- [ ] **M6 — Full Regression & Report** (`all`):
  - [ ] [verify] `./scripts/test.sh` toàn bộ packages

Checkpoint log (the agent appends one line per finished milestone):
- —

## 7. Review hotspots (filled in after implementation)
- —

## 8. Open questions
- — (đã chốt toàn bộ với user)
