# Plan: Client-Server Storage Interaction via Presigned URLs (Zero Business Logic Change)

## 1. Context & Architectural Principle
- **Core Principle**: Keep `usfds-core` business logic 100% storage-agnostic through `IFileStorage`. Switching between Standalone (`LocalFileStorage`) and Client-Server (`S3FileStorage`) must not alter domain/service workflows.
- **Root Cause Identified**:
	- `TrainingOrchestrationService.register_plugged_model`, `InferenceService._resolve_input_source`, `DataMappingService`, `FeatureEngineeringExecutionService`, `TrainingRunExecutor`, `BatchInferenceExecutor`, and `DatasetExportService` **already** resolve files via `self.file_storage.exists()` and `self.file_storage.read_bytes()`.
	- Only **one place** in `usfds-core` leaked local filesystem assumptions: `DatasetIngestionService.import_dataset` (`usfds-core/src/usfds_core/services/data_management/ingestion.py`), which called `Path(file_path).resolve().is_file()` and `src_path.stat().st_size` directly instead of checking `self.file_storage`.
	- Additionally, `S3FileStorage.save_file(src_path, dest_path)` assumed `src_path` is always a local OS path rather than an existing S3 object key uploaded via Presigned URL.

---

## 2. Minimal Scope of Changes

### Phase 1: Fix Local Path Leak in `DatasetIngestionService` (`usfds-core`)
1. **`usfds-core/src/usfds_core/services/data_management/ingestion.py`**:
	- In `import_dataset(file_path, ...)`:
		- Resolve file existence & size via local OS path (`src_path.is_file()`) **OR** `self.file_storage.exists(str(file_path))` + `self.file_storage.get_file_size(str(file_path))` (matching the exact pattern already used in `InferenceService._resolve_input_source` and `TrainingOrchestrationService.register_plugged_model`).
		- Delegate copying to `self.file_storage.save_file(file_path, storage_dest)` (or `save_bytes`).

### Phase 2: Extend `S3FileStorage` with Presigned URLs & Server-Side Copy (`usfds-infra`)
1. **`usfds-infra/src/usfds_infra/storage/s3_storage.py`**:
	- Add `public_endpoint_url: Optional[str] = None` to `S3FileStorage.__init__` so `s3v4` Presigned URLs are signed with the browser-facing host (`USFDS_S3_PUBLIC_ENDPOINT_URL`, e.g. `http://localhost:9000`) while internal Server/Worker calls use `endpoint_url` (`http://rustfs:9000`).
	- Update `S3FileStorage.save_file(src_path, dest_path)`:
		- If `Path(src_path).is_file()` exists on local disk $\rightarrow$ `upload_file` to S3.
		- Else if `self.exists(str(src_path))` on S3 $\rightarrow$ server-side `copy_object` from `src_key` to `dest_key` (no download/re-upload across the network).
	- Add `generate_presigned_upload_url(file_path, content_type, expires_in=900) -> str` (`put_object`).
	- Add `generate_presigned_download_url(file_path, filename, expires_in=900) -> str` (`get_object` with `ResponseContentDisposition`).
	- Configure bucket CORS (`GET`, `PUT`, `HEAD`) in `ensure_bucket()` so browser direct uploads/downloads succeed.

### Phase 3: Thin Presigned URL Endpoints in `usfds-server` (`usfds-server` & `deploy/`)
1. **`usfds-server/src/usfds_server/config.py`, `dependencies.py`, `deploy/`**:
	- Add `USFDS_S3_PUBLIC_ENDPOINT_URL` to `Settings`, `deploy/docker-compose.yml`, and `deploy/.env.example`.
2. **New `usfds-server/src/usfds_server/routers/storage_router.py` (`/api/v1/storage`)**:
	- `POST /api/v1/storage/presigned-upload`: Accepts `{ filename, purpose, project_id, content_type }`, generates an object key `uploads/{project_id or 'global'}/{uuid4()}/{filename}`, and returns `{ upload_url, object_key, expires_in }` from `S3FileStorage.generate_presigned_upload_url`.
	- `GET /api/v1/storage/presigned-download`: Accepts `object_key` and optional `filename`, returns `{ download_url, filename, expires_in }` from `S3FileStorage.generate_presigned_download_url`.
3. **Export Endpoints (`dataset_router.py`, `detection_router.py`, `insight_report_router.py`)**:
	- Add optional `presigned: bool = Query(False)`: when `True` and `storage` is `S3FileStorage`, save the exported file to `exports/...` on S3 (or reuse `job.output_path` directly for unfiltered Parquet detection results) and return `ApiResponse.ok({ "download_url": presigned_url, "filename": filename })`.

### Phase 4: Frontend Pre-Upload / Download Integration (`usfds-web`)
1. **New `usfds-web/src/api/storageApi.ts`**:
	- `resolveStoragePath(file: File, nativePath: string, purpose, projectId): Promise<string>`:
		- In Standalone mode (`storage.type === 'local_filesystem'` and `nativePath` present): returns `nativePath` immediately.
		- In Client-Server mode (`storage.type === 's3'` or browser without native path): calls `POST /api/v1/storage/presigned-upload` $\rightarrow$ `PUT`s `file` directly to S3 $\rightarrow$ returns `object_key`.
2. **Wire into the 3 Upload & 3 Export UI Callers**:
	- Upload callers (`useDatasetImport.ts`, `DetectionJobWizardView.tsx`, `ImportCustomModelModal.tsx`) call `storageApi.resolveStoragePath(...)` and pass the resulting `object_key` into the existing `file_path` / `input_file_path` / `model_artifact_path` fields without changing any API payload contracts.
	- Export callers (`datasetApi.ts`, `detectionApi.ts`, `insightReportApi.ts`) use `presigned=true` when `storage.type === 's3'` to download directly via the S3 Presigned GET URL.

---

## 3. Verifiable Success Criteria
- [ ] Zero changes to core business/pipeline logic; only `DatasetIngestionService.import_dataset` is updated to check `self.file_storage.exists()` alongside `Path.is_file()`.
- [ ] `S3FileStorage` supports `save_file` from existing S3 keys (`copy_object`), `generate_presigned_upload_url`, `generate_presigned_download_url` with `public_endpoint_url`, and bucket CORS.
- [ ] `/api/v1/storage/presigned-upload`, `/api/v1/storage/presigned-download`, and `?presigned=true` on exports pass unit & API tests in `usfds-core`, `usfds-infra`, and `usfds-server`.
- [ ] `usfds-web` builds cleanly (`npm run build`) and transparently switches between local native path (Standalone) and Presigned URLs (Client-Server).
