# Plan: Project-Scoped Access Control Hardening (List, Get-by-ID & Cross-Project Guards)

> **Task ID:** `project_scoped_access_control` (= this file name) · **Issues:** `ISS-042` · **Spec:** `.plan/user_management_rbac.md`, `.plan/rbac_feature_visibility.md`, reference pattern `usfds-server/src/usfds_server/routers/investigation_router.py`
> **Conflict verdict:** PARALLEL-SAFE · **Status:** Done (26-11-22)

## 1. Context (facts)
- **`GET /api/v1/datasets`** (`usfds-server/src/usfds_server/routers/dataset_router.py:183-201`): `project_id` là `Optional[UUID]`. Khi bỏ `project_id`, bỏ qua `authz.require_project_permission(actor, "dataset:read", project_id)` và chỉ lọc theo `ds.project_id in member_pids` (`L195-L197`), khiến member không có `dataset:read` vẫn liệt kê được toàn bộ dataset của project.
- **`POST /api/v1/datasets/import`** (`dataset_router.py:106-118`, `usfds-server/src/usfds_server/schemas/dataset_api_schemas.py:14`, `usfds-core/src/usfds_core/services/data_management/ingestion.py:116`): `req.project_id` là `Optional[UUID] = None`; khi không truyền, bỏ qua hoàn toàn `dataset:create` và `ingestion.py:116` tự sinh `project_id = uuid4()` mồ côi.
- **`training_router.py`** (`usfds-server/src/usfds_server/routers/training_router.py:352-648`):
  - `GET /models` (`L358-L370`), `GET /models/{id}/versions` (`L404-L420`), `GET /runs` (`L578-L590`) để `project_id` optional và bỏ qua `require_project_permission` khi `project_id is None`.
  - `GET /models/{id}` (`L390-L391`), `GET /versions/{id}` (`L442-L443`), `GET /versions/{id}/lineage` (`L486-L487`), `GET /runs/{id}` (`L616-L617`), `GET /runs/{id}/lineage` (`L640-L641`) đều kiểm tra `if entity.project_id is not None:`, bỏ qua toàn bộ kiểm tra quyền khi `project_id IS NULL`.
  - `TrainingOrchestrationService.list_training_runs` (`usfds-core/src/usfds_core/services/training/training_service.py:482-486`) lọc `r.project_id == project_id or r.project_id is None`, làm lộ run `project_id IS NULL` ngay cả khi truyền `project_id`.
  - `POST /api/v1/training/runs` (`training_router.py:534-568`, `training_api_schemas.py:38`, `training_service.py:96-168`): `project_id` là optional và `prepare_and_dispatch` không kiểm tra `dataset_artifact_id` và `model_id` có thuộc `project_id` hay không (`providers/training.py:23-57` chưa inject `dataset_repo`).
- **Nhóm `GET by ID` không nhận `project_id` và fetch DB trước khi check quyền** (gây 404 vs 403 ID existence oracle và không đối chiếu `project_id` ngữ cảnh):
  - `dataset_router.py:204-222, 283-301` (`get_dataset`, `get_artifact`)
  - `training_router.py:377-394, 429-449, 473-494, 603-624, 627-648` (`get_model`, `get_model_version`, `get_model_version_lineage`, `get_training_run`, `get_training_run_lineage`)
  - `detection_router.py:119-259` (`get_detection_job`, `get_detection_job_results`, `export_detection_job_results`)
  - `rule_router.py:139-155, 235-253` (`get_rule`, `get_rule_versions`)
- **`rule_router.py` cross-project `version_id` & `dataset` bypass**:
  - `evaluate_single_rule` (`rule_router.py:301-302`) và `backtest_rule_on_dataset` (`rule_router.py:447-448`) tải `RuleVersion` theo `version_id` mà không xác minh `target_version.rule_id == rule.rule_id`.
  - `backtest_rule_on_dataset` (`rule_router.py:415`) dùng `if dataset and str(dataset.project_id) != ...`, bỏ qua nếu `dataset is None`.
