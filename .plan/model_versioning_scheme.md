# Plan: Đơn giản hoá Model Versioning thành `v1, v2, v3...`

> **Task ID:** `model_versioning_scheme` · **Issues:** ISS-010 · **Spec:** `docs/features/detection/training/suc-spec.md#L107` (BR-DT-03 — cập nhật từ `1.0.0 -> 1.0.1` sang `v1 -> v2` theo quyết định người dùng)
> **Conflict verdict:** PARALLEL-SAFE · **Status:** Done (26-11-20)

## 1. Context (facts)
- `TrainingOrchestrationService._resolve_next_semver` (`usfds-core/src/usfds_core/services/training/training_service.py:259-275`) tự động tăng phần patch (`1.0.0` → `1.0.1`), rơi về `f"{latest.semver}.1"` nếu `len(parts) != 3`, và trả về `"1.0.0"` khi có lỗi.
- `SqliteModelVersionRepository.get_latest_version` (`usfds-infra/src/usfds_infra/database/repos/model.py:214-222`) và `InMemoryModelVersionRepository.get_latest_version` (`usfds-core/src/usfds_core/repositories/in_memory_repos.py:109-113`) chọn phiên bản mới nhất theo `registered_at` thay vì thứ tự số phiên bản.
- `ModelVersionModel` (`usfds-infra/src/usfds_infra/database/tables/model.py:28-49`) và migration `0001_baseline_baseline_schema.py:242-265` chưa có `UniqueConstraint("model_id", "semver")` trên bảng `model_versions`, khiến các lần chạy song song có thể tạo `semver` trùng nhau.
- `training_service.py:611` (`label=f"v{version.semver}"`) và các màn hình `usfds-web` (`DetectionJobWizardView.tsx:717,1013`, `DetectionJobsHubView.tsx:349`, `DetectionResultExplorerView.tsx:193`, `ActivateModelModal.tsx:129`, `ModelHubView.tsx:528,683`, `ModelLineageModal.tsx:27`, `ModelLineagePanel.tsx:181`, `TrainingRunDetailView.tsx:209`) đang tự gắn thêm tiền tố `v` trước `version.semver` — nếu `semver` là `"v1"` sẽ hiển thị thành `"vv1"` nếu không xử lý.

## 2. Goal, scope verdict & non-goals
- **Goal:** Đơn giản hoá định danh phiên bản mô hình thành chuỗi tuần tự `v1`, `v2`, `v3`..., sắp xếp theo số phiên bản (`v10` > `v2`), đảm bảo duy nhất `(model_id, semver)` ở tầng DB và an toàn khi nhiều training run hoàn tất đồng thời, đồng thời hiển thị đúng `v1` (không thành `vv1`) trên API lineage và `usfds-web`.
- **Scope:** OK.
- **Non-goals / omitted:**
  - Không đổi tên cột `semver` trong DB/API schema (giữ nguyên hợp đồng `ModelVersionResponse.semver` để tránh breaking change).
  - Không tự động migrate dữ liệu `1.0.0` cũ trong DB (các phiên bản mới bắt đầu từ `v1`, hoặc `v{max_n + 1}` nếu đã có `vN`; dữ liệu cũ `1.0.0` vẫn hiển thị bình thường là `v1.0.0`).
  - Không thêm các FK/constraint khác của `ISS-023` (`datasets.project_id`, `rules.project_id`, `detection_jobs.project_id`).
- **Assumptions:**
  - Giá trị `semver` mới có dạng `v1`, `v2`, `v3`,... (chữ `v` thường + số nguyên dương).

## 3. Files
| Action | File | Milestone | Note |
|---|---|---|---|
| modify | `usfds-core/src/usfds_core/services/training/training_service.py` | M1 | Sinh `v1, v2, v3...`, retry khi trùng `(model_id, semver)`, sửa lineage `label` tránh `vv1` |
| modify | `usfds-core/src/usfds_core/repositories/in_memory_repos.py` | M1 | Ràng buộc duy nhất `(model_id, semver)` & sắp xếp `get_latest_version` theo số phiên bản |
| modify | `usfds-infra/src/usfds_infra/database/tables/model.py` | M1 | Thêm `UniqueConstraint("model_id", "semver", name="uq_model_versions_model_semver")` |
| modify | `usfds-infra/src/usfds_infra/database/repos/model.py` | M1 | `get_latest_version` sắp xếp theo số phiên bản (`vN` > legacy `X.Y.Z`) |
| migration | `usfds-infra/src/usfds_infra/database/migrations/versions/<rev>_add_model_version_unique_semver.py` | M1 | Alembic revision thêm `uq_model_versions_model_semver` |
| modify | `usfds-core/tests/training/test_training_service.py` | M1 | Test `v1 -> v2`, thứ tự `v10 > v2`, và lineage label không bị `vv1` |
| create | `usfds-infra/tests/test_model_version_uniqueness.py` | M1 | Test DB unique constraint & retry khi chạy đồng thời |
| modify | `usfds-server/tests/test_training_api.py` | M1 | Cập nhật assertion `"1.0.0"` → `"v1"` |
| modify | `usfds-web/src/utils/formatters.ts` | M2 | Thêm helper `formatModelVersion(semver)` (không gắn thêm `v` nếu đã bắt đầu bằng `v`) |
| modify | `usfds-web/src/components/modules/model/{ActivateModelModal,ModelHubView,ModelLineageModal,ModelLineagePanel,TrainingRunDetailView}.tsx` | M2 | Dùng `formatModelVersion` |
| modify | `usfds-web/src/components/modules/detection/{DetectionJobWizardView,DetectionJobsHubView,DetectionResultExplorerView}.tsx` | M2 | Dùng `formatModelVersion` |
| create | `usfds-web/src/utils/formatters.test.ts` | M2 | Test `formatModelVersion("v1") === "v1"` và legacy `"1.0.0" === "v1.0.0"` |

