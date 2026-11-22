# Plan: Enforcing `GrantScope.OWN`, Unified `user_id`, Built-in Role Scopes & Schema Foreign Keys

> **Task ID:** `own_scope_access_control` (= this file name) · **Issues:** `ISS-043`, `ISS-023` · **Spec:** `.plan/user_management_rbac.md`, `.plan/rbac_feature_visibility.md`, `.plan/project_scoped_access_control.md`, `usfds-core/src/usfds_core/services/auth/access_logic.py`
> **Conflict verdict:** PARALLEL-SAFE · **Status:** Done <!-- Approved (26-11-22) -->

## 1. Context (facts)
- `can_access_record` (`usfds-core/src/usfds_core/services/auth/access_logic.py:127-134`) yêu cầu `resource.owner_id is not None and actor.user_id == resource.owner_id` khi `scope == GrantScope.OWN`, nhưng `AuthzService.require_project_permission` (`usfds-core/src/usfds_core/services/auth/authz_service.py:85-101`) mặc định `owner_id: Optional[UUID] = None`.
- Không router nào truyền `owner_id` vào `require_project_permission(...)`, và chỉ `GET /api/v1/projects` (`project_router.py:109-111`) dùng `authz.can_list(...)`:
  - `project_router.py:129, 152, 182, 207`
  - `dataset_router.py:191, 208, 236, 259, 294, 322, 362`
  - `training_router.py:363, 383, 408, 440, 489, 521, 592, 618, 647`
  - `rule_router.py:129, 151, 174, 222, 248, 272, 300, 351, 412`
  - `detection_router.py:74, 131, 169, 238`
  - `storage_router.py:154-188`
- **Thiếu cột `user_id` và thiếu FK constraints (`ISS-043` + `ISS-023`):**
  - 4 bảng `rules` (`tables/rule.py:21`), `detection_jobs` (`tables/detection.py:31`), `training_runs` (`tables/model.py:85`), `model_versions` (`tables/model.py:44`) chưa có cột `user_id: UUID` (mới chỉ có chuỗi username `created_by`/`registered_by`; `training_service.py:263-273` chưa gán `registered_by`).
  - 3 bảng `projects` (`tables/project.py:15`), `datasets` (`tables/dataset.py:16`), `models` (`tables/model.py:16`) đã có `user_id` nhưng chưa có `ForeignKey("users.user_id")`; built-in models trong `dependencies.py:38-57` phải dùng UUID giả `SYSTEM_USER_ID` vì `models.user_id` đang `NOT NULL`.
  - 6 bảng thuộc project (`datasets`, `rules`, `detection_jobs`, `models`, `model_versions`, `training_runs`) chưa có `ForeignKey("projects.project_id", ondelete="CASCADE")` (`ISS-023`; phần unique constraint trên `model_versions` đã xong ở `ISS-010`). SQLite đã bật `PRAGMA foreign_keys=ON` (`engine.py:17`).
- Trong `usfds-infra/src/usfds_infra/database/seed_rbac.py:96-167`, toàn bộ quyền `data_scientist` và `fraud_analyst` đang là `GrantScope.PROJECT`, `project_admin` thiếu quyền dọn dẹp/vận hành mức `PROJECT` (`dataset:delete`, `rule:deploy`, `rule:undeploy`, `rule:delete`), và vòng `seed_rbac` (`L212-L228`) chưa đồng bộ `grant_scope` nếu DB đã seed trước đó.
- Trên `usfds-web`, `canOpenActorFeature` (`feature-policy.ts:169-185`) và `useActorContext` (`useActorContext.ts:39-69`) chưa kiểm tra chủ sở hữu từng bản ghi cho `GrantScope.OWN`.

