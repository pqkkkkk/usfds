# Plan: Chuẩn hóa File I/O qua `IFileStorage` (`ISS-015`) & Sửa luồng Presigned Upload / Export (`ISS-036`)

> **Task ID:** `presigned_upload_and_file_io_guard` (= this file name) · **Issues:** ISS-015, ISS-036 · **Spec:** `docs/features/data_management/user-flow-and-ui-design.md`, `docs/arch/high-level-design.md`
> **Conflict verdict:** PARALLEL-SAFE · **Status:** Done (26-11-15)

## 1. Context (facts)
- **Vấn đề 1 — Phân tán `Path(...).is_file()` ngoài `IFileStorage` (`ISS-015`):**
  - Dù `LocalFileStorage._resolve_path(file_path)` (`usfds-infra/src/usfds_infra/storage/local_storage.py:15-23`) đã hỗ trợ sẵn cả đường dẫn tuyệt đối (`p.is_absolute() -> p`) lẫn đường dẫn tương đối trong `base_dir`, nhiều service và router lại tự viết nhánh `if Path(path).is_file(): ... else: storage.read_bytes(...)`:
    - `usfds-core/src/usfds_core/services/data_management/ingestion.py:90-108` (`import_dataset`)
    - `usfds-core/src/usfds_core/services/inference/inference_service.py:98-100, 585-591` (`_read_bytes`, `_resolve_input_source`)
    - `usfds-core/src/usfds_core/services/inference/executor.py:258-261` (`_read_bytes`)
    - `usfds-core/src/usfds_core/services/training/training_service.py:297-328, 408-414` (`register_plugged_model`, `activate_model_version`)
    - `usfds-core/src/usfds_core/services/training/executor.py:37-43` (`_read_bytes`)
    - `usfds-core/src/usfds_core/services/preprocessing/feature_engineering_service.py:39-53` (`_load_dataframe`)
    - `usfds-core/src/usfds_core/services/preprocessing/leaked_feature_engineering_service.py:41-55` (`_load_dataframe`)
    - `usfds-core/src/usfds_core/services/preprocessing/preprocessing_service.py:42-65` (`_load_dataframe`)
    - `usfds-core/src/usfds_core/services/insight_report/engine.py:127-135` (`_read_parquet_bytes`)
    - `usfds-server/src/usfds_server/routers/rule_router.py:348-355` (`_load_artifact_dataframe`)
    - `usfds-worker/src/usfds_worker/handlers.py:84-91` (`_load_artifact_dataframe`)
  - Ngoài ra, `S3FileStorage.save_file` (`usfds-infra/src/usfds_infra/storage/s3_storage.py:140-144`) cũng có nhánh `if Path(src_path).is_file(): self._client.upload_file(...)` cho phép client gửi đường dẫn file trên máy chủ để copy thẳng lên S3.
  - Hậu quả: Code lặp lại `if-else` ở 11 nơi và khi chạy Client-Server (`USFDS_STORAGE_BACKEND=s3`), client có thể truyền đường dẫn nội bộ của server (ví dụ `/etc/passwd` hoặc file bất kỳ) để đọc dữ liệu (`ISS-015`).
