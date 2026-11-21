# Plan: Đơn giản hoá Model Versioning thành `v1, v2, v3...`

> **Task ID:** `model_versioning_scheme` · **Issues:** ISS-010 · **Spec:** `docs/features/detection/training/suc-spec.md#L107` (BR-DT-03 — cập nhật từ `1.0.0 -> 1.0.1` sang `v1 -> v2` và phạm vi `(project_id, model_id)`)
> **Conflict verdict:** PARALLEL-SAFE · **Status:** Done (26-11-21)

## 1. Context (facts)
- `TrainingOrchestrationService._resolve_next_semver` (`usfds-core/src/usfds_core/services/training/training_service.py:259-275`) tự động tăng phần patch (`1.0.0` → `1.0.1`), rơi về `f"{latest.semver}.1"` nếu `len(parts) != 3`, và trả về `"1.0.0"` khi có lỗi.
- `SqliteModelVersionRepository.get_latest_version` (`usfds-infra/src/usfds_infra/database/repos/model.py:214-222`) và `InMemoryModelVersionRepository.get_latest_version` (`usfds-core/src/usfds_core/repositories/in_memory_repos.py:109-113`) chọn phiên bản mới nhất theo `registered_at` thay vì thứ tự số phiên bản.
- `ModelVersionModel` (`usfds-infra/src/usfds_infra/database/tables/model.py:28-49`) và migration `0001_baseline_baseline_schema.py:242-265` chưa có `UniqueConstraint` trên `model_versions`. M1 đã thêm `UniqueConstraint("model_id", "semver", name="uq_model_versions_model_semver")`.
- **Phát hiện bổ sung (26-11-21):** Các mô hình `BUILTIN` (`BUILTIN_RANDOM_FOREST_ID`, `BUILTIN_XGBOOST_ID` ở `usfds-server/src/usfds_server/dependencies.py:30-79`) dùng chung toàn hệ thống (`project_id = None`, `BR-PM-06`), nhưng mỗi `TrainingRun` và `ModelVersion` gắn với `project_id` riêng (`training_service.py:168-170,247`). Constraint `(model_id, semver)` chặn Project B tạo `v1` cho mô hình `BUILTIN` nếu Project A đã có `v1`; `_resolve_next_semver` (`training_service.py:278-290`), `GET /api/v1/training/models/{model_id}/versions` (`training_router.py:398-418`), và `ModelHubView.tsx:87` cũng chưa lọc theo `project_id`. Ngoài ra, `model_versions.project_id` là `nullable=True`, nên `UniqueConstraint("project_id", "model_id", "semver")` cần đi kèm partial unique index `(model_id, semver) WHERE project_id IS NULL` để chống trùng khi `project_id` là `NULL`.
- `training_service.py:611` (`label=f"v{version.semver}"`) và các màn hình `usfds-web` (`DetectionJobWizardView.tsx:717,1013`, `DetectionJobsHubView.tsx:349`, `DetectionResultExplorerView.tsx:193`, `ActivateModelModal.tsx:129`, `ModelHubView.tsx:528,683`, `ModelLineageModal.tsx:27`, `ModelLineagePanel.tsx:181`, `TrainingRunDetailView.tsx:209`) đang tự gắn thêm tiền tố `v` trước `version.semver` — nếu `semver` là `"v1"` sẽ hiển thị thành `"vv1"` nếu không xử lý.

## 2. Goal, scope verdict & non-goals
- **Goal:** Đơn giản hoá định danh phiên bản mô hình thành chuỗi tuần tự `v1`, `v2`, `v3`..., sắp xếp theo số phiên bản (`v10` > `v2`), đảm bảo duy nhất theo từng `(project_id, model_id, semver)` (cùng partial unique index khi `project_id IS NULL`), tự tăng phiên bản và liệt kê `ModelVersion` độc lập theo từng project (đặc biệt cho `BUILTIN` models), hiển thị đúng `v1` trên API & `usfds-web`.
- **Scope:** OK.
- **Non-goals / omitted:**
  - Không đổi tên cột `semver` trong DB/API schema (giữ nguyên hợp đồng `ModelVersionResponse.semver` để tránh breaking change).
  - Không ép `model_versions.project_id` thành `NOT NULL` (giữ `nullable=True` để không vỡ dữ liệu/test cũ, chống trùng NULL bằng partial unique index).
  - Không tự động migrate dữ liệu `1.0.0` cũ trong DB (các phiên bản mới bắt đầu từ `v1`, hoặc `v{max_n + 1}` nếu đã có `vN`; dữ liệu cũ `1.0.0` vẫn hiển thị bình thường là `v1.0.0`).
  - Không thêm các FK/constraint khác của `ISS-023` (`datasets.project_id`, `rules.project_id`, `detection_jobs.project_id`).