## 2. Goal, scope verdict & non-goals
- **Goal:**
  1. Thống nhất cột chủ sở hữu tên **`user_id`** với `ForeignKey("users.user_id", ondelete="RESTRICT")` (`NOT NULL` trên 6 bảng tài nguyên người dùng `projects`, `datasets`, `rules`, `training_runs`, `model_versions`, `detection_jobs`; `nullable=True` riêng trên `models` cho built-in models có `project_id = NULL, user_id = NULL`) và gắn **`ForeignKey("projects.project_id", ondelete="CASCADE")`** trên cả 6 bảng thuộc project (`datasets`, `rules`, `detection_jobs`, `models`, `model_versions`, `training_runs`) trong 1 Alembic revision (`ISS-043` + `ISS-023`).
  2. Loại bỏ UUID ảo `SYSTEM_USER_ID` khi seed built-in models (`user_id=None`).
  3. Chuẩn hóa `ROLE_GRANTS` trong `seed_rbac.py` (siết create/mutate/delete/deploy của `data_scientist` và `detection:create` của `fraud_analyst` xuống `OWN`; bổ sung `dataset:delete`, `rule:deploy/undeploy/delete` mức `PROJECT` cho `project_admin`; sync `grant_scope` idempotent).
  4. Thực thi `GrantScope.OWN` trên 6 backend routers (`project`, `dataset`, `training`, `rule`, `detection`, `storage`) + trả `user_id` trong tất cả response DTO.
  5. Gating ẩn nút mutate/delete/deploy/export theo `record.user_id` trên `usfds-web` khi user chỉ có `GrantScope.OWN`.
- **Scope:** OK
- **Non-goals / omitted:**
  - **Loại khỏi scope theo quyết định của user (26-11-22):** toàn bộ module **Investigation (`fraud_cases`, `entity_blacklist`, `investigation_router.py`, `case:*`, `blacklist:manage`)** và **Insight Report (`insight_report_router.py`, `report:*`)** — chờ user thiết kế lại riêng.
  - Không đổi chữ ký HTTP (URL, query/body bắt buộc) của các endpoint `mutate` hiện có.
  - Không thêm FK cho `run_datasets.dataset_artifact_id` hay `detection_jobs.{target_artifact_id,model_version_id}` để không phá ngữ nghĩa xóa dataset đã có run/job hoàn tất.
- **Assumptions:**
  - Mọi FK mới đều đặt tên tường minh (`fk_<table>_<col>_<ref>`) trong cả ORM lẫn migration để hỗ trợ SQLite `render_as_batch` khi `upgrade`/`downgrade` và PostgreSQL.
  - Built-in models (`Model.project_id is None`, `Model.user_id is None`) vẫn đọc được dưới `model:read:OWN` khi caller truyền `project_id` hợp lệ; custom models (`model.project_id == project_id`) và `ModelVersion` lọc chặt theo `user_id == actor.user_id`.
  - Quy trình 3 bước chống oracle cho `get by id` / `mutate` có `project_id`: (1) `authz.require_project_scope(actor, perm, project_id)` → `403` trước DB; (2) fetch theo `(project_id, id)` → `404`; (3) `authz.require_project_permission(actor, perm, project_id, owner_id=entity.user_id, action=...)` → `403` nếu lệch owner.
  - Ma trận `ROLE_GRANTS` cập nhật cho các module trong scope:
    - `data_scientist`: `PROJECT` cho `project:read`, `dataset:read`, `dataset:export`, `model:read`, `training:read`, `rule:read`, `rule:dry_run`, `detection:read`, `detection:export`, `report:read`; `OWN` cho `dataset:create`, `dataset:update`, `dataset:delete`, `model:create`, `model:update`, `training:create`, `deployment:deploy`, `deployment:undeploy`, `rule:create`, `rule:update`, `rule:delete`, `rule:deploy`, `rule:undeploy`, `detection:create`.
    - `fraud_analyst`: `detection:create` → `OWN` (giữ nguyên `case:*`, `blacklist:manage`, `report:*`).
    - `project_admin`: bổ sung mức `PROJECT` cho `dataset:delete`, `rule:deploy`, `rule:undeploy`, `rule:delete`.

