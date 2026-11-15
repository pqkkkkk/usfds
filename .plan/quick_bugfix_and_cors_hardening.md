# Plan: Quick Bugfix & CORS Hardening (ISS-035, ISS-014, ISS-017, ISS-003)

> **Task ID:** `quick_bugfix_and_cors_hardening` · **Issues:** ISS-035, ISS-014, ISS-017, ISS-003 · **Spec:** —
> **Conflict verdict:** PARALLEL-SAFE · **Status:** Done (26-11-15)

## 1. Context (facts)
- **ISS-035:** `SqliteModelRepository._to_entity` (`usfds-infra/src/usfds_infra/database/repos/model.py:44-50`) gọi `RiskLevel(record.risk_level)` nhưng `RiskLevel` chưa được import từ `usfds_core.domain.entities.enums`, gây `NameError` khi đọc model có `risk_level != None`.
- **ISS-017:** `DataManagementService.delete_dataset` (`usfds-core/src/usfds_core/services/data_management/service.py:118-134`) gọi `self.artifact_repo.get_by_dataset_id(dataset_id)` — method này không tồn tại (interface dùng `list_by_dataset`). `AttributeError` bị nuốt bởi `except Exception: pass`, khiến file artifact không bao giờ bị xóa khỏi storage.
- **ISS-003:** `DataManagementService.delete_dataset` (`usfds-core/src/usfds_core/services/data_management/service.py:111-144`) không kiểm tra xem dataset (hoặc các `artifact_id` của nó) có đang được dùng bởi `TrainingRun` (`run_datasets.dataset_artifact_id`) hay `DetectionJob` (`detection_jobs.target_artifact_id`) đang chạy/chờ (`PENDING`/`RUNNING`) hay không. Ngoài ra, `dataset_router.py:231-232` map mọi `ValueError` sang `404 Not Found`.
- **ISS-014:** `usfds-server/src/usfds_server/api.py:58-64` hardcode `allow_origins=["*"]` cùng `allow_credentials=True`, bỏ qua `settings.cors_origins` đã khai báo ở `usfds-server/src/usfds_server/config.py:91-94` (mặc định `"*"`). Khi bật auth/RBAC, bất kỳ origin nào cũng có thể gửi credentialed request.

## 2. Goal, scope verdict & non-goals
- **Goal:** Sửa dứt điểm 4 lỗi nhỏ/bảo mật (`ISS-035`, `ISS-014`, `ISS-017`, `ISS-003`) kèm test tái hiện và test chấp nhận cho từng issue.
- **Scope:** OK — 4 issue đều nhỏ, độc lập về nghiệp vụ nhưng cùng thuộc backend quick-fix/hardening, gọn trong 1 phiên.
- **Non-goals / omitted:**
  - Không thay đổi DB schema / không tạo Alembic migration mới.
  - Không chặn xóa dataset đã hoàn tất job (`COMPLETED`/`FAILED`/`CANCELLED`), chỉ chặn khi có job `PENDING`/`RUNNING` (tương đồng với `ProjectManagementService._check_active_workloads` ở `project_service.py:72-98`).
  - Không sửa `RuleManager.delete_rule` (thuộc `ISS-002`, ngoài scope task này).
- **Assumptions:**
  - `USFDS_CORS_ORIGINS` mặc định trong `config.py` chuyển từ `"*"` sang danh sách origin local dev (`http://localhost:5173,http://127.0.0.1:5173,http://localhost:8200,http://127.0.0.1:8200`); nếu user cấu hình tường minh `USFDS_CORS_ORIGINS="*"` thì server tự tắt `allow_credentials=False` để tránh cấu hình CORS không hợp lệ/không an toàn.