- **`GET /api/v1/storage/presigned-download`** (`storage_router.py:108-158`): không nhận `project_id`, đoán project từ UUID đầu tiên trong `object_key.split("/")` (`L125-L133`), không chặn path traversal `..`, và chỉ kiểm tra `project:read` thay vì quyền export tương ứng và xác minh sở hữu thực tế của object key.
- **`usfds-web/src/api/*`**: đã có `projectId` ở các màn hình gọi list, nhưng các hàm `getDatasetDetail`, `getArtifact`, `getModel`, `getModelVersion`, `getTrainingRun`, `getModelVersionLineage`, `getTrainingRunLineage`, `getJob`, `getJobResults`, `exportResults`, `getRule`, `getRuleVersions`, `requestPresignedDownload` chưa truyền `project_id`.

## 2. Goal, scope verdict & non-goals
- **Goal:** Bắt buộc `project_id: UUID` trên toàn bộ API `list` và `get by id` thuộc phạm vi project (cùng `POST /datasets/import`, `POST /training/runs`, `GET /storage/presigned-download`), kiểm tra quyền theo `project_id` trước khi truy vấn DB/storage, đối chiếu quyền sở hữu bản ghi theo `project_id` (trả `404` khi lệch hoặc khi bản ghi `TrainingRun`/`ModelVersion` có `project_id IS NULL`), vá cross-project checks trên `training` & `rule`, và cập nhật đồng bộ `usfds-web`.
- **Scope:** OK
- **Non-goals / omitted:**
  - Không thêm cột `owner_id` / migration cho `GrantScope.OWN` trên các bảng lưu `created_by` string (`rules`, `detection_jobs`, `training_runs`) — tách thành follow-up riêng nếu cần.
  - Không thay đổi schema DB (không cần Alembic migration; bản ghi cũ có `project_id IS NULL` ở `training_runs`/`model_versions` bị chặn tự nhiên qua điều kiện `entity.project_id == project_id`).
  - Không sửa nhóm router SYSTEM (`auth`, `user`, `rbac`, `system_metadata`) hay `project_router` (đã dùng `can_list` và check `project:read` trước DB).
  - Không đổi chữ ký các endpoint mutate đã check quyền theo `project_id` `NOT NULL` (như `DELETE /datasets/{id}`, `PUT /rules/{id}`), ngoại trừ các lỗ hổng thực tế đã xác định (`POST /datasets/import`, `POST /training/runs`, `POST /rules/{id}/evaluate`, `POST /rules/backtest`).
- **Assumptions:**
  - Built-in / global models (`Model.project_id is None`) vẫn được phép đọc qua `GET /training/models`, `GET /training/models/{id}`, `GET /training/models/{id}/versions` khi caller truyền `project_id` hợp lệ và có quyền `model:read` trên `project_id` đó.
  - Khi caller có quyền trên `project_id` nhưng `resource_id` không tồn tại hoặc thuộc project khác (hoặc có `project_id is None` với `TrainingRun`/`ModelVersion`), API trả `404 Not Found` (khớp pattern `investigation_router.py`) để chống ID existence oracle.
  - `GET /api/v1/storage/presigned-download` yêu cầu `project_id: UUID` và xác minh `object_key` theo prefix hợp lệ (`uploads/{purpose}/{project_id}/...`, `exports/reports/{project_id}/...`, `exports/datasets/{dataset_id}/...`, `datasets/{dataset_id}/...`, `datasets/{project_id}/inferences/...`, `exports/detection/{job_id}/...`) kèm kiểm tra permission tương ứng (`project:read` / `dataset:export` / `detection:export` / `report:export`).