## 3. Files
| Action | File | Milestone | Note |
|---|---|---|---|
| modify | `usfds-core/src/usfds_core/services/auth/authz_service.py` | M1 | thêm `require_project_scope(...)` và `resolve_project_list_owner(...)` |
| modify | `usfds-core/src/usfds_core/domain/entities/{model,rule,detection}.py` | M1 | `Model.user_id: Optional[UUID] = None`; thêm `user_id: UUID` trên `ModelVersion`, `TrainingRun`, `Rule`, `DetectionJob` |
| modify | `usfds-core/src/usfds_core/services/training/plugins/register.py` | M1 | `_resolve_user_id` trả `Optional[UUID]` (`None` khi `None`/`"system"`) |
| modify | `usfds-core/src/usfds_core/services/rule_engine/manager.py` | M1 | nhận và lưu `user_id: Optional[UUID] = None` trong `create_rule` |
| modify | `usfds-core/src/usfds_core/services/inference/inference_service.py` | M1 | nhận và lưu `user_id: Optional[UUID] = None` trong `start_detection_job` và `batch_inference` |
| modify | `usfds-core/src/usfds_core/services/training/training_service.py` | M1 | nhận và lưu `user_id: Optional[UUID] = None` trong `prepare_and_dispatch`; propagate `user_id=run.user_id` và `registered_by=run.created_by` trong `handle_training_completion` |
| modify | `usfds-infra/src/usfds_infra/database/tables/{project,dataset,model,rule,detection}.py` | M1 | 7 FK `user_id -> users.user_id (ON DELETE RESTRICT, index=True; NOT NULL trên 6 bảng, nullable trên models)` + 6 FK `project_id -> projects.project_id (ON DELETE CASCADE)` |
| modify | `usfds-infra/src/usfds_infra/database/repos/{model,rule,detection}.py` | M1 | map `user_id` hai chiều trên `Model`, `ModelVersion`, `TrainingRun`, `Rule`, `DetectionJob` |
| modify | `usfds-infra/src/usfds_infra/database/seed_rbac.py` | M1 | cập nhật `ROLE_GRANTS` và đồng bộ `grant_scope` idempotent cho built-in roles |
| migration | `usfds-infra/src/usfds_infra/database/migrations/versions/<rev>_add_user_id_and_foreign_keys.py` | M1 | 1 revision: thêm `user_id` + backfill + dọn orphan + chuyển `models.user_id` sang nullable + gắn 13 named FKs |
| modify | `usfds-core/tests/test_authz_enforcement.py` | M1 | unit tests `require_project_scope` & `resolve_project_list_owner` |
| modify | `usfds-infra/tests/{test_migrations,test_auth_repositories,test_dataset_repositories,test_model_repositories,test_model_version_uniqueness}.py` | M1 | acceptance tests migration backfill + FK enforcement (`ISS-023`) + `seed_rbac` sync, và cập nhật fixtures thỏa FK thật |
| modify | `usfds-server/src/usfds_server/dependencies.py` | M2 | `seed_builtin_models` lưu `user_id=None` thay vì `SYSTEM_USER_ID` giả |
| modify | `usfds-worker/src/usfds_worker/handlers.py` | M2 | bỏ fallback `"mock_user"` trong `handle_plugin_dry_run` (`L289`), truyền `data.get("user_id")` |
| modify | `usfds-server/src/usfds_server/schemas/{training,rule,detection}_api_schemas.py` | M2 | `ModelResponse.user_id: Optional[UUID] = None`; thêm `user_id: UUID` trên `ModelVersionResponse`, `TrainingRunResponse`, `RuleResponse`, `DetectionJobResponse` |
| modify | `usfds-server/src/usfds_server/routers/{project,dataset,training,rule,detection,storage}_router.py` | M2 | thực thi `GrantScope.OWN` (list/get/mutate/storage) với `entity.user_id`, ghi `user_id=actor.user_id` khi tạo mới, map `user_id` vào responses |
| modify | `usfds-server/tests/{test_auth_and_rbac_api,test_dataset_api,test_training_api,test_detection_api,test_insight_report_api,test_investigation_api}.py` & `usfds-worker/tests/test_handlers.py` | M2 | acceptance tests `ISS-043` và cập nhật các test chèn bản ghi trực tiếp thỏa FK `users`/`projects` |
| modify | `usfds-web/src/lib/feature-policy.ts` | M3 | thêm `canAccessRecordFeature(actor, feature, ownerId, projectId?)` |
| modify | `usfds-web/src/hooks/useActorContext.ts` | M3 | expose `canAccessRecord(feature, ownerId, targetProjectId?)` |
| modify | `usfds-web/src/types/{model,rule,detection}.ts` | M3 | thống nhất `user_id?: string | null` trên `ModelResponse`, `ModelVersionResponse`, `TrainingRunResponse`, `RuleResponse`, `DetectionJobResponse` |
| modify | `usfds-web/src/components/modules/project_management/{ProjectManagementView,ProjectSettingsView,ProjectSchemaDrawer}.tsx` | M3 | dùng `canAccessRecord(..., project.user_id, project.project_id)` |
| modify | `usfds-web/src/components/modules/data_management/{DatasetHubView,DataPipelineWorkspace,DatasetLineageExplorer}.tsx` | M3 | dùng `canAccessRecord(..., dataset.user_id)` |
| modify | `usfds-web/src/components/modules/model/{ModelHubView,TrainingRunDetailView}.tsx` | M3 | dùng `canAccessRecord('deployModel', version.user_id)` |
| modify | `usfds-web/src/components/modules/rule/{RuleCatalogView,RuleWorkspace}.tsx` | M3 | dùng `canAccessRecord(..., rule.user_id)` |
| modify | `usfds-web/src/components/modules/detection/DetectionResultExplorerView.tsx` | M3 | dùng `canAccessRecord('exportDetection', job?.user_id)` |
| modify | `usfds-web/src/lib/feature-policy.test.ts` | M3 | unit tests `canAccessRecordFeature` |
| modify | `usfds-web/src/test/featureVisibilityModules.test.tsx` | M3 | acceptance tests ẩn nút mutate cho bản ghi của user khác dưới `data_scientist` (`OWN`) và hiện dưới `project_admin` (`PROJECT`) |