- **Assumptions:**
  - Giá trị `semver` mới có dạng `v1`, `v2`, `v3`,... (chữ `v` thường + số nguyên dương).

## 3. Files
| Action | File | Milestone | Note |
|---|---|---|---|
| modify | `usfds-core/src/usfds_core/services/training/training_service.py` | M1, M3 | Sinh `v1, v2, v3...`, retry khi trùng, sửa lineage `label`; M3: scope `_resolve_next_semver` và `list_model_versions` theo `project_id` |
| modify | `usfds-core/src/usfds_core/repositories/base_model_version_repo.py` | M3 | Thêm tham số tùy chọn `project_id` / `scope_to_project` cho `get_latest_version`, `list_by_model` |
| modify | `usfds-core/src/usfds_core/repositories/in_memory_repos.py` | M1, M3 | M3: ràng buộc duy nhất `(project_id, model_id, semver)` & lọc `project_id` ở `get_latest_version`/`list_by_model` |
| modify | `usfds-infra/src/usfds_infra/database/tables/model.py` | M1, M3 | M3: đổi sang `UniqueConstraint("project_id", "model_id", "semver", name="uq_model_versions_project_model_semver")` + partial unique index `uq_model_versions_null_project_model_semver` |
| modify | `usfds-infra/src/usfds_infra/database/repos/model.py` | M1, M3 | M3: bắt `IntegrityError` cho 2 constraint mới & lọc `project_id` ở `list_by_model`/`get_latest_version` |
| migration | `usfds-infra/src/usfds_infra/database/migrations/versions/14f998f68015_add_model_version_unique_semver.py` | M1 | Đã merge (giữ nguyên cùng bản sửa `down_revision='adb5e69392ae'`) |
| migration | `usfds-infra/src/usfds_infra/database/migrations/versions/<rev>_scope_model_version_unique_by_project.py` | M3 | Migration mới nối sau `14f998f68015`: drop `uq_model_versions_model_semver`, tạo constraint theo `(project_id, model_id, semver)` + partial index `WHERE project_id IS NULL` |
| modify | `usfds-server/src/usfds_server/routers/training_router.py` | M3 | `GET /models/{model_id}/versions` nhận query `project_id`, kiểm tra quyền `model:read` và lọc theo project |
| modify | `usfds-core/tests/training/test_training_service.py` | M1, M3 | M3: test `BUILTIN` model đánh số `v1` độc lập giữa 2 project & `list_model_versions(model_id, project_id)` |
| modify | `usfds-infra/tests/test_model_version_uniqueness.py` | M1, M3 | M3: test 2 project khác nhau đều lưu được `v1`, trùng cùng `(project_id, model_id, v1)` raise `IntegrityError`, trùng `(NULL, model_id, v1)` raise `IntegrityError` |
| modify | `usfds-server/tests/test_training_api.py` | M1, M3 | M3: test `GET /models/{model_id}/versions?project_id=...` cô lập version giữa 2 project trên cùng `BUILTIN` model |
| modify | `usfds-web/src/utils/formatters.ts` | M2 | Thêm helper `formatModelVersion(semver)` |
| modify | `usfds-web/src/api/trainingApi.ts` | M3 | `listModelVersions(modelId, projectId?)` truyền query `project_id` |
| modify | `usfds-web/src/components/modules/model/{ActivateModelModal,ModelHubView,ModelLineageModal,ModelLineagePanel,TrainingRunDetailView}.tsx` | M2, M3 | M3: `ModelHubView` truyền `projectId` khi gọi `listModelVersions` |
| modify | `usfds-web/src/components/modules/detection/{DetectionJobWizardView,DetectionJobsHubView,DetectionResultExplorerView}.tsx` | M2, M3 | M3: `DetectionJobWizardView` truyền `projectId` khi gọi `listModelVersions` |
| create | `usfds-web/src/utils/formatters.test.ts` | M2 | Test `formatModelVersion` |
| modify | `usfds-web/src/components/modules/model/ModelHubView.test.tsx` | M3 | Test `listModelVersions` gửi query `project_id` khi có active project |
| modify | `docs/features/detection/training/suc-spec.md` | M3 | Cập nhật `BR-DT-03` ghi rõ phạm vi `(project_id, model_id)` (`[26-11-21]`) |