## 3. Files
| Action | File | Milestone | Note |
|---|---|---|---|
| modify | `usfds-core/src/usfds_core/services/training/training_service.py` | M1 | inject optional `dataset_repo`; kiểm tra cross-project cho `model` và `dataset_artifact` trong `prepare_and_dispatch`; bỏ `or r.project_id is None` trong `list_training_runs` |
| modify | `usfds-core/tests/training/test_training_service.py` | M1 | thêm unit tests cho cross-project guard và strict project filter trên `list_training_runs` |
| modify | `usfds-server/src/usfds_server/providers/training.py` | M2 | inject `dataset_repo = Depends(get_dataset_repo)` vào `TrainingOrchestrationService` |
| modify | `usfds-server/src/usfds_server/schemas/dataset_api_schemas.py` | M2 | đổi `ImportDatasetRequest.project_id` thành `UUID` bắt buộc |
| modify | `usfds-server/src/usfds_server/schemas/training_api_schemas.py` | M2 | đổi `StartTrainingRunRequest.project_id` thành `UUID` bắt buộc |
| modify | `usfds-server/src/usfds_server/routers/dataset_router.py` | M2 | bắt buộc `project_id` + authz trước DB + verify `dataset.project_id == project_id` trên `list_datasets`, `get_dataset`, `get_artifact`, `import_dataset` |
| modify | `usfds-server/src/usfds_server/routers/training_router.py` | M2 | bắt buộc `project_id` + authz trước DB + verify project ownership trên `list_models`, `get_model`, `list_model_versions`, `get_model_version`, `get_model_version_lineage`, `list_training_runs`, `get_training_run`, `get_training_run_lineage`, `start_training_run` |
| modify | `usfds-server/src/usfds_server/routers/detection_router.py` | M2 | bắt buộc `project_id` + authz trước DB + verify `job.project_id == project_id` trên `get_detection_job`, `get_detection_job_results`, `export_detection_job_results` |
| modify | `usfds-server/src/usfds_server/routers/rule_router.py` | M2 | bắt buộc `project_id` + authz trước DB + verify `rule.project_id == project_id` trên `get_rule`, `get_rule_versions`; verify `target_version.rule_id == rule.rule_id` và `dataset is not None` trên `evaluate_single_rule`, `backtest_rule_on_dataset` |
| modify | `usfds-server/src/usfds_server/routers/storage_router.py` | M2 | bắt buộc `project_id`, chặn `..` path traversal, xác minh `object_key` ownership qua prefix + `dataset_repo`/`detection_job_repo` và check permission trước khi chạm storage |
| modify | `usfds-server/tests/test_auth_and_rbac_api.py` | M2 | thêm acceptance tests `ISS-042` cho toàn bộ list, get-by-id, oracle prevention, null-project blocking, cross-project training/rule, storage guard |
| modify | `usfds-server/tests/test_dataset_api.py` | M2 | cập nhật truyền `project_id` cho các lời gọi `GET /datasets`, `GET /datasets/{id}`, `GET /datasets/{id}/artifacts/{aid}`, `POST /datasets/import` |
| modify | `usfds-server/tests/test_training_api.py` | M2 | cập nhật truyền `project_id` cho các lời gọi training `list`, `get`, `lineage`, `POST /runs` |
| modify | `usfds-server/tests/test_detection_api.py` | M2 | cập nhật truyền `project_id` cho `GET /jobs/{id}`, `/results`, `/export` |
| modify | `usfds-server/tests/test_rule_api.py` | M2 | cập nhật truyền `project_id` cho `GET /rules/{id}`, `/versions` |
| modify | `usfds-server/tests/test_queue_mode_api.py` | M2 | cập nhật truyền `project_id` cho `POST /datasets/import` và `GET /datasets/{id}` |
| modify | `usfds-web/src/api/datasetApi.ts` | M3 | bắt buộc `projectId` trên `listDatasets`, `getDatasetDetail`, `getArtifact` |
| modify | `usfds-web/src/api/trainingApi.ts` | M3 | bắt buộc `projectId` trên `listModels`, `getModel`, `listModelVersions`, `getModelVersion`, `listTrainingRuns`, `getTrainingRun`, `getModelVersionLineage`, `getTrainingRunLineage` |
| modify | `usfds-web/src/api/detectionApi.ts` | M3 | bắt buộc `projectId` trên `getJob`, `getJobResults`, `getExportUrl`, `exportResults` |
| modify | `usfds-web/src/api/ruleApi.ts` | M3 | bắt buộc `projectId` trên `getRule`, `getRuleVersions` |
| modify | `usfds-web/src/api/storageApi.ts` | M3 | bắt buộc `projectId` trên `requestPresignedDownload` |
| modify | `usfds-web/src/hooks/useDatasetList.ts` | M3 | guard `enabled: Boolean(projectId)` và truyền `projectId` bắt buộc |
| modify | `usfds-web/src/hooks/useDatasetDetail.ts` | M3 | nhận `projectId`, guard `enabled`, truyền `projectId` vào `getDatasetDetail` |
| modify | `usfds-web/src/hooks/useDatasetPipeline.ts` | M3 | nhận `projectId`, guard `enabled`, truyền `projectId` vào `getDatasetDetail` |
| modify | `usfds-web/src/hooks/useModelLineage.ts` | M3 | nhận `projectId`, guard `enabled`, truyền `projectId` vào `getModelVersionLineage` / `getTrainingRunLineage` |
| modify | `usfds-web/src/components/modules/data_management/{DatasetLineageExplorer,DataPipelineWorkspace}.tsx` | M3 | truyền `currentProjectId` vào `useDatasetDetail` / `useDatasetPipeline` |
| modify | `usfds-web/src/components/modules/model/{ModelHubView,ModelLineagePanel,ModelLineageModal,TrainingRunDetailView,TrainingWizardView}.tsx` | M3 | truyền `projectId` vào `trainingApi` / `datasetApi` / `useModelLineage` |
| modify | `usfds-web/src/components/modules/detection/{DetectionJobWizardView,DetectionResultExplorerView}.tsx` | M3 | truyền `projectId` vào `getDatasetDetail`, `getJobResults`, `exportResults` |
| modify | `usfds-web/src/components/modules/rule/{RuleDryRunWorkspace,RuleWorkspace,RuleVersionHistoryModal}.tsx` | M3 | truyền `projectId` vào `getDatasetDetail`, `getRule`, `getRuleVersions` |
| modify | `usfds-web/src/components/modules/data_management/DatasetHubView.test.tsx` | M3 | truyền `projectId` cho `detectionApi.exportResults` và assert query param |
| modify | `usfds-web/src/components/modules/model/{ModelHubView,ModelLineagePanel}.test.tsx` | M3 | truyền `projectId` và assert query param `project_id` |
| create | `usfds-web/src/test/projectScopedApi.test.ts` | M3 | kiểm thử unit/MSW xác nhận mọi client `list` và `get by id` đều đính kèm `project_id` |