## 4. Dependencies & conflicts (with other tasks on BOARD)
| # | Check | Answer |
|---|---|---|
| D1 | Needs unfinished task? | No (`user_management_rbac`, `rbac_feature_visibility`, `project_scoped_access_control`, `model_versioning_scheme` đều đã `Done`) |
| D2 | Needed by unfinished task? | No |
| C1 | Modified files owned by in-progress task? | No (không có task `In progress` trên BOARD) |
| C2 | Hot-spot files touched | `usfds-server/src/usfds_server/dependencies.py` (chỉ sửa `user_id=None` trong `seed_builtin_models`, không đụng vùng provider re-exports) |
| C3 | Schema change | Yes: 1 Alembic revision thống nhất cột `user_id` (`NOT NULL` trên 6 bảng, `nullable=True` trên `models`, indexed) + 13 named FK constraints (`7 x users.user_id ON DELETE RESTRICT`, `6 x projects.project_id ON DELETE CASCADE`) kèm backfill |
| C4 | Public contract change | No (chỉ thêm `user_id` vào 4 response DTO mới và nới `ModelResponse.user_id` thành optional cho built-in models) |
| C5 | Shared UI shell change | No |

## 5. Acceptance tests (user reviews this section)
| Milestone | Test | Given | When | Then | Covers |
|---|---|---|---|---|---|
| M1 | `test_authz_project_scope_and_list_owner_helpers` (`usfds-core/tests/test_authz_enforcement.py`) | User có `rule:read:OWN` ở Project A, `rule:read:PROJECT` ở Project B, không có quyền ở Project C | Gọi `require_project_scope` và `resolve_project_list_owner` cho A, B, C | A trả `GrantScope.OWN` / `actor.user_id`; B trả `GrantScope.PROJECT` / `None`; C raise `PermissionDeniedError` | `ISS-043` |
| M1 | `test_user_id_and_fk_migration_backfills_enforces_fks_and_renders_pg` (`usfds-infra/tests/test_migrations.py`) | DB ở revision `845d529c5502` có user `alice`, 1 project, các bản ghi legacy gắn username `alice` và 1 built-in model có `SYSTEM_USER_ID` ảo | Chạy `upgrade_database` lên `head`, kiểm tra render PostgreSQL offline SQL, thử chèn `Dataset`/`Rule`/`DetectionJob` với `project_id` hoặc `user_id` không tồn tại, và thử xóa `User` đang sở hữu bản ghi | Bản ghi của `alice` backfill đúng `user_id = alice.user_id` (`NOT NULL`); built-in model chuyển `user_id = None`; chèn FK ảo và xóa user đang sở hữu tài nguyên đều bị chặn bởi `IntegrityError` (`ON DELETE RESTRICT`); xóa project cascade xóa tài nguyên con (`CASCADE`); `schema_drift == []`; render PG SQL sạch | `ISS-043`, `ISS-023` |
| M1 | `test_seed_rbac_syncs_builtin_role_own_scopes_idempotently` (`usfds-infra/tests/test_auth_repositories.py`) | DB đã seed trước đó với `data_scientist` giữ `rule:update:PROJECT`, `dataset:delete:PROJECT` | Chạy `seed_rbac` lại 2 lần | `data_scientist` hạ các quyền create/mutate/delete/deploy về `OWN` (giữ `PROJECT` cho read/dry-run/export); `fraud_analyst` có `detection:create:OWN`; `project_admin` có thêm `dataset:delete`, `rule:deploy`, `rule:undeploy`, `rule:delete` mức `PROJECT` | `ISS-043` |
| M2 | `test_own_scope_list_and_get_by_id_across_core_routers` (`usfds-server/tests/test_auth_and_rbac_api.py`) | Project A có `u1` và `u2` giữ custom role `GrantScope.OWN` cho `project:read`, `dataset:*`, `model:*`, `training:*`, `rule:*`, `detection:*`; mỗi user sở hữu tài nguyên riêng và có built-in model (`user_id=None`) | `u1` gọi `list`, `get by id`, `lineage`, `results`, `export` và `storage/presigned-download` trên tài nguyên của `u1`, của `u2`, ID không tồn tại ở Project A và Project B | `list` chỉ trả tài nguyên của `u1` (kèm built-in model cho `GET /models`); `get by id` trả `200` (kèm `user_id`) cho tài nguyên `u1` & built-in model, `403` cho tài nguyên `u2`, `404` cho ID không tồn tại ở A, `403` trước DB cho Project B | `ISS-043` |
| M2 | `test_builtin_ds_own_mutate_isolation_and_project_admin_override` (`usfds-server/tests/test_auth_and_rbac_api.py`) | Project A có 2 `data_scientist` (`ds1`, `ds2`) và 1 `project_admin` (`padmin`) dùng built-in role mặc định; `ds1` tạo dataset, rule, training run & model version | `ds2` đọc và thử update/delete/deploy tài nguyên của `ds1`; `ds1` tự update/deploy/delete tài nguyên của mình; `padmin` deploy/delete rule & delete dataset của `ds1` | `ds2` đọc được (`200`) nhưng mutate/deploy/delete tài nguyên của `ds1` bị `403`; `ds1` thao tác trên tài nguyên của mình thành công (`200`/`201`); `padmin` override thành công (`200`) | `ISS-043` |
| M3 | `test_can_access_record_feature_respects_own_project_and_system_scopes` (`usfds-web/src/lib/feature-policy.test.ts`) | `ActorContext` với quyền `OWN`, `PROJECT`, `SYSTEM` và `is_system_admin` | Gọi `canAccessRecordFeature` với `ownerId === actor.user_id`, `ownerId !== actor.user_id`, và `ownerId === null` | `OWN` chỉ `true` khi `ownerId === actor.user_id`; `PROJECT`/`SYSTEM`/`is_system_admin` luôn `true` bất kể `ownerId` | `ISS-043` |
| M3 | `test_module_views_hide_mutate_actions_for_other_owners_under_own_scope` (`usfds-web/src/test/featureVisibilityModules.test.tsx`) | Render `DatasetHubView`, `RuleCatalogView`, `ModelHubView` dưới role `data_scientist` (`OWN` mutate) với 1 bản ghi của chính user và 1 bản ghi của user khác; và dưới `project_admin` (`PROJECT`) | Kiểm tra nút Xóa/Sửa/Kích hoạt trên từng dòng | Dưới `data_scientist`: hiện nút trên dòng của chính mình, ẩn hoàn toàn trên dòng của user khác; dưới `project_admin`: hiện nút trên cả 2 dòng | `ISS-043` |