- **Vấn đề 2 — `/api/health` và Presigned Upload / Download ở Client-Server mode (`ISS-036`):**
  - Trên Backend, `usfds-server/src/usfds_server/api.py:132-162` đã có cả `@app.get("/health")` và `@app.get("/api/health")`, trả JSON thô `{ "status": "healthy", ..., "storage": { "status": "ready", "type": "s3" | "local_filesystem", ... } }`, và `apiClient.normalizeResponse` (`usfds-web/src/api/client.ts:163-171`) bọc thành `{ success: true, data: { storage: { type: ... } } }`.
  - Tuy nhiên:
    1. `deploy/nginx.conf` (`deploy/nginx.conf:10-19`) chỉ proxy `/api/`, và `deploy/.env` hiện tại của dev có thể thiếu biến hoặc khi container `usfds-server` khởi động chậm/lỗi mạng tạm thời, `storageApi.isS3StorageBackend()` (`usfds-web/src/api/storageApi.ts:25-39`) nuốt lỗi hoặc cache kết quả mà không có cơ chế làm mới, và khi chọn tệp trên trình duyệt (`useDatasetImport.ts:108-110`, `DetectionJobWizardView.tsx:207-212`) lại tự gán đường dẫn giả `../datasets/${selected.name}`.
    2. Trong `useDatasetImport.ts:126-150`, khi chọn file qua `electronAPI.openFileDialog`, state `rawFile` không được reset về `null`. Đồng thời `useDatasetImport.ts:228` vẫn gửi `user_id` hardcode, và `dataset_router.py:136,160` vẫn dùng `req.user_id` thay vì `actor.user_id`.
    3. Các hàm xuất/tải file (`datasetApi.ts:109`, `detectionApi.ts:99`, `insightReportApi.ts:110,131`) chưa đồng nhất:
       - `insightReportApi.exportReport` (`insightReportApi.ts:110`) chặn `params.format !== 'html'` không cho dùng Presigned URL trên S3, dẫn đến gọi `window.open('/api/v1/reports/export?...')` không có `Authorization: Bearer` -> lỗi `401 Unauthorized` khi `USFDS_AUTH_MODE=required`.
       - Ở chế độ `local`, `datasetApi.exportDataset` dùng raw `axios.post('/api/v1/...')` còn `detectionApi.exportResults` & `insightReportApi.exportReport` dùng `window.open`, đều thiếu `Authorization: Bearer` và không đi qua `baseURL` của `apiClient`.

## 2. Goal, scope verdict & non-goals
- **Goal:** (1) Gom toàn bộ kiểm tra/đọc/lưu tệp về duy nhất interface `IFileStorage` (`LocalFileStorage` cho phép đường dẫn cục bộ; `S3FileStorage` chỉ làm việc với S3 object keys — giải quyết `ISS-015`), và (2) đảm bảo Dataset Import cùng các chức năng tương tác file hoạt động chuẩn xác với cả Presigned URL (`s3`) lẫn Electron (`local_filesystem`) (`ISS-036`).
- **Scope:** OK
- **Non-goals / omitted:**
  - Không thêm multipart upload fallback cho Web Browser khi chạy với `USFDS_STORAGE_BACKEND=local` (chấp nhận báo lỗi khi chạy trên trình duyệt web thường ở mode `local`, vì mode `local` dành cho Electron Desktop).
  - Không thay đổi prefix tạm `uploads/` (thuộc `ISS-004`).