## 4. Dependencies & conflicts (with other tasks on BOARD)
| # | Check | Answer |
|---|---|---|
| D1 | Needs unfinished task? | No (`user_management_rbac`, `rbac_feature_visibility`, `model_versioning_scheme` đều đã `Done`) |
| D2 | Needed by unfinished task? | No |
| C1 | Modified files owned by in-progress task? | No (không có task `In progress` trên BOARD) |
| C2 | Hot-spot files touched | — |
| C3 | Schema change | No |
| C4 | Public contract change | Yes: bắt buộc `project_id` trên các REST endpoints `list`/`get-by-id` của `dataset`, `training`, `detection`, `rule`, `storage`, `POST /datasets/import`, `POST /training/runs` → consumers: `usfds-web/src/api/*` (cập nhật trong M3), `usfds-server/tests/*` (cập nhật trong M2) |
| C5 | Shared UI shell change | No |

## 5. Acceptance tests (user reviews this section)
| Milestone | Test | Given | When | Then | Covers |
|---|---|---|---|---|---|
| M1 | `test_prepare_and_dispatch_rejects_cross_project_artifact_and_model` (`usfds-core/tests/training/test_training_service.py`) | Project A và Project B có dataset artifact và custom model riêng | Gọi `prepare_and_dispatch` với `project_id=A` nhưng `dataset_artifact_id` thuộc B, hoặc `model_id` thuộc B | Raise `ValueError` (BR-PM-06); không tạo `TrainingRun`; built-in model (`project_id=None`) vẫn được phép train trong Project A | `ISS-042` / `BR-PM-06` |
| M1 | `test_list_training_runs_excludes_null_project_runs_when_filtered` (`usfds-core/tests/training/test_training_service.py`) | DB/repo có run thuộc Project A và run cũ có `project_id=None` | Gọi `list_training_runs(project_id=A)` | Chỉ trả về run có `project_id == A`, không rò rỉ run `project_id=None` | `ISS-042` |
| M2 | `test_list_and_import_endpoints_require_project_id_and_enforce_permission` (`usfds-server/tests/test_auth_and_rbac_api.py`) | User có custom role thuộc Project A nhưng không có `dataset:read`/`dataset:create`, và `fraud_analyst` không có `model:read`/`training:read` | Gọi `GET /datasets`, `POST /datasets/import`, `GET /training/models`, `GET /training/models/{id}/versions`, `GET /training/runs`, `POST /training/runs` khi (a) thiếu `project_id` và (b) có `project_id=A` | (a) Thiếu `project_id` trả `422`; (b) Có `project_id=A` nhưng thiếu quyền trả `403` (không còn bypass `member_pids` hay `project_id is None`) | `ISS-042` |
| M2 | `test_get_by_id_endpoints_require_project_id_block_null_and_prevent_oracle` (`usfds-server/tests/test_auth_and_rbac_api.py`) | User thuộc Project A (có đủ quyền read), không thuộc Project B; tồn tại dataset/artifact/model/version/run/job/rule ở Project B và version/run có `project_id=None` | Gọi các endpoint `GET by ID` & `lineage` & `detection export`: (a) thiếu `project_id`, (b) truyền `project_id=B`, (c) truyền `project_id=A` với ID của B hoặc ID có `project_id=None`, (d) truyền `project_id=A` với built-in model | (a) `422`; (b) `403` (kể cả ID không tồn tại ở B → không lộ 404 vs 403); (c) `404`; (d) built-in model trả `200` khi có `model:read` trên A và `403` khi không có | `ISS-042` |
| M2 | `test_cross_project_training_rule_version_and_storage_download_blocked` (`usfds-server/tests/test_auth_and_rbac_api.py`) | `data_scientist` ở Project A cố dùng `dataset_artifact_id` của Project B trong `POST /training/runs`; cố dùng `version_id` của rule Project B trong `POST /rules/{rule_A}/evaluate` & `/backtest`; gọi `GET /storage/presigned-download` không có `project_id`, có `..`, hoặc trỏ `object_key` của Project B | Gửi các request vi phạm xuyên project | `POST /training/runs` trả `400`; `rule evaluate`/`backtest` trả `400`/`404`; `storage/presigned-download` thiếu `project_id` trả `422`, `..` trả `400`, khác project hoặc thiếu quyền export trả `403` | `ISS-042` |
| M3 | `test_web_api_clients_attach_project_id_on_all_list_and_get_by_id_calls` (`usfds-web/src/test/projectScopedApi.test.ts`) | MSW server ghi nhận query params của tất cả endpoint `datasets`, `training`, `detection`, `rules`, `storage` | Gọi toàn bộ hàm `list` và `get by id` trên `datasetApi`, `trainingApi`, `detectionApi`, `ruleApi`, `storageApi` kèm `projectId` | Mọi request đều gửi đúng query param `project_id=<projectId>` | `ISS-042` |