## 3. Files
| Action | File | Milestone | Note |
|---|---|---|---|
| modify | `usfds-infra/src/usfds_infra/database/repos/model.py` | M1 | Import `RiskLevel`; thêm `list_active_by_artifact_ids` trên `SqliteTrainingRunRepository` |
| modify | `usfds-infra/src/usfds_infra/database/repos/detection.py` | M1 | Thêm `list_active_by_target_artifact_ids` trên `SqliteDetectionJobRepository` |
| create | `usfds-infra/tests/test_model_repositories.py` | M1 | Test cho `ISS-035` |
| modify | `usfds-core/src/usfds_core/repositories/base_training_run_repo.py` | M1 | Thêm method `list_active_by_artifact_ids` |
| modify | `usfds-core/src/usfds_core/repositories/base_detection_job_repo.py` | M1 | Thêm method `list_active_by_target_artifact_ids` |
| modify | `usfds-core/src/usfds_core/repositories/in_memory_repos.py` | M1 | Implement `list_active_by_artifact_ids` trên `InMemoryTrainingRunRepository` |
| modify | `usfds-core/src/usfds_core/services/data_management/service.py` | M1 | Sửa `list_by_dataset` (ISS-017); thêm `DatasetInUseError` + reference check (ISS-003) |
| modify | `usfds-server/src/usfds_server/providers/data.py` | M2 | Inject `training_run_repo` và `detection_job_repo` vào `DataManagementService` |
| modify | `usfds-server/src/usfds_server/routers/dataset_router.py` | M2 | Map `DatasetInUseError` → `409 Conflict` |
| modify | `usfds-server/src/usfds_server/config.py` | M2 | Đổi default `cors_origins` sang local dev origins (append-only style, giữ nguyên field) |
| modify | `usfds-server/src/usfds_server/api.py` | M2 | Đọc `settings.cors_origins` vào `CORSMiddleware`, tắt `allow_credentials` nếu wildcard `*` |
| modify | `usfds-server/tests/test_dataset_api.py` | M2 | Test cho `ISS-017` và `ISS-003` |
| modify | `usfds-server/tests/test_api.py` | M2 | Test cho `ISS-014` |

## 4. Dependencies & conflicts (with other tasks on BOARD)
| # | Check | Answer |
|---|---|---|
| D1 | Needs unfinished task? | No (tất cả task trên BOARD đều đã `Done`) |
| D2 | Needed by unfinished task? | No |
| C1 | Modified files owned by in-progress task? | No (không có task nào đang `In progress`) |
| C2 | Hot-spot files touched | `usfds-server/src/usfds_server/config.py`, `usfds-server/src/usfds_server/api.py` (chỉ sửa đúng phần CORS, không reformat) |
| C3 | Schema change | No |
| C4 | Public contract change | No (thêm `409 Conflict` cho `DELETE /v1/datasets/{id}` khi dataset đang được dùng; không đổi payload thành công) |
| C5 | Shared UI shell change | No |

## 5. Acceptance tests (user reviews this section)
| Milestone | Test | Given | When | Then | Covers |
|---|---|---|---|---|---|
| M1 | `test_get_model_with_risk_level_returns_entity` (`usfds-infra/tests/test_model_repositories.py`) | Một `MLModel` trong DB có `risk_level="HIGH"` | Gọi `SqliteModelRepository.get_by_id(model_id)` | Trả về `Model` với `risk_level == RiskLevel.HIGH`, không lỗi `NameError` | ISS-035 |
| M2 | `test_delete_dataset_removes_artifact_files_from_storage` (`usfds-server/tests/test_dataset_api.py`) | Dataset có artifact lưu file tại path ngoài prefix `datasets/{dataset_id}/` (hoặc có file artifact trong storage) | Gọi `DELETE /v1/datasets/{dataset_id}` | Trả `200`, record bị xóa và file artifact không còn tồn tại trong storage | ISS-017 |
| M2 | `test_delete_dataset_used_by_active_training_run_returns_409` (`usfds-server/tests/test_dataset_api.py`) | Dataset có artifact đang gắn với `TrainingRun` trạng thái `RUNNING` | Gọi `DELETE /v1/datasets/{dataset_id}` | Trả `409 Conflict`, dataset và file vẫn còn nguyên | ISS-003 |
| M2 | `test_delete_dataset_used_by_active_detection_job_returns_409` (`usfds-server/tests/test_dataset_api.py`) | Dataset có artifact đang là `target_artifact_id` của `DetectionJob` trạng thái `PENDING` | Gọi `DELETE /v1/datasets/{dataset_id}` | Trả `409 Conflict`, dataset và file vẫn còn nguyên | ISS-003 |
| M2 | `test_delete_dataset_with_completed_jobs_succeeds` (`usfds-server/tests/test_dataset_api.py`) | Dataset có artifact gắn với `TrainingRun` và `DetectionJob` đều đã `COMPLETED` | Gọi `DELETE /v1/datasets/{dataset_id}` | Trả `200`, dataset bị xóa thành công | ISS-003 |
| M2 | `test_cors_allows_configured_origin_with_credentials` (`usfds-server/tests/test_api.py`) | `CORSMiddleware` được cấu hình với `http://localhost:5173` | Gửi request `OPTIONS` / `GET` với `Origin: http://localhost:5173` | Header `access-control-allow-origin` là `http://localhost:5173` và `access-control-allow-credentials` là `true` | ISS-014 |
| M2 | `test_cors_rejects_unlisted_origin` (`usfds-server/tests/test_api.py`) | `CORSMiddleware` được cấu hình với `http://localhost:5173` | Gửi request với `Origin: https://evil.example.com` | Không có header `access-control-allow-origin` cho `https://evil.example.com` | ISS-014 |
| M2 | `test_cors_wildcard_disables_credentials` (`usfds-server/tests/test_api.py`) | `cors_origins="*"` | Tạo CORS config / app middleware | `allow_credentials` là `False` khi `allow_origins` chứa `"*"` | ISS-014 |

