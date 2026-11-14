# Plan: Trực quan hóa phả hệ dữ liệu cho phiên bản mô hình (Model Version Lineage)

> **Task ID:** `model_version_lineage` · **Issues:** ISS-008 · **Spec:** — (chốt scope theo câu trả lời của user: hiển thị ở cả `TrainingRunDetailView` và Model Registry, chỉ upstream, read-only)
> **Conflict verdict:** PARALLEL-SAFE · **Status:** Done (26-11-14)

## 1. Context (facts)
- `ISS-008` ([11-13-2026.md](file:///home/antigravity/pqkkkkk/usfds/docs/issues/11-13-2026.md#L25-L29)) yêu cầu trực quan hóa data lineage cho `ModelVersion` của `TrainingRun`.
- Backend đã có:
  - [`DataLineageService`](file:///home/antigravity/pqkkkkk/usfds/usfds-core/src/usfds_core/services/data_management/lineage.py#L37-L82) dựng DAG `DatasetArtifact` qua `parent_artifact_id`.
  - [`TrainingOrchestrationService`](file:///home/antigravity/pqkkkkk/usfds/usfds-core/src/usfds_core/services/training/training_service.py#L37-L56) đã được inject sẵn `training_run_repo`, `model_version_repo`, `model_repo`, `dataset_artifact_repo` và có [`get_run_dataset_artifact_id`](file:///home/antigravity/pqkkkkk/usfds/usfds-core/src/usfds_core/services/training/training_service.py#L417-L422).
  - [`training_router.py`](file:///home/antigravity/pqkkkkk/usfds/usfds-server/src/usfds_server/routers/training_router.py#L314-L456) chưa có endpoint trả về lineage cho `ModelVersion` hoặc `TrainingRun`.
- Frontend đã có:
  - [`LineageCanvasView`](file:///home/antigravity/pqkkkkk/usfds/usfds-web/src/components/modules/LineageCanvasView.tsx#L19-L200) và [`computeCanvasLayout`](file:///home/antigravity/pqkkkkk/usfds/usfds-web/src/utils/lineageLayout.ts#L41-L157) hỗ trợ render DAG (`RAW`, `MAPPED`, `PRE_PROCESSED`), chưa có styling cho `FEATURE_ENGINEERED`, `TRAINING_RUN`, `MODEL_VERSION`.
  - [`TrainingRunDetailView.tsx`](file:///home/antigravity/pqkkkkk/usfds/usfds-web/src/components/modules/model/TrainingRunDetailView.tsx#L751-L795) mới chỉ hiển thị text metadata (`version_id`, `artifact_uri`, `checksum_sha256`).
  - [`ModelHubView.tsx`](file:///home/antigravity/pqkkkkk/usfds/usfds-web/src/components/modules/model/ModelHubView.tsx#L649-L702) bảng `ModelVersion` trong tab Model Registry chưa có nút xem lineage.

## 2. Goal, scope verdict & non-goals
- **Goal:** Cho phép người dùng xem đồ thị phả hệ dữ liệu read-only (`RAW → ... → FEATURE_ENGINEERED/PRE_PROCESSED → TRAINING_RUN → MODEL_VERSION`) và metadata chi tiết từng node tại cả trang chi tiết lượt huấn luyện (`TrainingRunDetailView`) và bảng phiên bản trong Model Registry (`ModelHubView`).
- **Scope:** OK
- **Non-goals / omitted:**
  - Không hiển thị downstream (`Deployment`, `DetectionJob`).
  - Không hỗ trợ thao tác rẽ nhánh/chỉnh sửa trên đồ thị lineage (chỉ read-only + click chọn node xem metadata và link sang Dataset Lineage).
  - Không thay đổi DB schema / Alembic migration.
- **Assumptions:**
  - Một `TrainingRun` liên kết tối đa 1 `dataset_artifact_id` chính qua `get_run_dataset_artifact_id(run_id)`.
  - Nếu `TrainingRun` thất bại hoặc chưa sinh `ModelVersion`, đồ thị vẫn hiển thị chuỗi `DatasetArtifact → TRAINING_RUN`.

## 3. Files
| Action | File | Milestone | Note |
|---|---|---|---|
| modify | `usfds-core/src/usfds_core/services/training/training_service.py` | M1 | Thêm DTO + `get_model_version_lineage`, `get_training_run_lineage` |
| modify | `usfds-core/tests/training/test_training_service.py` (hoặc file test training mới nếu chưa có) | M1 | Unit tests cho M1 |
| modify | `usfds-server/src/usfds_server/schemas/training_api_schemas.py` | M2 | Thêm `ModelLineageNodeResponse`, `ModelLineageEdgeResponse`, `ModelLineageResponse` |
| modify | `usfds-server/src/usfds_server/routers/training_router.py` | M2 | Thêm `GET /versions/{version_id}/lineage` và `GET /runs/{run_id}/lineage` |
| modify | `usfds-server/tests/test_training_api.py` | M2 | API tests cho 2 endpoint mới |
| modify | `usfds-web/src/types/navigation.ts` | M3 | Append optional `label?: string` vào `LineageRawNode` (hot-spot, append-only) |
| modify | `usfds-web/src/types/model.ts` | M3 | Thêm `ModelLineageNode`, `ModelLineageGraph` |
| modify | `usfds-web/src/api/trainingApi.ts` | M3 | Thêm `getModelVersionLineage`, `getTrainingRunLineage` |
| create | `usfds-web/src/hooks/useModelLineage.ts` | M3 | Hook `react-query` lấy lineage theo `versionId` / `runId` |
| modify | `usfds-web/src/hooks/index.ts` | M3 | Export `useModelLineage` (append-only) |
| modify | `usfds-web/src/components/modules/LineageCanvasView.tsx` | M3 | Hỗ trợ stage `FEATURE_ENGINEERED`, `TRAINING_RUN`, `MODEL_VERSION` và `node.label` |
| create | `usfds-web/src/components/modules/model/ModelLineagePanel.tsx` | M3 | Component render DAG + panel metadata read-only khi click node |
| create | `usfds-web/src/components/modules/model/ModelLineageModal.tsx` | M3 | Modal read-only bọc `ModelLineagePanel` cho `ModelHubView` |
| modify | `usfds-web/src/components/modules/model/TrainingRunDetailView.tsx` | M3 | Tích hợp `ModelLineagePanel` vào trang chi tiết lượt huấn luyện |
| modify | `usfds-web/src/components/modules/model/ModelHubView.tsx` | M3 | Thêm nút `Phả hệ` trên từng dòng `ModelVersion` mở `ModelLineageModal` |
| modify | `usfds-web/src/components/modules/model/index.ts` | M3 | Export mới (append-only) |
| create | `usfds-web/src/components/modules/model/ModelLineagePanel.test.tsx` | M3 | Vitest + MSW tests cho render lineage & click node metadata |

## 4. Dependencies & conflicts (with other tasks on BOARD)
| # | Check | Answer |
|---|---|---|
| D1 | Needs unfinished task? | No |
| D2 | Needed by unfinished task? | No |
| C1 | Modified files owned by in-progress task? | No |
| C2 | Hot-spot files touched | `usfds-web/src/types/navigation.ts`, `usfds-web/src/hooks/index.ts`, `usfds-web/src/components/modules/model/index.ts` (append-only) |
| C3 | Schema change | No |
| C4 | Public contract change | No (chỉ thêm 2 endpoint `GET` mới, không sửa endpoint/payload hiện có) |
| C5 | Shared UI shell change | No (`App.tsx`, `Sidebar.tsx`, `client.ts` không đổi) |

## 5. Acceptance tests (user reviews this section)
| Milestone | Test | Given | When | Then | Covers |
|---|---|---|---|---|---|
| M1 | `test_get_model_version_lineage_traces_full_upstream_chain` (`usfds-core/tests/training/test_model_lineage.py`) | Chuỗi `RAW → MAPPED → FEATURE_ENGINEERED` liên kết tới `TrainingRun` và `ModelVersion` | Gọi `service.get_model_version_lineage(version_id)` | Trả về đủ 5 nodes theo thứ tự từ `RAW` tới `MODEL_VERSION` và 4 edges nối đúng nguồn-đích | ISS-008 |
| M1 | `test_get_training_run_lineage_without_model_version` (`usfds-core/tests/training/test_model_lineage.py`) | `TrainingRun` trạng thái `FAILED` có `dataset_artifact_id` nhưng `version_id = None` | Gọi `service.get_training_run_lineage(run_id)` | Trả về chuỗi `DatasetArtifact → TRAINING_RUN` (không lỗi) | ISS-008 |
| M1 | `test_get_model_version_lineage_raises_when_not_found` (`usfds-core/tests/training/test_model_lineage.py`) | `version_id` không tồn tại | Gọi `service.get_model_version_lineage(version_id)` | Raise `ValueError` | ISS-008 |
| M2 | `test_get_version_lineage_endpoint_returns_dag` (`usfds-server/tests/test_training_api.py`) | DB có `DatasetArtifact` chain, `TrainingRun`, `ModelVersion` | `GET /api/v1/training/versions/{version_id}/lineage` | HTTP 200, `data.nodes` chứa `RAW..MODEL_VERSION`, `data.edges` khớp | ISS-008 |
| M2 | `test_get_run_lineage_endpoint_returns_dag_and_404` (`usfds-server/tests/test_training_api.py`) | 1 `run_id` hợp lệ và 1 `run_id` ngẫu nhiên | `GET /api/v1/training/runs/{run_id}/lineage` | HTTP 200 cho run hợp lệ; HTTP 404 cho run không tồn tại | ISS-008 |
| M3 | `test_model_lineage_panel_renders_nodes_and_inspector` (`usfds-web/src/components/modules/model/ModelLineagePanel.test.tsx`) | Mock API trả về 4 nodes (`RAW`, `MAPPED`, `TRAINING_RUN`, `MODEL_VERSION`) | Render `ModelLineagePanel` và click vào node `RAW` | Hiển thị đủ các node trên canvas và panel metadata cập nhật thông tin của node `RAW` | ISS-008 |
| M3 | `test_model_hub_opens_lineage_modal_for_version` (`usfds-web/src/components/modules/model/ModelLineagePanel.test.tsx`) | `ModelHubView` có model với 1 `ModelVersion` | Mở rộng model và bấm nút `Phả hệ` | Mở modal read-only hiển thị đồ thị lineage của `ModelVersion` đó | ISS-008 |

## 6. Milestones & to-do (checkpoints, not stop points: all tests green at each)
- [x] **M1 — Core Lineage Service** (`usfds-core`): Truy vết DAG upstream cho `ModelVersion` và `TrainingRun`
  - [x] [tests] Viết tests M1 trong `usfds-core/tests/training/test_model_lineage.py`; xác nhận fail đúng lý do
  - [x] [core] Thêm `ModelLineageNode`, `ModelLineageEdge`, `ModelLineageGraph` và `get_model_version_lineage`, `get_training_run_lineage` vào `TrainingOrchestrationService`
  - [x] [verify] `./scripts/test.sh core`
- [x] **M2 — Server Lineage Endpoints** (`usfds-server`): Expose API read-only cho Web
  - [x] [tests] Viết API tests M2 trong `usfds-server/tests/test_training_api.py`; xác nhận fail đúng lý do
  - [x] [server] Thêm schemas trong `training_api_schemas.py` và routes `GET /versions/{version_id}/lineage`, `GET /runs/{run_id}/lineage` trong `training_router.py`
  - [x] [verify] `./scripts/test.sh server`
- [x] **M3 — Web Lineage Visualization** (`usfds-web`): Hiển thị DAG read-only tại `TrainingRunDetailView` và `ModelHubView`
  - [x] [tests] Viết Vitest + MSW tests M3 trong `ModelLineagePanel.test.tsx`; xác nhận fail đúng lý do
  - [x] [web] Cập nhật `types/navigation.ts`, `types/model.ts`, `trainingApi.ts`, tạo `useModelLineage.ts`, cập nhật `LineageCanvasView.tsx`
  - [x] [web] Tạo `ModelLineagePanel.tsx`, `ModelLineageModal.tsx`; tích hợp vào `TrainingRunDetailView.tsx` và `ModelHubView.tsx`
  - [x] [verify] `./scripts/test.sh web` và `./scripts/test.sh core server`

Checkpoint log:
- 26-11-14 M1 done: `146 passed, 15 skipped, 9 warnings in 5.47s`; notes: —
- 26-11-14 M2 done: `16 passed, 18 warnings in 10.34s`; notes: —
- 26-11-14 M3 done: `Test Files 11 passed (11), Tests 19 passed (19)` + `npm run build` + `npm run lint` (`0 errors`); notes: thêm `test_model_lineage_panel_shows_error_state`

## 7. Review hotspots (filled in after implementation)
- `usfds-core/src/usfds_core/services/training/training_service.py:481-646` (M1): Truy vết chuỗi `parent_artifact_id` từ `dataset_artifact_id` của `TrainingRun` lên `RAW` với `visited: Set[UUID]` chống vòng lặp vô hạn và dừng an toàn nếu thiếu parent; xử lý `TrainingRun` thất bại chưa có `ModelVersion`. Covered by `test_get_model_version_lineage_traces_full_upstream_chain`, `test_get_training_run_lineage_without_model_version`.
- `usfds-server/src/usfds_server/routers/training_router.py:358-394,505-522` (M2): Map `ValueError` từ service sang HTTP 404 cho cả `/versions/{version_id}/lineage` và `/runs/{run_id}/lineage`. Covered by `test_get_version_lineage_endpoint_returns_dag`, `test_get_run_lineage_endpoint_returns_dag_and_404`.
- `usfds-web/src/hooks/useModelLineage.ts:19-45` (M3): Throw error khi `!res.success` để `react-query` chuyển sang error state (tránh `apiClient` nuốt lỗi theo ISS-028). Covered by `test_model_lineage_panel_shows_error_state`.
- `usfds-web/src/components/modules/LineageCanvasView.tsx:47-68,208-212` (M3): Thêm màu cho `FEATURE_ENGINEERED`, `TRAINING_RUN`, `MODEL_VERSION` và ưu tiên hiển thị `node.label` giữ nguyên hành vi cũ cho `DatasetLineageExplorer`. Covered by `test_model_lineage_panel_renders_nodes_and_inspector`.

## 8. Open questions
- —