## 3. Files
| Action | File | Milestone | Note |
|---|---|---|---|
| modify | `usfds-core/src/usfds_core/storage/base_storage.py` | M1 | bổ sung `save_file(src_path, dest_path)` mặc định vào `IFileStorage` |
| modify | `usfds-core/src/usfds_core/storage/in_memory_storage.py` | M1 | hỗ trợ fallback đọc file cục bộ trong `exists`/`read_bytes`/`get_file_size` khi dùng trong unit tests của `usfds-core` |
| modify | `usfds-infra/src/usfds_infra/storage/local_storage.py` | M1 | ` _resolve_path` xử lý chuẩn cả đường dẫn tuyệt đối, đường dẫn tương đối trên máy cục bộ và đường dẫn trong `base_dir` |
| modify | `usfds-infra/src/usfds_infra/storage/s3_storage.py` | M1 | bỏ nhánh `if local_src.is_file()` trong `save_file` để `S3FileStorage` chỉ thao tác trên S3 object keys (`ISS-015`) |
| modify | `usfds-core/src/usfds_core/services/data_management/ingestion.py` | M1 | xóa nhánh `if is_local:` thủ công; dùng hoàn toàn `self.file_storage.exists()`, `get_file_size()`, `save_file()`, `read_bytes()` |
| modify | `usfds-core/src/usfds_core/services/inference/inference_service.py` | M1 | xóa `local_p.is_file()` trong `_read_bytes` và `_resolve_input_source`; chỉ gọi `self.file_storage` |
| modify | `usfds-core/src/usfds_core/services/inference/executor.py` | M1 | xóa `p.is_file()` trong `_read_bytes` |
| modify | `usfds-core/src/usfds_core/services/training/training_service.py` | M1 | xóa `local_p.is_file()` trong `activate_model_version` và dùng `self.file_storage` trong `register_plugged_model` |
| modify | `usfds-core/src/usfds_core/services/training/executor.py` | M1 | xóa `local_p.is_file()` trong `_read_bytes` |
| modify | `usfds-core/src/usfds_core/services/preprocessing/feature_engineering_service.py` | M1 | xóa `p.is_file()` trong `_load_dataframe`, chỉ đọc qua `self.file_storage.read_bytes` |
| modify | `usfds-core/src/usfds_core/services/preprocessing/leaked_feature_engineering_service.py` | M1 | xóa `p.is_file()` trong `_load_dataframe`, chỉ đọc qua `self.file_storage.read_bytes` |
| modify | `usfds-core/src/usfds_core/services/preprocessing/preprocessing_service.py` | M1 | xóa `p.is_file()` trong `_load_dataframe`, chỉ đọc qua `self.file_storage.read_bytes` |
| modify | `usfds-core/src/usfds_core/services/insight_report/engine.py` | M1 | xóa `local_path.is_file()` trong `_read_parquet_bytes`, chỉ đọc qua `self.file_storage` |
| modify | `usfds-server/src/usfds_server/routers/dataset_router.py` | M1 | lấy `actor.user_id` và `actor.username` thay vì `req.user_id` |
| modify | `usfds-server/src/usfds_server/routers/rule_router.py` | M1 | rút gọn `_load_artifact_dataframe` chỉ dùng `storage.exists` & `storage.read_bytes` |
| modify | `usfds-worker/src/usfds_worker/handlers.py` | M1 | rút gọn `_load_artifact_dataframe` chỉ dùng `storage.exists` & `storage.read_bytes` |
| modify | `usfds-web/src/api/storageApi.ts` | M2 | chuẩn hóa `isS3StorageBackend` & `resolveStoragePath`: nếu có `file` (trình duyệt) và S3 -> presigned upload; nếu có native path (Electron) -> trả native path |
| modify | `usfds-web/src/hooks/useDatasetImport.ts` | M2 | không gán path giả `../datasets/<name>` khi chọn file trên trình duyệt; reset `rawFile` khi chọn qua `electronAPI.openFileDialog`; bỏ `user_id` hardcode |
| modify | `usfds-web/src/components/modules/data_management/ImportDatasetModal.tsx` | M2 | thêm `.pq,.txt` vào `accept` |
| modify | `usfds-web/src/components/modules/detection/DetectionJobWizardView.tsx` | M2 | đồng bộ chọn file với `useDatasetImport` (không gán path giả khi không có `electronAPI`, cho phép `canProceedFromSource` khi có `selectedRawFile` hoặc `inputFilePath`) |
| modify | `usfds-web/src/api/datasetApi.ts` | M2 | dùng `apiClient.getRawAxios()` khi tải blob ở local mode |
| modify | `usfds-web/src/api/detectionApi.ts` | M2 | dùng presigned download khi `s3`, và dùng `apiClient.getRawAxios()` tải blob khi `local` |
| modify | `usfds-web/src/api/insightReportApi.ts` | M2 | cho phép presigned download với mọi format (kể cả `html`) khi `s3`, và dùng `apiClient.getRawAxios()` tải blob khi `local` |
| modify | `usfds-server/tests/test_dataset_api.py` | M1 | thêm acceptance tests cho presigned S3 import và chặn đọc local path trên S3 (`ISS-015`) |
| modify | `usfds-web/src/components/modules/data_management/DatasetHubView.test.tsx` | M2 | thêm acceptance tests cho Dataset Import (S3 presigned vs Electron local) và Exports |

## 4. Dependencies & conflicts (with other tasks on BOARD)
| # | Check | Answer |
|---|---|---|
| D1 | Needs unfinished task? | No |
| D2 | Needed by unfinished task? | No |
| C1 | Modified files owned by in-progress task? | No |
| C2 | Hot-spot files touched | — |
| C3 | Schema change | No |
| C4 | Public contract change | No |
| C5 | Shared UI shell change | No |