## 4. Dependencies & conflicts (with other tasks on BOARD)
| # | Check | Answer |
|---|---|---|
| D1 | Needs unfinished task? | No |
| D2 | Needed by unfinished task? | No |
| C1 | Modified files owned by in-progress task? | No (mọi task trên `.plan/BOARD.md` đều đã `Done`) |
| C2 | Hot-spot files touched | — |
| C3 | Schema change | Yes: đổi `UniqueConstraint` trên `model_versions` sang `(project_id, model_id, semver)` + partial unique index `WHERE project_id IS NULL` (Alembic revision mới nối sau `14f998f68015`) |
| C4 | Public contract change | Backward-compatible: `GET /api/v1/training/models/{model_id}/versions` thêm query param tùy chọn `project_id`; `IModelVersionRepository` thêm keyword args tùy chọn `project_id`, `scope_to_project` |
| C5 | Shared UI shell change | No |

## 5. Acceptance tests (user reviews this section)
| Milestone | Test | Given | When | Then | Covers |
|---|---|---|---|---|---|
| M1 | `test_end_to_end_training_lifecycle_and_semver` (`usfds-core/tests/training/test_training_service.py`) | Model chưa có phiên bản nào | Chạy training run 1 rồi run 2 | Run 1 tạo `"v1"`, run 2 tạo `"v2"` | ISS-010 |
| M1 | `test_resolve_next_version_orders_numerically_not_lexically_or_by_timestamp` (`usfds-core/tests/training/test_training_service.py`) | Model có `"v10"` (cũ hơn) và `"v2"` (mới hơn theo `registered_at`) | Run mới hoàn tất | Phiên bản tiếp theo là `"v11"` (không phải `"v3"`) | ISS-010 |
| M1 | `test_lineage_label_no_double_v_prefix` (`usfds-core/tests/training/test_training_service.py`) | `ModelVersion` có `semver="v1"` | Gọi `get_model_lineage` | `node.label == "v1"` (không phải `"vv1"`) | ISS-010 |
| M1 | `test_model_version_unique_constraint_prevents_duplicates` (`usfds-infra/tests/test_model_version_uniqueness.py`) | Đã có `(project_id, model_id, "v1")` trong DB | Lưu thêm `ModelVersion` cùng `(project_id, model_id, "v1")` | DB ném `IntegrityError` | ISS-010 |
| M1 | `test_concurrent_completion_retries_and_allocates_distinct_versions` (`usfds-infra/tests/test_model_version_uniqueness.py`) | 2 training run của cùng `(project_id, model_id)` hoàn tất đồng thời | Cả 2 gọi `handle_training_completion` | Cả 2 thành công với phiên bản tách biệt `"v1"` và `"v2"` | ISS-010 |
| M2 | `test_formatModelVersion` (`usfds-web/src/utils/formatters.test.ts`) | Chuỗi `"v1"` hoặc chuỗi legacy `"1.0.0"` | Gọi `formatModelVersion` | `"v1"` → `"v1"`, `"1.0.0"` → `"v1.0.0"` | ISS-010 |
| M3 | `test_builtin_model_versions_increment_independently_per_project` (`usfds-core/tests/training/test_training_service.py`) | 1 `BUILTIN` model (`project_id=None`), Project A đã train xong `"v1"` | Project B train xong cùng `BUILTIN` model | Project B nhận `"v1"` (không phải `"v2"`); `list_model_versions(model_id, project_id=B)` chỉ trả về version của Project B | ISS-010, BR-DT-03, BR-PM-06 |
| M3 | `test_same_model_semver_allowed_across_projects_but_unique_within_project_and_null` (`usfds-infra/tests/test_model_version_uniqueness.py`) | Đã có `(project_A, model_id, "v1")` và `(None, model_id, "v1")` trong SQLite | Lưu `(project_B, model_id, "v1")` và sau đó thử lưu trùng `(project_A, model_id, "v1")` và `(None, model_id, "v1")` | `(project_B, model_id, "v1")` lưu thành công; 2 ca trùng cùng project và cùng `NULL` ném `IntegrityError` | ISS-010 |
| M3 | `test_list_model_versions_filters_by_project_id` (`usfds-server/tests/test_training_api.py`) | `BUILTIN` model có `v1` thuộc Project A và `v1` thuộc Project B | Gọi `GET /api/v1/training/models/{model_id}/versions?project_id={project_A}` và `?project_id={project_B}` | Mỗi project chỉ nhận đúng danh sách version của mình, mỗi bên đều là `"v1"` | ISS-010, BR-PM-06 |
| M3 | `test_model_hub_passes_project_id_to_list_model_versions` (`usfds-web/src/components/modules/model/ModelHubView.test.tsx`) | Active project đang chọn `proj-1` | `ModelHubView` tải danh sách model & versions | Request `GET /v1/training/models/{model_id}/versions` có query `project_id=proj-1` | ISS-010, BR-PM-06 |

