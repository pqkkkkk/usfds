# Kế hoạch Thiết kế & Cài đặt `usfds-worker` (Tái sử dụng Trực tiếp `usfds-core`)

## 1. Nguyên lý Cốt lõi (Zero File-Logic Duplication)

- **Tương tác File/S3 đã được trừu tượng hóa qua [`IFileStorage`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-core/src/usfds_core/storage/base_storage.py)**:
	- [`DataMappingService`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-core/src/usfds_core/services/data_management/mapping.py#L41-L44), [`FeatureEngineeringExecutionService`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-core/src/usfds_core/services/preprocessing/feature_engineering_service.py#L124-L284), [`TrainingRunExecutor`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-core/src/usfds_core/services/training/executor.py#L37-L43), [`TrainingOrchestrationService.register_plugged_model`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-core/src/usfds_core/services/training/training_service.py#L270-L271), [`BatchInferenceExecutor`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-core/src/usfds_core/services/inference/executor.py#L316) và [`InferenceService._resolve_input_source`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-core/src/usfds_core/services/inference/inference_service.py#L588-L589) **đều đã đọc/ghi file qua `self.file_storage` (`S3FileStorage`)**.
	- Điểm duy nhất còn kiểm tra `Path.is_file()` cục bộ là [`DatasetIngestionService.import_dataset`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-core/src/usfds_core/services/data_management/ingestion.py#L88-L98) — đã được lên kế hoạch sửa trong [`.plan/client_server_storage_presigned_url.md`](file:///d:/Thesis/4.%20Implementation/usfds/.plan/client_server_storage_presigned_url.md).
- **Hệ quả**:
	- Tại [`usfds-worker`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-worker/src/usfds_worker/handlers.py), mỗi handler **chỉ cần import trực tiếp Service/Executor tương ứng từ `usfds-core`**, khởi tạo với `ctx.storage` ([`S3FileStorage`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-infra/src/usfds_infra/storage/s3_storage.py)) + `session` (PostgreSQL) và gọi hàm nghiệp vụ có sẵn.
	- **Không sửa đổi bất kỳ logic đọc/ghi file hay thuật toán nào trong `usfds-core`.**

---

## 2. Danh sách Hàng đợi & Ánh xạ Trực tiếp sang Hàm của `usfds-core`

| Queue (BullMQ PG) | Job Name | Hàm `usfds-core` được gọi trực tiếp tại `usfds-worker` |
| --- | --- | --- |
| `usfds-training` | `training_run` | [`TrainingRunExecutor(file_storage=ctx.storage, ...).run(payload)`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-core/src/usfds_core/services/training/executor.py#L71) *(đã có)* |
| `usfds-training` | `plugin_dry_run` | [`TrainingOrchestrationService(..., file_storage=ctx.storage).register_plugged_model(...)`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-core/src/usfds_core/services/training/training_service.py#L249) |
| `usfds-batch-inference` | `batch_inference` | [`BatchInferenceExecutor(file_storage=ctx.storage, ...).run(payload)`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-core/src/usfds_core/services/inference/executor.py#L316) *(đã có)* |
| `usfds-batch-inference` | `rule_backtest` | [`RuleExecutor().backtest_dataframe(...)`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-core/src/usfds_core/services/rule_engine/executor.py) |
| `usfds-data-pipeline` | `dataset_ingestion` | [`DataManagementService(..., file_storage=ctx.storage).import_dataset(...)`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-core/src/usfds_core/services/data_management/service.py#L158) |
| `usfds-data-pipeline` | `schema_mapping` | [`DataManagementService(..., file_storage=ctx.storage).map_schema(...)`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-core/src/usfds_core/services/data_management/service.py#L187) |
| `usfds-data-pipeline` | `feature_engineering` | [`DataManagementService(..., file_storage=ctx.storage).execute_feature_engineering(...)`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-core/src/usfds_core/services/data_management/service.py#L211) |

---

## 3. Các Thay đổi Tối thiểu Cần Thực hiện

### Phase 1: `usfds-infra` — Mở rộng `BullMQJobQueue` (`bullmq_queue.py`)
1. **[`usfds-infra/src/usfds_infra/job_queue/bullmq_queue.py`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-infra/src/usfds_infra/job_queue/bullmq_queue.py)**:
	- Khai báo thêm hằng số queue `QUEUE_DATA_PIPELINE = "usfds-data-pipeline"` và tên các job:
		- `JOB_PLUGIN_DRY_RUN = "plugin_dry_run"`
		- `JOB_RULE_BACKTEST = "rule_backtest"`
		- `JOB_DATASET_INGESTION = "dataset_ingestion"`
		- `JOB_SCHEMA_MAPPING = "schema_mapping"`
		- `JOB_FEATURE_ENGINEERING = "feature_engineering"`
	- Thêm phương thức `enqueue_and_wait(queue_name, job_name, data, timeout_s=300) -> Any`:
		- Đẩy job vào BullMQ và chờ Worker xử lý xong (kiểm tra trạng thái job trong PostgreSQL mỗi `300ms`), trả về `returnvalue` của handler hoặc ném `ValueError(failedReason)` nếu job thất bại.

### Phase 2: `usfds-worker` — Import & Gọi Trực tiếp `usfds-core` (`handlers.py` & `main.py`)
1. **[`usfds-worker/src/usfds_worker/handlers.py`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-worker/src/usfds_worker/handlers.py)**:
	- Helper `_make_data_service(session, storage) -> DataManagementService`.
	- `handle_dataset_ingestion(ctx, data) -> dict`: gọi `service.import_dataset(...)`, `session.commit()`, trả về `{"dataset_id": str(ds.dataset_id), "artifact_id": str(art.artifact_id)}`.
	- `handle_schema_mapping(ctx, data) -> dict`: gọi `service.map_schema(...)`, `session.commit()`, trả về `{"artifact_id": str(art.artifact_id)}`.
	- `handle_feature_engineering(ctx, data) -> dict`: gọi `service.execute_feature_engineering(...)`, `session.commit()`, trả về `{"artifact_id": str(art.artifact_id)}`.
	- `handle_plugin_dry_run(ctx, data) -> dict`: gọi `TrainingOrchestrationService(..., file_storage=ctx.storage).register_plugged_model(...)`, `session.commit()`, trả về `{"model_id": str(model.model_id)}`.
	- `handle_rule_backtest(ctx, data) -> dict`: đọc DataFrame từ `ctx.storage`, gọi `RuleExecutor().backtest_dataframe(...)`, trả về `asdict(bt_result)`.
2. **[`usfds-worker/src/usfds_worker/main.py`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-worker/src/usfds_worker/main.py)**:
	- Đăng ký 3 `Worker` cho `QUEUE_TRAINING`, `QUEUE_BATCH_INFERENCE`, `QUEUE_DATA_PIPELINE`, định tuyến theo `job.name` tới từng hàm `handle_*` tương ứng.

### Phase 3: `usfds-server` & `usfds-web` — Điều phối qua Queue & Auto-Polling
1. **Tại `usfds-server` ([`dataset_router.py`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-server/src/usfds_server/routers/dataset_router.py), [`training_router.py`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-server/src/usfds_server/routers/training_router.py), [`rule_router.py`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-server/src/usfds_server/routers/rule_router.py))**:
	- Khi `settings.dispatch_backend == "queue"`, đẩy job tương ứng qua `get_job_queue().enqueue_and_wait(...)` để Worker thực thi, sau đó đọc thực thể kết quả từ DB và trả về đúng schema response hiện tại.
	- Khi `settings.dispatch_backend == "local"`, giữ nguyên lời gọi trực tiếp như hiện tại.
2. **Tại `usfds-web` ([`TrainingRunDetailView.tsx`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-web/src/components/modules/model/TrainingRunDetailView.tsx), [`ModelHubView.tsx`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-web/src/components/modules/model/ModelHubView.tsx), [`DetectionResultExplorerView.tsx`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-web/src/components/modules/detection/DetectionResultExplorerView.tsx), [`DetectionJobsHubView.tsx`](file:///d:/Thesis/4.%20Implementation/usfds/usfds-web/src/components/modules/detection/DetectionJobsHubView.tsx))**:
	- Thêm auto-polling (`2.5s`) khi `TrainingRun.status` hoặc `DetectionJob.status` đang là `PENDING` hoặc `RUNNING`.

---

## 4. Tiêu chí Nghiệm thu (Verifiable Success Criteria)
- [ ] **Zero business/file logic changes** trong `usfds-core` (ngoài bản vá `DatasetIngestionService.import_dataset` trong [`.plan/client_server_storage_presigned_url.md`](file:///d:/Thesis/4.%20Implementation/usfds/.plan/client_server_storage_presigned_url.md)).
- [ ] `usfds-worker` chỉ import và gọi trực tiếp các service/executor của `usfds-core` với `S3FileStorage`.
- [ ] Unit tests trong `usfds-worker/tests/test_handlers.py` và `usfds-infra/tests/` kiểm tra toàn bộ 7 handlers hoạt động đúng.
- [ ] `usfds-web` tự động poll cập nhật kết quả khi `TrainingRun` / `DetectionJob` chạy nền trên Worker.