## 4. Dependencies & conflicts (with other tasks on BOARD)
| # | Check | Answer |
|---|---|---|
| D1 | Needs unfinished task? | No |
| D2 | Needed by unfinished task? | No |
| C1 | Modified files owned by in-progress task? | No (mọi task trên `.plan/BOARD.md` đều đã `Done`) |
| C2 | Hot-spot files touched | — |
| C3 | Schema change | Yes: `UniqueConstraint("model_id", "semver")` trên `model_versions` (Alembic revision riêng) |
| C4 | Public contract change | No (giữ nguyên field `semver: str`, chỉ đổi format giá trị mới sang `v1, v2, v3...`) |
| C5 | Shared UI shell change | No |

## 5. Acceptance tests (user reviews this section)
| Milestone | Test | Given | When | Then | Covers |
|---|---|---|---|---|---|
| M1 | `test_end_to_end_training_lifecycle_and_semver` (`usfds-core/tests/training/test_training_service.py`) | Model chưa có phiên bản nào | Chạy training run 1 rồi run 2 | Run 1 tạo `"v1"`, run 2 tạo `"v2"` | ISS-010 |
| M1 | `test_resolve_next_version_orders_numerically_not_lexically_or_by_timestamp` (`usfds-core/tests/training/test_training_service.py`) | Model có `"v10"` (cũ hơn) và `"v2"` (mới hơn theo `registered_at`) | Run mới hoàn tất | Phiên bản tiếp theo là `"v11"` (không phải `"v3"`) | ISS-010 |
| M1 | `test_lineage_label_no_double_v_prefix` (`usfds-core/tests/training/test_training_service.py`) | `ModelVersion` có `semver="v1"` | Gọi `get_model_lineage` | `node.label == "v1"` (không phải `"vv1"`) | ISS-010 |
| M1 | `test_model_version_unique_constraint_prevents_duplicates` (`usfds-infra/tests/test_model_version_uniqueness.py`) | Đã có `(model_id, "v1")` trong DB | Lưu thêm `ModelVersion` cùng `(model_id, "v1")` | DB ném `IntegrityError` | ISS-010 |
| M1 | `test_concurrent_completion_retries_and_allocates_distinct_versions` (`usfds-infra/tests/test_model_version_uniqueness.py`) | 2 training run của cùng `model_id` hoàn tất đồng thời | Cả 2 gọi `handle_training_completion` | Cả 2 thành công với phiên bản tách biệt `"v1"` và `"v2"` | ISS-010 |
| M2 | `test_formatModelVersion` (`usfds-web/src/utils/formatters.test.ts`) | Chuỗi `"v1"` hoặc chuỗi legacy `"1.0.0"` | Gọi `formatModelVersion` | `"v1"` → `"v1"`, `"1.0.0"` → `"v1.0.0"` | ISS-010 |

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

Checkpoint log (the agent appends one line per finished milestone):
- 26-11-20 M1 done: core 154 passed, 15 skipped; infra 39 passed; server 33 passed; notes: —
- 26-11-20 M2 done: web 18 test files / 30 passed, build & lint 0 errors; notes: —

## 7. Review hotspots (filled in after implementation)
1. `usfds-core/src/usfds_core/services/training/training_service.py:239-269` (M1): Retry loop (tối đa 5 lần) khi `DuplicateModelVersionError` xảy ra do 2 run hoàn tất đồng thời đọc cùng `latest`. Nếu retry hết 5 lần vẫn trùng sẽ raise lỗi để không ghi đè hoặc treo vô hạn. Được cover bởi `test_concurrent_completion_retries_and_allocates_distinct_versions`.
2. `usfds-infra/src/usfds_infra/database/repos/model.py:179-219` (M1): Dùng `session.begin_nested()` (SAVEPOINT) quanh `flush()` để `IntegrityError` trên `uq_model_versions_model_semver` chỉ rollback savepoint và chuyển thành `DuplicateModelVersionError` mà không làm hỏng transaction ngoài. Được cover bởi `test_concurrent_completion_retries_and_allocates_distinct_versions`.
3. `usfds-infra/src/usfds_infra/database/migrations/versions/14f998f68015_add_model_version_unique_semver.py:21-27` (M1): Alembic migration thêm `UniqueConstraint('model_id', 'semver')` (`down_revision='b1b7b507e88d'`). Lưu ý: nếu DB production/staging đang có sẵn bản ghi `(model_id, semver)` bị trùng từ trước khi có constraint, `alembic upgrade` sẽ fail cho tới khi dọn bản ghi trùng. Được cover bởi `test_migrations.py` và `test_model_version_unique_constraint_prevents_duplicates`.
4. `usfds-core/src/usfds_core/repositories/base_model_version_repo.py:14-29` (M1): `parse_version_sort_key` xếp `vN` (`(1, N)`) cao hơn legacy `X.Y.Z` (`(0, X, Y, Z)`), nên model đã có `1.0.0` sẽ bắt đầu chuỗi mới từ `v1` rồi `v2`, `v3`... Được cover bởi `test_resolve_next_version_orders_numerically_not_lexically_or_by_timestamp`.

## 8. Open questions
- —