## 6. Milestones & to-do (checkpoints, not stop points: all tests green at each)
The agent ticks items as it works. This is the task's only to-do list (`TODO.md` is no longer used for new work).

- [x] **M1 — Unified `user_id` (`NOT NULL` + `RESTRICT`), Schema FKs (`ISS-023`), Authz Helpers & Built-in Role Scopes** (`usfds-core`, `usfds-infra`): toàn bộ 7 bảng domain thống nhất `user_id` (`NOT NULL` trên 6 bảng, `nullable` trên `models`, FK `RESTRICT`) và 6 bảng có FK `project_id` (`CASCADE`), `seed_rbac` đồng bộ scope `OWN`/`PROJECT`, và `AuthzService` có helper dùng chung.
  - [x] [tests] Viết 3 M1 acceptance tests từ §5 (`test_authz_enforcement.py`, `test_migrations.py`, `test_auth_repositories.py`); xác nhận fail đúng lý do
  - [x] [core] Thêm `require_project_scope`, `resolve_project_list_owner` vào `authz_service.py`; thống nhất `user_id` trên entities (`model.py`, `rule.py`, `detection.py`) và cập nhật `ModelPluginRegistrationService`, `RuleManager`, `InferenceService`, `TrainingOrchestrationService`
  - [x] [infra] Cập nhật 5 file `tables/*.py` (13 named FKs + `user_id`), 3 file `repos/*.py`, `seed_rbac.py`, tạo 1 Alembic revision kèm backfill/orphan cleanup, cập nhật fixtures infra tests thỏa FK, chạy `migrate check` / `migrate heads`
  - [x] [verify] `./scripts/test.sh core infra`