## 6. Milestones & to-do (checkpoints, not stop points: all tests green at each)
The agent ticks items as it works. This is the task's only to-do list (`TODO.md` is no longer used for new work).

- [x] **M1 — Core & Infra fixes** (`usfds-core`, `usfds-infra`): Sửa `RiskLevel` import (ISS-035), sửa `list_by_dataset` (ISS-017), thêm query & reference check cho dataset đang dùng (ISS-003)
  - [x] [tests] Viết `test_get_model_with_risk_level_returns_entity` trong `usfds-infra/tests/test_model_repositories.py`; xác nhận fail với `NameError`
  - [x] [infra] Import `RiskLevel` trong `usfds-infra/src/usfds_infra/database/repos/model.py`
  - [x] [core] Thêm `list_active_by_artifact_ids` vào `ITrainingRunRepository` + `InMemoryTrainingRunRepository`, `list_active_by_target_artifact_ids` vào `IDetectionJobRepository`
  - [x] [infra] Implement 2 method query trên `SqliteTrainingRunRepository` và `SqliteDetectionJobRepository` (đảm bảo tương thích PostgreSQL guard)
  - [x] [core] Cập nhật `DataManagementService.delete_dataset` dùng `list_by_dataset`, bỏ nuốt `AttributeError`, thêm check active runs/jobs và raise `DatasetInUseError(ValueError)`
  - [x] [verify] `./scripts/test.sh core infra`
- [x] **M2 — Server wiring, CORS hardening & API acceptance tests** (`usfds-server`): Nối repo vào `DataManagementService`, map `409 Conflict`, cấu hình CORS từ `settings.cors_origins`
  - [x] [tests] Viết các test M2 trong `usfds-server/tests/test_dataset_api.py` và `usfds-server/tests/test_api.py`; xác nhận fail đúng lý do
  - [x] [server] Cập nhật `providers/data.py` và `routers/dataset_router.py` (`DatasetInUseError` → `409`)
  - [x] [server] Cập nhật `config.py` và `api.py` dùng `settings.cors_origins` (và tắt `allow_credentials` nếu wildcard `*`)
  - [x] [verify] `./scripts/test.sh core infra server`

Checkpoint log (the agent appends one line per finished milestone):
- 26-11-15 M1 done: core `149 passed, 15 skipped in 9.79s`, infra `35 passed, 1 xfailed in 3.92s`; notes: —
- 26-11-15 M2 done: server `30 passed, 31 warnings in 30.57s`; notes: —

## 7. Review hotspots (filled in after implementation)
- `usfds-core/src/usfds_core/services/data_management/service.py:121-162` (M1): Thứ tự kiểm tra `list_active_by_artifact_ids` / `list_active_by_target_artifact_ids` trước khi xóa file trong storage, và bỏ `except Exception: pass` bao ngoài để không nuốt `AttributeError`; được cover bởi `test_delete_dataset_removes_artifact_files_from_storage`, `test_delete_dataset_used_by_active_training_run_returns_409`, `test_delete_dataset_used_by_active_detection_job_returns_409`.
- `usfds-infra/src/usfds_infra/database/repos/model.py:423-442` & `usfds-infra/src/usfds_infra/database/repos/detection.py:150-167` (M1): Query lọc `PENDING`/`RUNNING` theo `artifact_ids` có guard `if not artifact_ids: return []` và qua PostgreSQL compatibility guard; được cover bởi các API test xóa dataset ở M2.
- `usfds-server/src/usfds_server/api.py:57-74` (M2): `build_cors_options` parse `settings.cors_origins` và tự động tắt `allow_credentials=False` khi có `*` hoặc rỗng; được cover bởi `test_cors_allows_configured_origin_with_credentials`, `test_cors_rejects_unlisted_origin`, `test_cors_wildcard_disables_credentials`.

## 8. Open questions
- —