## 6. Milestones & to-do (checkpoints, not stop points: all tests green at each)
The agent ticks items as it works. This is the task's only to-do list (`TODO.md` is no longer used for new work).

- [x] **M1 — `v1, v2, v3...` versioning, ordering & DB uniqueness** (`usfds-core`, `usfds-infra`, `usfds-server`):
  - [x] [tests] Viết & cập nhật các test M1 trong §5; xác nhận fail đúng lý do
  - [x] [core] Cập nhật `TrainingOrchestrationService._resolve_next_semver`, `handle_training_completion` (retry khi trùng) và `get_model_lineage` (tránh `vv1`)
  - [x] [core] Cập nhật `InMemoryModelVersionRepository` kiểm tra duy nhất `(model_id, semver)` và sắp xếp theo số phiên bản
  - [x] [infra] Thêm `UniqueConstraint("model_id", "semver")` vào `ModelVersionModel` và tạo Alembic migration
  - [x] [infra] Cập nhật `SqliteModelVersionRepository.get_latest_version` sắp xếp theo số phiên bản
  - [x] [verify] `./scripts/test.sh core infra server`
- [x] **M2 — Hiển thị `v1` không bị `vv1` trên UI** (`usfds-web`):
  - [x] [tests] Viết `usfds-web/src/utils/formatters.test.ts`
  - [x] [web] Thêm `formatModelVersion` vào `usfds-web/src/utils/formatters.ts` và thay thế các chỗ `v{...semver}`
  - [x] [verify] `./scripts/test.sh web`
- [x] **M3 — Scope uniqueness, đánh số & hiển thị `ModelVersion` theo `project_id`** (`usfds-core`, `usfds-infra`, `usfds-server`, `usfds-web`, `docs`):
  - [x] [tests] Viết các test M3 trong §5 ở `usfds-core`, `usfds-infra`, `usfds-server`, `usfds-web`; xác nhận fail trước khi sửa code
  - [x] [core] Cập nhật `IModelVersionRepository`, `InMemoryModelVersionRepository` (unique theo `(project_id, model_id, semver)` kể cả khi `project_id=None`), và `TrainingOrchestrationService` (`_resolve_next_semver`, `list_model_versions`)
  - [x] [infra] Cập nhật `ModelVersionModel` (`UniqueConstraint` + partial unique index `WHERE project_id IS NULL`), `SqliteModelVersionRepository`, và tạo Alembic migration mới nối sau `14f998f68015`
  - [x] [server] Cập nhật `GET /api/v1/training/models/{model_id}/versions` hỗ trợ `project_id` filter + RBAC check
  - [x] [web] Cập nhật `trainingApi.listModelVersions`, `ModelHubView.tsx`, `DetectionJobWizardView.tsx` truyền `projectId`
  - [x] [docs] Cập nhật `BR-DT-03` trong `docs/features/detection/training/suc-spec.md` với `[26-11-21]`
  - [x] [verify] `./scripts/test.sh core infra server web`