- [x] **M2 — `GrantScope.OWN` Enforcement, Built-in Model Fix & Unified `user_id` DTOs** (`usfds-server`, `usfds-worker`): 6 backend routers thực thi `GrantScope.OWN`, trả `user_id`, và built-in models dùng `user_id=None`.
  - [x] [tests] Viết 2 M2 acceptance tests trong `usfds-server/tests/test_auth_and_rbac_api.py`; xác nhận fail trước khi sửa
  - [x] [server] Cập nhật `dependencies.py`, `schemas/{training,rule,detection}_api_schemas.py`, `routers/{project,dataset,training,rule,detection,storage}_router.py`
  - [x] [worker] Bỏ fallback `"mock_user"` trong `usfds-worker/src/usfds_worker/handlers.py`
  - [x] [tests] Cập nhật các test server/worker chèn trực tiếp DB để thỏa FK `users`/`projects`
  - [x] [verify] `./scripts/test.sh core infra server worker cli`
- [x] **M3 — Per-Record `OWN` Action Gating on `usfds-web` & Full Regression** (`usfds-web`, `all`): frontend kiểm tra `record.user_id` cho nút mutate/delete/deploy/export và toàn bộ suite + build/lint xanh.
  - [x] [tests] Viết 2 M3 tests trong `feature-policy.test.ts` và `featureVisibilityModules.test.tsx`; xác nhận fail trước khi sửa
  - [x] [web] Thêm `canAccessRecordFeature` (`feature-policy.ts`), `canAccessRecord` (`useActorContext.ts`), thống nhất `user_id?: string | null` trong `types/{model,rule,detection}.ts`, và áp dụng gating theo bản ghi trên các view `project_management`, `data_management`, `model`, `rule`, `detection`
  - [x] [verify] `./scripts/test.sh` + `cd usfds-web && npm run build && npm run lint`