## 5. Acceptance tests (user reviews this section)
| Milestone | Test | Given | When | Then | Covers |
|---|---|---|---|---|---|
| M1 | `test_dataset_import_uses_presigned_upload_when_storage_is_s3` (`usfds-web/src/components/modules/data_management/DatasetHubView.test.tsx`) | `GET /api/health` trả `storage.type = 's3'`, người dùng chọn file `tx.csv` trong `ImportDatasetModal` và submit | Bấm nút "Tiếp tục" | Gọi `POST /api/v1/storage/presigned-upload` -> `PUT` lên `upload_url` -> `POST /api/v1/datasets/import` với `file_path = object_key` | ISS-036 |
| M1 | `test_dataset_import_uses_native_path_in_electron_local_mode` (`usfds-web/src/components/modules/data_management/DatasetHubView.test.tsx`) | `GET /api/health` trả `storage.type = 'local_filesystem'` và `window.electronAPI.getPathForFile` trả `/Users/alice/tx.csv` | Chọn file `tx.csv` và submit | Không gọi `/v1/storage/presigned-upload`; gọi thẳng `POST /api/v1/datasets/import` với `file_path = '/Users/alice/tx.csv'` | ISS-036 |
| M1 | `test_exports_use_presigned_url_on_s3_and_authenticated_axios_on_local` (`usfds-web/src/components/modules/data_management/DatasetHubView.test.tsx`) | Lần lượt ở mode `s3` và `local_filesystem` | Gọi `datasetApi.exportDataset`, `detectionApi.exportResults`, `insightReportApi.exportReport` (bao gồm `format: 'html'`) | Ở `s3`: gọi kèm `presigned=true` và tải qua `download_url`; ở `local_filesystem`: tải blob qua `apiClient.getRawAxios()` (có Bearer token) | ISS-036 |
| M2 | `test_import_dataset_from_presigned_s3_staging_key_copies_and_cleans_staging` (`usfds-server/tests/test_dataset_api.py`) | Backend cấu hình `S3FileStorage` (moto), client gọi `POST /api/v1/storage/presigned-upload` (`purpose="dataset_raw"`), upload CSV vào `object_key` (`uploads/dataset_raw/...`) | Gọi `POST /api/v1/datasets/import` với `file_path=object_key` | Trả `201 Created`, artifact `RAW` nằm tại `datasets/{dataset_id}/raw/...`, key tạm `uploads/...` đã bị xóa, `dataset.user_id == actor.user_id` | ISS-036 |
| M2 | `test_s3_storage_mode_rejects_server_local_filesystem_paths` (`usfds-server/tests/test_dataset_api.py`) | Backend cấu hình `S3FileStorage` (moto), có file `/tmp/.../secret.csv` tồn tại trên filesystem của server nhưng không có trên S3 | Client gọi `POST /api/v1/datasets/import` và `POST /api/v1/detection/jobs` với `file_path` trỏ tới file cục bộ đó | Cả hai trả `404 Not Found` (`FileNotFoundError`), không đọc file cục bộ của server | ISS-015 |
| M2 | `test_local_storage_mode_imports_from_external_local_filesystem_path` (`usfds-server/tests/test_dataset_api.py`) | Backend cấu hình `LocalFileStorage` (Electron/Desktop mode) và có file CSV nằm ngoài `storage_dir` trên máy cục bộ | Gọi `POST /api/v1/datasets/import` với đường dẫn tuyệt đối của file đó | `LocalFileStorage.exists()` / `save_file()` nhận diện được file cục bộ, trả `201 Created` | ISS-015, ISS-036 |

## 6. Milestones & to-do (checkpoints, not stop points: all tests green at each)
The agent ticks items as it works. This is the task's only to-do list (`TODO.md` is no longer used for new work).

- [x] **M1 — Frontend Presigned Upload & Export ở cả S3 và Electron Local mode (`ISS-036`)** (`usfds-web`) — *Dừng sau M1 để user test & duyệt*:
  - [x] [tests] Viết 3 acceptance tests M1 trong `usfds-web/src/components/modules/data_management/DatasetHubView.test.tsx`; xác nhận fail đúng lý do
  - [x] [web] Cập nhật `storageApi.ts`, `useDatasetImport.ts`, `ImportDatasetModal.tsx`, `DetectionJobWizardView.tsx`
  - [x] [web] Cập nhật `datasetApi.ts`, `detectionApi.ts`, `insightReportApi.ts`
  - [x] [verify] `./scripts/test.sh web` + `npm run build` + `npm run lint`