## 6. Milestones & to-do (checkpoints, not stop points: all tests green at each)
The agent ticks items as it works. This is the task's only to-do list (`TODO.md` is no longer used for new work).

- [x] **M1 — Core Training Cross-Project & Null-Project Guards** (`usfds-core`): `TrainingOrchestrationService` chặn cross-project artifact/model và không rò rỉ run `project_id=None`.
  - [x] [tests] Viết 2 M1 tests trong `usfds-core/tests/training/test_training_service.py`; xác nhận fail trước khi sửa
  - [x] [core] Cập nhật `usfds-core/src/usfds_core/services/training/training_service.py` (inject optional `dataset_repo`, kiểm tra `model`/`dataset_artifact` theo `project_id`, bỏ `or r.project_id is None` trong `list_training_runs`)
  - [x] [verify] `./scripts/test.sh core`
- [x] **M2 — Mandatory `project_id` Enforcement & Ownership Verification Across Routers** (`usfds-server`): toàn bộ `list`, `get by id`, `import`, `training/runs`, `rule evaluate/backtest`, `storage/presigned-download` siết quyền trước DB và chống oracle.
  - [x] [tests] Viết 3 M2 acceptance tests trong `usfds-server/tests/test_auth_and_rbac_api.py`; xác nhận fail trước khi sửa
  - [x] [server] Cập nhật `providers/training.py`, `schemas/{dataset,training}_api_schemas.py`, `routers/{dataset,training,detection,rule,storage}_router.py`
  - [x] [tests] Cập nhật các test server hiện có (`test_dataset_api.py`, `test_training_api.py`, `test_detection_api.py`, `test_rule_api.py`, `test_queue_mode_api.py`) truyền `project_id` theo contract mới
  - [x] [verify] `./scripts/test.sh core infra server worker cli`