Checkpoint log (the agent appends one line per finished milestone):
- [26-11-22] M1 complete: `user_id` + 13 named FKs (`f232fc1f5c13`), `seed_rbac` OWN/PROJECT sync, and `AuthzService` helpers verified (`./scripts/test.sh core infra` — 162 core + 42 infra passed, 0 drift).
- [26-11-22] M2 complete: `GrantScope.OWN` enforced across 6 routers (`project`, `dataset`, `training`, `rule`, `detection`, `storage`), built-in models seeded with `user_id=None`, `user_id` exposed in response DTOs (`./scripts/test.sh core infra server worker cli` — 162 core, 42 infra, 41 server, 3 worker, 5 cli passed).
- [26-11-22] M3 complete: `canAccessRecordFeature` + `canAccessRecord` added on `usfds-web`, per-record UI gating applied across 11 module views, full test suite + `npm run build` + `npm run lint` passed.

## 7. Review hotspots (filled in after implementation)
- `usfds-infra/src/usfds_infra/database/migrations/versions/f232fc1f5c13_add_user_id_and_foreign_keys.py:24-198` — thêm cột `user_id` trên 4 bảng (`rules`, `detection_jobs`, `training_runs`, `model_versions`), backfill chủ sở hữu từ `created_by`/`registered_by`/`projects.user_id`, chuyển `models.user_id` sang `nullable=True` (`NULL` cho built-in models), và gắn 13 named foreign keys (`7 x users.user_id ON DELETE RESTRICT`, `6 x projects.project_id ON DELETE CASCADE`).
- `usfds-infra/src/usfds_infra/database/migrate.py:58-74` — tắt tạm `PRAGMA foreign_keys=OFF` ngoài transaction trước khi chạy Alembic `batch_alter_table` trên SQLite để `DROP TABLE` nội bộ của batch mode không kích hoạt `ON DELETE CASCADE` / `SET NULL` làm mất dữ liệu bảng con, và bật lại `PRAGMA foreign_keys=ON` ngay sau khi migration hoàn tất.
- `usfds-infra/src/usfds_infra/database/seed_rbac.py:96-175, 212-232` — cập nhật `ROLE_GRANTS` (`data_scientist` create/mutate/delete/deploy và `fraud_analyst` `detection:create` chuyển sang `GrantScope.OWN`; `project_admin` thêm `dataset:delete`, `rule:deploy`, `rule:undeploy`, `rule:delete` ở mức `GrantScope.PROJECT`) và đồng bộ `grant_scope` idempotent khi khởi động.
- `usfds-core/src/usfds_core/services/auth/authz_service.py:103-140` — hai helper `require_project_scope` (chặn `403` trước khi chạm DB, chống 404 oracle) và `resolve_project_list_owner` (trả `actor.user_id` khi scope là `OWN`, `None` khi `PROJECT`/`SYSTEM`).
- `usfds-server/src/usfds_server/routers/{project,dataset,training,rule,detection,storage}_router.py` — thực thi `GrantScope.OWN` trên toàn bộ endpoint `list`, `get by id` (quy trình 3 bước `403` pre-DB → `404` → `403` lệch owner), `mutate`/`delete`/`deploy`/`export`, và `storage/presigned-download`.
- `usfds-web/src/lib/feature-policy.ts:187-212` & `usfds-web/src/hooks/useActorContext.ts:62-75` — `canAccessRecordFeature` và `canAccessRecord` kiểm tra `ownerId === actor.user_id` khi quyền chỉ có `GrantScope.OWN`.

## 8. Open questions
- — (đã chốt toàn bộ với user ngày 26-11-22: gộp `ISS-023` vào cùng task; thống nhất tên cột `user_id` `NOT NULL` + FK `users.user_id ON DELETE RESTRICT` cho 6 bảng tài nguyên người dùng và `nullable=True` + `ON DELETE RESTRICT` riêng cho `models` built-in; FK `projects.project_id ON DELETE CASCADE` cho 6 bảng thuộc project; áp dụng bảng `OWN` mặc định cho `data_scientist`/`fraud_analyst` và bổ sung quyền quản trị mức `PROJECT` cho `project_admin`; trả `user_id` & ẩn nút trên `usfds-web`; loại Investigation & Insight Report khỏi scope.)