Checkpoint log (the agent appends one line per finished milestone):
- 26-11-20 M1 done: core 154 passed, 15 skipped; infra 39 passed; server 33 passed; notes: —
- 26-11-20 M2 done: web 18 test files / 30 passed, build & lint 0 errors; notes: —
- 26-11-21 M3 done: core 159 passed, 15 skipped; infra 40 passed; server 36 passed; web 19 test files / 34 passed, build & lint 0 errors; notes: —

## 7. Review hotspots (filled in after implementation)
1. `usfds-core/src/usfds_core/services/training/training_service.py:239-269` (M1): Retry loop (tối đa 5 lần) khi `DuplicateModelVersionError` xảy ra do 2 run hoàn tất đồng thời đọc cùng `latest`. Nếu retry hết 5 lần vẫn trùng sẽ raise lỗi để không ghi đè hoặc treo vô hạn. Được cover bởi `test_concurrent_completion_retries_and_allocates_distinct_versions`.
2. `usfds-infra/src/usfds_infra/database/repos/model.py:179-219` (M1): Dùng `session.begin_nested()` (SAVEPOINT) quanh `flush()` để `IntegrityError` trên `uq_model_versions_model_semver` chỉ rollback savepoint và chuyển thành `DuplicateModelVersionError` mà không làm hỏng transaction ngoài. Được cover bởi `test_concurrent_completion_retries_and_allocates_distinct_versions`.
3. `usfds-infra/src/usfds_infra/database/migrations/versions/14f998f68015_add_model_version_unique_semver.py:21-27` (M1): Alembic migration thêm `UniqueConstraint('model_id', 'semver')` (`down_revision='adb5e69392ae'`). Lưu ý: nếu DB production/staging đang có sẵn bản ghi `(model_id, semver)` bị trùng từ trước khi có constraint, `alembic upgrade` sẽ fail cho tới khi dọn bản ghi trùng. Được cover bởi `test_migrations.py` và `test_model_version_unique_constraint_prevents_duplicates`.
4. `usfds-core/src/usfds_core/repositories/base_model_version_repo.py:14-29` (M1): `parse_version_sort_key` xếp `vN` (`(1, N)`) cao hơn legacy `X.Y.Z` (`(0, X, Y, Z)`), nên model đã có `1.0.0` sẽ bắt đầu chuỗi mới từ `v1` rồi `v2`, `v3`... Được cover bởi `test_resolve_next_version_orders_numerically_not_lexically_or_by_timestamp`.
5. `usfds-infra/src/usfds_infra/database/migrations/versions/845d529c5502_scope_model_version_unique_by_project.py:21-51` (M3): Migration đổi `uq_model_versions_model_semver` sang `uq_model_versions_project_model_semver` (`['project_id', 'model_id', 'semver']`) + partial unique index `uq_model_versions_null_project_model_semver` (`['model_id', 'semver'] WHERE project_id IS NULL`), đồng thời kiểm tra `sa.inspect` khi online để idempotent với DB legacy tạo bằng `create_all`. Được cover bởi `test_migrations.py` và `test_same_model_semver_allowed_across_projects_but_unique_within_project_and_null`.
6. `usfds-core/src/usfds_core/services/training/training_service.py:278-296` & `usfds-infra/src/usfds_infra/database/repos/model.py:235-269` (M3): `scope_to_project=True` phân biệt rõ `project_id=None` (chỉ khớp `project_id IS NULL` khi cấp số `semver` cho run không gắn project) với việc bỏ qua filter `project_id` khi liệt kê toàn hệ thống. Được cover bởi `test_builtin_model_versions_increment_independently_per_project`.
7. `usfds-server/src/usfds_server/routers/training_router.py:397-427` (M3): `GET /models/{model_id}/versions` kiểm tra `authz.require_project_permission(actor, "model:read", project_id)` khi có query `project_id`, và lọc `effective_scope` cho non-admin khi không truyền `project_id`. Được cover bởi `test_list_model_versions_filters_by_project_id`.

## 8. Open questions
- —