- [x] **M3 — Web API Clients, Hooks & Views Alignment** (`usfds-web`, `all`): toàn bộ lời gọi `list` và `get by id` trên frontend truyền `project_id` và test/build/lint xanh.
  - [x] [tests] Viết `usfds-web/src/test/projectScopedApi.test.ts` và cập nhật assertions trong `DatasetHubView.test.tsx`, `ModelHubView.test.tsx`, `ModelLineagePanel.test.tsx`
  - [x] [web] Cập nhật `api/{dataset,training,detection,rule,storage}Api.ts`, `hooks/{useDatasetList,useDatasetDetail,useDatasetPipeline,useModelLineage}.ts`, và các components gọi tương ứng
  - [x] [verify] `./scripts/test.sh` + `cd usfds-web && npm run build && npm run lint`

Checkpoint log (the agent appends one line per finished milestone):
- 26-11-21 M1 done: `161 passed, 15 skipped, 169 warnings in 9.45s`; notes: —
- 26-11-21 M2 done: `core 161 passed (15 skipped), infra 40 passed, server 39 passed, worker 3 passed, cli 5 passed`; notes: updated `test_api.py` S3 presigned-download test to pass `project_id` and scoped key
- 26-11-21 M3 done: `web 20 files / 35 tests passed (+1 node test), build 862ms, lint 0 errors; re-verified core 161 passed (15 skipped), infra 40 passed, server 39 passed, worker 3 passed, cli 5 passed`; notes: required `projectId` in web API clients and guarded hooks/components when no active project is selected

## 7. Review hotspots (filled in after implementation)
1. `usfds-core/src/usfds_core/services/training/training_service.py:108-121` & `:485-505` (M1): đối chiếu `model.project_id` and `dataset.project_id` với `effective_project_id` trước khi tạo `TrainingRun` (chỉ bỏ qua check model cho built-in `model.project_id is None`, và giữ fallback `dataset_repo is None` cho caller không inject); loại bỏ `r.project_id is None` khỏi `list_training_runs(project_id=...)`. Covered by `test_prepare_and_dispatch_rejects_cross_project_artifact_and_model`, `test_list_training_runs_excludes_null_project_runs_when_filtered`.
2. `usfds-server/src/usfds_server/routers/training_router.py:433-495` (M2): các endpoint `GET by ID` & lineage check `authz.require_project_permission(..., project_id)` trước khi truy vấn DB và chặn `entity.project_id is None` (trả `404`) đối với `ModelVersion`/`TrainingRun` trong khi cho phép built-in `Model.project_id is None` qua `model:read` trên `project_id`. Covered by `test_get_by_id_endpoints_require_project_id_block_null_and_prevent_oracle`.
3. `usfds-server/src/usfds_server/routers/storage_router.py:115-190` (M2): `_authorize_download_key` chuẩn hóa `object_key` (chặn `\` và `..`), suy ra quyền export/read tương ứng theo prefix (`uploads/*`, `exports/reports/*`, `exports/datasets/*`, `exports/detection/*`, `datasets/*`) và đối chiếu DB/UUID với `project_id` query param bắt buộc. Covered by `test_cross_project_training_rule_version_and_storage_download_blocked`.
4. `usfds-server/src/usfds_server/routers/rule_router.py:402-455` (M2): `backtest_rule_on_dataset` ép `if not dataset or str(dataset.project_id) != ...` (fix lỗi bypass khi `dataset is None`) và cùng `evaluate_single_rule` xác minh `target_ver.rule_id == rule.rule_id` khi truyền `version_id`. Covered by `test_cross_project_training_rule_version_and_storage_download_blocked`.
5. `usfds-web/src/hooks/useModelLineage.ts:5-38` & `usfds-web/src/hooks/useDatasetList.ts:16-31` & `usfds-web/src/hooks/useDatasetDetail.ts:10-34` (M3): các hook fetch giữ `enabled: Boolean(... && projectId)` để tránh gửi request thiếu `project_id` gây 422 khi ProjectContext chưa mount xong. Covered by `projectScopedApi.test.ts`, `ModelLineagePanel.test.tsx`, `ModelHubView.test.tsx`.

## 8. Open questions
- — (đã chốt toàn bộ với user ngày 26-11-21: PA-A cho `list` và `get by id`, bắt buộc `project_id` cho `POST /datasets/import` và `POST /training/runs`, chặn bản ghi `project_id=NULL` trừ built-in models, gộp `rule_router` và `storage/presigned-download`, tách riêng `GrantScope.OWN`.)