- [x] **M2 — Chuẩn hóa toàn bộ File I/O qua `IFileStorage` (`ISS-015`, `ISS-036`)** (`usfds-core`, `usfds-infra`, `usfds-server`, `usfds-worker`):
  - [x] [tests] Viết 3 acceptance tests M2 trong `usfds-server/tests/test_dataset_api.py`; xác nhận fail đúng lý do
  - [x] [core] Đưa `save_file` mặc định vào `IFileStorage`; gom toàn bộ đọc/kiểm tra file trong `ingestion.py`, `inference_service.py`, `inference/executor.py`, `training_service.py`, `training/executor.py`, `feature_engineering_service.py`, `leaked_feature_engineering_service.py`, `preprocessing_service.py`, `insight_report/engine.py` về `self.file_storage` (xóa các nhánh `if Path(...).is_file()`)
  - [x] [infra] Đảm bảo `LocalFileStorage._resolve_path` hỗ trợ đường dẫn cục bộ ngoài `base_dir` (cho Electron), và xóa nhánh `if local_src.is_file()` trong `S3FileStorage.save_file`
  - [x] [server] Rút gọn `rule_router._load_artifact_dataframe` chỉ gọi `storage.read_bytes`; cập nhật `dataset_router.import_dataset` dùng `actor.user_id`/`actor.username`
  - [x] [worker] Rút gọn `usfds_worker.handlers._load_artifact_dataframe` chỉ gọi `storage.read_bytes`
  - [x] [verify] `./scripts/test.sh core infra server worker`

Checkpoint log (the agent appends one line per finished milestone):
- `2026-11-15 M1`: Completed `usfds-web` presigned upload & authenticated export updates (`storageApi.ts`, `useDatasetImport.ts`, `ImportDatasetModal.tsx`, `DetectionJobWizardView.tsx`, `datasetApi.ts`, `detectionApi.ts`, `insightReportApi.ts`); verified `./scripts/test.sh web` (12 files / 23 tests PASS), `npm run build` (PASS), `npm run lint` (0 errors). Paused for user testing before M2.
- `2026-11-15 M2`: Completed `IFileStorage` consolidation (`ISS-015`) & actor attribution across `usfds-core`, `usfds-infra`, `usfds-server`, `usfds-worker`; verified full `./scripts/test.sh` (core, infra, server, worker, cli, web ALL PASS).

## 7. Review hotspots (filled in after implementation)
- **Storage boundary (`ISS-015`):**
  - `usfds-infra/src/usfds_infra/storage/s3_storage.py#L138-L154` (`S3FileStorage.save_file`: bỏ nhánh đọc file cục bộ `local_src.is_file()`, chỉ thao tác S3 key).
  - `usfds-infra/src/usfds_infra/storage/local_storage.py#L15-L29` (`LocalFileStorage._resolve_path`: hỗ trợ đường dẫn tuyệt đối của Electron và fallback file cục bộ tương đối).
  - `usfds-core/src/usfds_core/services/data_management/ingestion.py#L88-L156` & `usfds-core/src/usfds_core/services/inference/inference_service.py#L580-L625` (toàn bộ kiểm tra/đọc file đi qua `self.file_storage`, tự xóa staging key `uploads/`/`staging/` sau khi copy).
- **Auth & Attribution:**
  - `usfds-server/src/usfds_server/routers/dataset_router.py#L135-L165` (`import_dataset` dùng `actor.user_id` & `actor.username` thay `req.user_id`).
- **Frontend Presigned Upload & Authenticated Exports (`ISS-036`):**
  - `usfds-web/src/api/storageApi.ts#L92-L135` (`resolveStoragePath`, `triggerBlobDownload`).
  - `usfds-web/src/hooks/useDatasetImport.ts#L107-L237` & `usfds-web/src/components/modules/detection/DetectionJobWizardView.tsx#L207-L297`.
  - `usfds-web/src/api/insightReportApi.ts#L100-L145` (cho phép presigned download với mọi định dạng kể cả `html`, fallback `apiClient.getRawAxios()` ở mode `local`).

## 8. Open questions
- — (Đã chốt: gom toàn bộ kiểm tra/đọc file về `IFileStorage` để bỏ `if-else` rải rác và chặn đọc file cục bộ khi dùng `S3FileStorage`).
