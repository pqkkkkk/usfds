# Plan: User Management, Authentication & 3-Scope RBAC (`SYSTEM`, `PROJECT`, `OWN`)

> **Issue:** [docs/issues/11-13-2026.md](file:///d:/Thesis/4. Implementation/usfds/docs/issues/11-13-2026.md#L3)  
> **Reference:** Notion `TASK-88` (*Thiết kế chính sách kiểm soát truy cập cho FDS*)  
> **Architecture Baseline:** Single-tenant self-hosted (`Client-Server` + `Local Desktop`), Clean Architecture (`usfds-core` -> `usfds-infra` -> `usfds-server` / `usfds-web`).

---

## 1. Quyết định Kiến trúc Cốt lõi

1. **Bỏ bảng `organizations` — Sử dụng 3 Permission Scopes (`SYSTEM`, `PROJECT`, `OWN`):**
   - Do hệ thống phục vụ mô hình mỗi tổ chức tự host (Single-Tenant), `platform` và `organization` trùng nhau về ngữ nghĩa. Tinh gọn thành 3 scopes:
     - **`SYSTEM`**: Quản trị toàn hệ thống (users, system roles, built-in models, system metadata, xem tất cả projects/audit).
     - **`PROJECT`**: Phân quyền theo từng Project qua `project_members (project_id, user_id, role_id)` (bám sát nguyên tắc *"Access control per project first"* trong `TASK-88`).
     - **`OWN`**: Tài nguyên cá nhân (`me` profile/password/sessions) và tài nguyên trong Project do user sở hữu/được giao (`created_by == user_id`, `assigned_to == user_id`).
   - *Non-breaking extensibility:* Nếu sau này mở rộng thành Multi-tenant SaaS, chỉ cần thêm `organizations`, `organization_members`, cột `org_id` trên `projects`/`roles`, và giá trị `ORGANIZATION` vào `RoleScope` mà không phá vỡ cấu trúc hiện tại.
2. **Data-Driven RBAC:**
   - Quyền được cấu hình trong DB (`roles`, `permissions`, `role_permissions`) thay vì hardcode role names trong nghiệp vụ. Bổ sung role mới (ví dụ `Risk Manager`) hoặc điều chỉnh ma trận quyền `TASK-88` chỉ là thay đổi dữ liệu seed/cấu hình.
3. **Authentication (Username + Password) & 2 Chế độ Triển khai:**
   - **Client-Server (`USFDS_AUTH_MODE=required`):** Xác thực bằng `username` + `password` (hash bằng `Argon2id` / `bcrypt`), cấp **JWT Access Token** (ngắn hạn) + **Refresh Token** (lưu hash trong DB `user_sessions`, hỗ trợ revoke/logout).
   - **Local Desktop (`USFDS_AUTH_MODE=local_auto`):** Tự động bootstrap 1 tài khoản `system_admin` cục bộ khi khởi động và auto-inject vào `CurrentUser` (không hiển thị màn hình Login).
   - **No custom UI for API keys:** Toàn bộ cấu hình auth/secret đặt trong `.env.example` và `usfds-server/src/usfds_server/config.py`.

---

## 2. Thiết kế ERD & Mô hình Dữ liệu

### 2.1. Các bảng mới (`usfds-infra/src/usfds_infra/database/auth_models.py`)

| Bảng | Cột chính | Ràng buộc / Ghi chú |
| :--- | :--- | :--- |
| **`users`** | `user_id` (PK, UUID), `username` (Unique, Indexed), `email` (Unique, Nullable), `full_name`, `password_hash`, `status` (`ACTIVE` \| `DISABLED`), `last_login_at`, `created_at`, `updated_at` | Thay thế `user_id` / `created_by` giả lập hiện tại. |
| **`user_sessions`** | `session_id` (PK), `user_id` (FK -> `users`, CASCADE), `refresh_token_hash` (Unique, Indexed), `expires_at`, `revoked_at`, `user_agent`, `ip_address`, `created_at` | Hỗ trợ refresh token rotation, logout và thu hồi ngay khi user bị `DISABLED`. |
| **`roles`** | `role_id` (PK), `name`, `display_name`, `scope` (`SYSTEM` \| `PROJECT`), `is_system` (Bool), `description`, `created_at`, `updated_at` | `UniqueConstraint("scope", "name")`. Built-in roles có `is_system = True`. |
| **`permissions`** | `permission_id` (PK), `code` (Unique, `resource:action`), `resource`, `action`, `scope` (`SYSTEM` \| `PROJECT` \| `OWN`), `description` | Catalog chuẩn hóa toàn bộ hành động trên hệ thống. |
| **`role_permissions`** | `role_id` (PK, FK -> `roles`, CASCADE), `permission_id` (PK, FK -> `permissions`, CASCADE), `grant_scope` (`ALL` \| `OWN`) | Cho phép phân biệt quyền trên toàn Project (`ALL`) hoặc chỉ trên dữ liệu của mình (`OWN`). |
| **`system_user_roles`** | `user_id` (PK, FK -> `users`, CASCADE), `role_id` (PK, FK -> `roles`, CASCADE), `assigned_by`, `created_at` | Gán role cấp `SYSTEM` (`system_admin`, `system_member`). |
| **`project_members`** | `project_id` (PK, FK -> `projects`, CASCADE), `user_id` (PK, FK -> `users`, CASCADE), `role_id` (FK -> `roles`), `added_by`, `created_at`, `updated_at` | Gán role cấp `PROJECT` (`project_admin`, `data_scientist`, `fraud_analyst`). |

### 2.2. Ma trận Seed Mặc định (Bám sát `TASK-88` & lấp đầy khoảng trống)

- **System Roles (`scope = SYSTEM`):**
  - `system_admin`: Toàn quyền `SYSTEM` (`user:*`, `role:*`, `project:create`, `project:list_all`, `audit:system_read`, `model_builtin:manage`) + quyền `PROJECT` đầy đủ khi truy cập bất kỳ project nào.
  - `system_member`: Quyền cơ bản (`project:create`, `project:list_own`, `own:profile_read`, `own:profile_update`, `own:password_change`, `own:session_manage`). Chỉ thấy và thao tác trên các Project mà mình là thành viên.
- **Project Roles (`scope = PROJECT`):**
  - `project_admin` (*Admin*): `project:read/update/delete/reset_schema`, `project_member:read/manage`, `dataset:read/export`, `model:read/update`, `training:read`, `deployment:deploy/undeploy`, `rule:read`, `detection:create/read`, `case:read/assign`, `report:read/create/export`, `audit:read`.
  - `data_scientist` (*Data Scientist*): `project:read`, `dataset:create/read/update/delete/export`, `model:create/read/update`, `training:create/read`, `deployment:deploy/undeploy`, `rule:create/read/update/delete/dry_run/deploy/undeploy`, `detection:create/read`, `report:read`.
  - `fraud_analyst` (*Fraud Analyst*): `project:read`, `dataset:read`, `rule:read`, `rule:propose` (`DRAFT`/`SHADOW`), `detection:create/read`, `case:read/claim/manual_review/escalate/reopen`, `blacklist:manage`, `report:read/create/export`, `audit:read` (case audit).
- **Thuật toán Kiểm tra Quyền (`AuthorizationService.authorize`):**
  1. Xác thực `CurrentUser` (`status == ACTIVE`).
  2. Nếu có permission ở scope `SYSTEM` -> **Allow**.
  3. Nếu request gắn `project_id`: kiểm tra user thuộc `project_members` của `project_id`.
     - Role trong project có `permission_code` với `grant_scope == ALL` -> **Allow**.
     - Role trong project có `permission_code` với `grant_scope == OWN` và `resource_owner_id == current_user.user_id` -> **Allow**.
  4. Nếu request ở scope `OWN` (`target_user_id == current_user.user_id`) -> **Allow**.
  5. Ngược lại -> Raise `PermissionDeniedError` (`HTTP 403`).

---

## 3. Các Giai đoạn Triển khai Chi tiết

### Phase 1: Core Domain, Interfaces & Services (`usfds-core`)
1. **[`usfds-core/src/usfds_core/domain/entities/enums.py`](file:///d:/Thesis/4. Implementation/usfds/usfds-core/src/usfds_core/domain/entities/enums.py)**:
   - Thêm `UserStatus`, `RoleScope`, `GrantScope`, `AuthMode`.
2. **[`usfds-core/src/usfds_core/domain/entities/auth.py`](file:///d:/Thesis/4. Implementation/usfds/usfds-core/src/usfds_core/domain/entities/auth.py)** *(mới)* & [`system.py`](file:///d:/Thesis/4. Implementation/usfds/usfds-core/src/usfds_core/domain/entities/system.py):
   - Mở rộng `User` (`full_name`, `password_hash`, `status`, `last_login_at`, `updated_at`), thêm dataclasses `Role`, `Permission`, `RolePermission`, `ProjectMember`, `UserSession`, `CurrentUser`, `PermissionDeniedError`.
3. **Repository Interfaces (`usfds-core/src/usfds_core/repositories/`)**:
   - Thêm `base_user_repo.py` (`IUserRepository`), `base_rbac_repo.py` (`IRoleRepository`, `IPermissionRepository`, `IProjectMemberRepository`), `base_session_repo.py` (`IUserSessionRepository`).
4. **Services (`usfds-core/src/usfds_core/services/auth/`)** *(mới)*:
   - `security.py`: interface/protocol `IPasswordHasher`, `ITokenProvider`.
   - `auth_service.py`: `login()`, `refresh()`, `logout()`, `change_password()`, `update_own_profile()`.
   - `user_service.py`: CRUD user, enable/disable (kèm revoke all sessions), reset password, gán system roles.
   - `rbac_service.py`: kiểm tra quyền 3 scopes (`SYSTEM`, `PROJECT`, `OWN`), quản lý `project_members` (bảo vệ không xóa `project_admin` cuối cùng).
5. **Cập nhật [`project_service.py`](file:///d:/Thesis/4. Implementation/usfds/usfds-core/src/usfds_core/services/project_management/project_service.py)**:
   - Khi `create_project(..., user_id=creator_id)`, tự động thêm `creator_id` vào `project_members` với role `project_admin`.
   - Hỗ trợ `list_projects_for_user(user_id, is_system_admin)` để cô lập danh sách dự án.

### Phase 2: Database ORM, Repositories & Seeding (`usfds-infra`)
1. **[`usfds-infra/src/usfds_infra/database/auth_models.py`](file:///d:/Thesis/4. Implementation/usfds/usfds-infra/src/usfds_infra/database/auth_models.py)** *(mới)* & `__init__.py`:
   - Cài đặt 7 ORM models tương thích cả SQLite và PostgreSQL.
2. **[`usfds-infra/src/usfds_infra/database/auth_repositories.py`](file:///d:/Thesis/4. Implementation/usfds/usfds-infra/src/usfds_infra/database/auth_repositories.py)** *(mới)*:
   - Cài đặt `SqlUserRepository`, `SqlRoleRepository`, `SqlPermissionRepository`, `SqlProjectMemberRepository`, `SqlUserSessionRepository`.
3. **`usfds-infra/src/usfds_infra/security/`** *(mới)* & **`seed_rbac.py`**:
   - Adapter hash mật khẩu (`Argon2id` hoặc `bcrypt`) và JWT (`PyJWT`).
   - Seed idempotent toàn bộ `permissions`, `roles` (`system_admin`, `system_member`, `project_admin`, `data_scientist`, `fraud_analyst`), `role_permissions`, bootstrap admin user, và backfill `project_members` cho các project chưa có member.

### Phase 3: Server Config, Auth Middleware, Endpoints & Hardening (`usfds-server` & `deploy/`)
1. **[`usfds-server/src/usfds_server/config.py`](file:///d:/Thesis/4. Implementation/usfds/usfds-server/src/usfds_server/config.py)**, [`deploy/.env.example`](file:///d:/Thesis/4. Implementation/usfds/deploy/.env.example), [`deploy/docker-compose.yml`](file:///d:/Thesis/4. Implementation/usfds/deploy/docker-compose.yml):
   - Thêm `USFDS_AUTH_MODE` (`local_auto` cho desktop mặc định khi không set `USFDS_DB_URL`; `required` trong `docker-compose.yml`), `USFDS_JWT_SECRET`, `USFDS_ACCESS_TOKEN_EXPIRE_MINUTES`, `USFDS_REFRESH_TOKEN_EXPIRE_DAYS`, `USFDS_BOOTSTRAP_ADMIN_USERNAME`, `USFDS_BOOTSTRAP_ADMIN_PASSWORD`, `USFDS_CORS_ORIGINS`.
   - Cập nhật `usfds-server/pyproject.toml` (thêm `pyjwt`, `pwdlib[argon2]` hoặc `bcrypt`).
2. **`usfds-server/src/usfds_server/auth_dependencies.py`** *(mới)* & [`dependencies.py`](file:///d:/Thesis/4. Implementation/usfds/usfds-server/src/usfds_server/dependencies.py):
   - `get_current_user`: giải mã Bearer JWT (mode `required`) hoặc trả về bootstrap local admin (mode `local_auto`).
   - `require_permission(permission_code, project_id_resolver=..., owner_resolver=...)`.
   - Khởi tạo seed RBAC + bootstrap admin trong `setup_infrastructure()`.
3. **New Routers (`usfds-server/src/usfds_server/routers/`)**:
   - `auth_router.py` (`/api/v1/auth`):
     - `GET /mode` (public: trả `auth_mode` để FE biết có cần trang Login không)
     - `POST /login`, `POST /refresh`, `POST /logout`
     - `GET /me`, `PATCH /me`, `POST /me/password`
   - `user_router.py` (`/api/v1/users` — yêu cầu quyền `SYSTEM`):
     - `GET /`, `POST /`, `GET /{user_id}`, `PATCH /{user_id}`, `PATCH /{user_id}/status`, `POST /{user_id}/reset-password`, `PUT /{user_id}/system-roles`
   - `rbac_router.py` (`/api/v1/rbac`):
     - `GET /roles`, `GET /permissions`, `POST /roles`, `PUT /roles/{role_id}/permissions`
   - Mở rộng [`project_router.py`](file:///d:/Thesis/4. Implementation/usfds/usfds-server/src/usfds_server/routers/project_router.py):
     - `GET /api/v1/projects/{project_id}/members`, `POST .../members`, `PATCH .../members/{user_id}`, `DELETE .../members/{user_id}`.
4. **Enforce Auth & RBAC trên toàn bộ Routers hiện có:**
   - Áp dụng `require_permission` cho [`project_router.py`](file:///d:/Thesis/4. Implementation/usfds/usfds-server/src/usfds_server/routers/project_router.py), `dataset_router.py`, `rule_router.py`, [`training_router.py`](file:///d:/Thesis/4. Implementation/usfds/usfds-server/src/usfds_server/routers/training_router.py), `detection_router.py`, [`investigation_router.py`](file:///d:/Thesis/4. Implementation/usfds/usfds-server/src/usfds_server/routers/investigation_router.py), [`insight_report_router.py`](file:///d:/Thesis/4. Implementation/usfds/usfds-server/src/usfds_server/routers/insight_report_router.py), [`storage_router.py`](file:///d:/Thesis/4. Implementation/usfds/usfds-server/src/usfds_server/routers/storage_router.py).
   - **Loại bỏ mọi định danh giả/từ client:** Xóa `get_actor() -> "local-analyst"`, `"mock_user"`, và không lấy `user_id`/`created_by` từ request body — luôn gán từ `current_user.user_id` / `current_user.username`.
   - **Siết `storage_router.py`:** `presigned-upload` kiểm tra quyền trên `project_id` (bắt buộc với upload nghiệp vụ); `presigned-download` kiểm tra `object_key` thuộc `project_id` mà user có quyền `read`/`export`.

### Phase 4: Frontend Auth, User Management & Project Access UI (`usfds-web`)
1. **Types & API Clients (`usfds-web/src/types/`, `usfds-web/src/api/`):**
   - `types/auth.ts`: `AuthUser`, `AuthModeResponse`, `LoginRequest`, `RoleDto`, `PermissionDto`, `ProjectMemberDto`, `AdminUserDto`.
   - `api/authApi.ts`, `api/userAdminApi.ts`, `api/projectMemberApi.ts`.
   - Cập nhật [`client.ts`](file:///d:/Thesis/4. Implementation/usfds/usfds-web/src/api/client.ts): tự động gắn `Authorization: Bearer <access_token>`, xử lý `401` bằng single-flight refresh token trước khi fallback về `/login`.
2. **Global `AuthProvider` (`usfds-web/src/hooks/useAuth.tsx`):**
   - Khi khởi động: gọi `GET /api/v1/auth/mode`. Nếu `local_auto` -> tự fetch `/auth/me`; nếu `required` -> khôi phục session hoặc chuyển `/login`.
   - Cung cấp `currentUser`, `hasPermission(code, projectId?)`, `isSystemAdmin`, `logout()`.
3. **UI Screens & Components (theo [`docs/design-system.md`](file:///d:/Thesis/4. Implementation/usfds/docs/design-system.md)):**
   - `LoginPage.tsx` (`/login`): giao diện đăng nhập username + password (ẩn trong `local_auto`).
   - `ProfileModal` / `ProfilePage.tsx`: xem thông tin tài khoản, role hiện tại, đổi mật khẩu (`OWN`).
   - `AdminUsersPage.tsx` (`/admin/users` cho `system_admin`): quản lý danh sách Users (Tạo user, Sửa thông tin, Bật/Khóa tài khoản, Reset mật khẩu, Gán System Role) + Tab xem/chỉnh sửa Role-Permission Matrix.
   - Mở rộng [`ProjectSettingsView.tsx`](file:///d:/Thesis/4. Implementation/usfds/usfds-web/src/components/modules/project_management/ProjectSettingsView.tsx): thêm tab **Members & Access** (xem thành viên, thêm thành viên vào dự án kèm chọn `Project Role`, đổi role, xóa thành viên).
   - Cập nhật [`Topbar.tsx`](file:///d:/Thesis/4. Implementation/usfds/usfds-web/src/components/layout/Topbar.tsx), [`useProjects.tsx`](file:///d:/Thesis/4. Implementation/usfds/usfds-web/src/hooks/useProjects.tsx), [`useDatasetImport.ts`](file:///d:/Thesis/4. Implementation/usfds/usfds-web/src/hooks/useDatasetImport.ts): xóa `DEFAULT_USER_ID` và mock profile `DS / Data Scientist`, hiển thị thông tin user thật + menu Profile / System Admin / Logout; lọc nút thao tác theo `hasPermission`.

### Phase 5: Testing & Verification
1. **`usfds-core/tests/test_rbac_service.py`**: kiểm thử phân giải quyền 3 scopes (`SYSTEM`, `PROJECT`, `OWN`), cô lập chéo project, ngăn xóa `project_admin` cuối cùng, vòng đời auth/session.
2. **`usfds-infra/tests/test_auth_repositories.py`**: kiểm thử ORM/repository (`users`, `roles`, `permissions`, `project_members`, `user_sessions`), tính idempotent của seed RBAC.
3. **`usfds-server/tests/test_auth_and_rbac_api.py`**:
   - Mode `required`: login, refresh token rotation, logout thu hồi token, `401` khi thiếu token, `403` khi sai role hoặc truy cập project không phải thành viên, `200` khi đủ quyền (`PROJECT` và `OWN`), kiểm tra `storage_router` chặn presigned URL chéo project.
   - Mode `local_auto`: auto-login admin cục bộ hoạt động bình thường, không làm gãy các test API hiện có.
4. **Chạy toàn bộ regression suite:** `pytest` ở `usfds-core`, `usfds-infra`, `usfds-server` và `npm run build` + `npm run lint` ở `usfds-web`.

---

## 4. Tiêu chí Nghiệm thu (Verifiable Success Criteria)
- [ ] `usfds-core` & `usfds-infra` hoàn thiện schema 7 bảng Auth/RBAC (`users`, `user_sessions`, `roles`, `permissions`, `role_permissions`, `system_user_roles`, `project_members`) không tạo bảng `organizations`.
- [ ] Ở `USFDS_AUTH_MODE=required`, mọi API nghiệp vụ đều yêu cầu Bearer JWT hợp lệ và kiểm tra quyền đúng theo 3 scopes (`SYSTEM`, `PROJECT`, `OWN`).
- [ ] Ở `USFDS_AUTH_MODE=local_auto` (Desktop SQLite), hệ thống tự động bootstrap tài khoản Admin cục bộ và vận hành mượt mà không cần màn hình Login.
- [ ] Không còn `DEFAULT_USER_ID`, `"local-analyst"`, `"mock_user"`, hay việc tin tưởng `user_id`/`created_by` từ client payload ở backend.
- [ ] `usfds-web` có đầy đủ Login, Profile/Change Password, Admin User/Role Management, và Project Members Management; build & lint pass sạch.
- [ ] Toàn bộ unit/API tests mới và hiện có đều pass.

