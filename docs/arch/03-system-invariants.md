# 03 — System Invariants & Guardrail Matrix
<!-- [26-11-27] Created: Canonical catalog of technical & business invariants (INV-001..015) and 3-tier enforcement strategy. -->

Tài liệu này định nghĩa **15 bất biến hệ thống (`INV-001` đến `INV-015`)** — tập hợp các quy tắc kỹ thuật và quy tắc nghiệp vụ cốt lõi mà mọi thay đổi mới **không được phép phá vỡ**.

Mỗi bất biến được gán vào **1 trong 3 tầng thực thi**:
- **Tầng 1 (Static / Structural Guard):** Test tự động trong `./scripts/test.sh` quét toàn bộ app/AST/schema — chặn lỗi ngay cả khi tác giả quên viết unit test cho tính năng mới.
- **Tầng 2 (Contract / Property Test):** Test tích hợp xuyên module hoặc kiểm tra bất biến toán học/vòng đời trên dữ liệu mẫu.
- **Tầng 3 (Plan Checklist + `usfds-review`):** Kiểm duyệt ngữ nghĩa ở bước lên kế hoạch và phản biện độc lập trước khi trình duyệt.

---

## Nhóm A — Bảo mật, Phân quyền & Cô lập dữ liệu (Security & Multi-Tenancy)

### `INV-001` — Authenticated-by-Default API & Safe CORS
- **Quy tắc:** Mọi FastAPI route không nằm trong `PUBLIC_ALLOWLIST` (`/health`, `/api/health`, `/api/v1/auth/{mode,login,refresh,logout}`) bắt buộc phải qua dependency xác thực (`get_actor_context` / `get_current_user` / `require_system_permission`). Khi `USFDS_CORS_ORIGINS` chứa `*`, `allow_credentials` bắt buộc là `False` (`ISS-014`).
- **Thực thi:** **Tầng 1 (ĐÃ KHÓA)** — [`test_route_security_guard.py`](../../usfds-server/tests/test_route_security_guard.py) + [`test_auth_and_rbac_api.py`](../../usfds-server/tests/test_auth_and_rbac_api.py).

### `INV-002` — Cô lập Project & Chống dò ID (Anti-404-Oracle)
- **Quy tắc:**
  - Mọi truy vấn tài nguyên thuộc project (`dataset`, `feature`, `rule`, `training`, `detection`, `case`, `network`, `report`, `storage`) phải xác thực quyền truy cập `project_id` **trước khi** tiết lộ sự tồn tại của bản ghi; truy cập chéo project trả `404` hoặc `403`, không bao giờ rò rỉ dữ liệu project khác (`ISS-042`).
  - `GET /api/v1/storage/presigned-download` chỉ ký URL sau khi kiểm tra anti-path-traversal, prefix hợp lệ và quyền sở hữu/project của key.
- **Thực thi:** **Tầng 1 (ĐÃ KHÓA)** ([`test_route_security_guard.py`](../../usfds-server/tests/test_route_security_guard.py)) + **Tầng 2** ([`test_auth_and_rbac_api.py`](../../usfds-server/tests/test_auth_and_rbac_api.py)).

### `INV-003` — RBAC 3 phạm vi (`OWN < PROJECT < SYSTEM`), Cô lập nhánh & Chống leo thang quyền
- **Quy tắc:**
  - `GrantScope.OWN` chỉ cho phép đọc/sửa/xóa bản ghi có `user_id == actor.user_id`; list query dưới quyền `OWN` bắt buộc lọc `owner_id = actor.user_id` (`ISS-043`).
  - `SYSTEM_ONLY_PERMISSIONS` không bao giờ được gán cho vai trò `RoleScope.PROJECT`; non-`system_admin` không được gán quyền rộng hơn quyền mình đang giữ; không được xóa/hạ cấp `project_admin` cuối cùng của một project.
- **Thực thi:** **Tầng 2** (`test_auth_and_rbac_api.py`, `test_authz_enforcement.py`, `test_authz_management.py`) + **Tầng 3** (`usfds-review` cho mọi router/endpoint mới).

### `INV-004` — Biên an toàn File I/O & Sandbox mã người dùng
- **Quy tắc:**
  - Ở chế độ S3, server không bao giờ đọc đường dẫn filesystem cục bộ do client gửi lên (`ISS-015`). Upload plugin có giới hạn dung lượng (`USFDS_MAX_PLUGIN_UPLOAD_MB`) và không chặn event loop (`ISS-016`, `ISS-019`).
  - Mã tùy chỉnh (`SCRIPT` model plugins & `PYTHON_CODE` features) bắt buộc qua AST validator (chặn import/builtin nguy hiểm) và chạy trong subprocess có timeout (`ISS-022`).
  - Remote compute (Modal) chỉ nhận `PresignedUrlStorage` có TTL giới hạn — **tuyệt đối không** truyền S3/DB credentials vào container từ xa.
- **Thực thi:** **Tầng 2** (`test_feature_management.py`, `test_modal_provider.py`, `test_s3_storage.py`) + **Tầng 3** (`usfds-review`).

---

## Nhóm B — Kiến trúc phân lớp, Dữ liệu bền vững & Hiệu năng

### `INV-005` — Ranh giới Clean Architecture & Worker Không Chạm DB
- **Quy tắc:**
  - `usfds-core` không được import `usfds_infra`, `usfds_server`, `usfds_worker`, `sqlalchemy`, `fastapi`, `boto3`, `bullmq`, hay `modal`.
  - `TrainingRunExecutor` và `BatchInferenceExecutor` không nhận SQLAlchemy session hay truy cập DB trực tiếp — chỉ giao tiếp qua DTO payload, `IFileStorage`, và notifier/result.
  - FastAPI routers không import trực tiếp ORM table/model từ `usfds_infra.database.{models,tables,case_models}`.
- **Thực thi:** **Tầng 1 (ĐÃ KHÓA)** — [`test_architecture_guards.py`](../../usfds-core/tests/test_architecture_guards.py) + [`test_route_security_guard.py`](../../usfds-server/tests/test_route_security_guard.py).

### `INV-006` — Tương thích PostgreSQL & Schema Migration duy nhất
- **Quy tắc:**
  - Mọi câu truy vấn SQL/ORM và DDL bắt buộc tương thích PostgreSQL dù test chạy trên SQLite (`ISS-018`).
  - Mọi thay đổi bảng/cột chỉ đi qua Alembic migration, luôn có **đúng 1 head**, `schema_drift == []`, và render được SQL offline cho PostgreSQL (`ISS-020`).
- **Thực thi:** **Tầng 1 (ĐÃ KHÓA)** — [`test_pg_compat_guard.py`](../../usfds-infra/tests/test_pg_compat_guard.py) + [`test_migrations.py`](../../usfds-infra/tests/test_migrations.py).

### `INV-007` — Xử lý dữ liệu lớn có giới hạn RAM (Bounded DuckDB)
- **Quy tắc:** Các luồng đọc dữ liệu lớn trong API/Worker (`Ingestion`, `DataMapping`, `PredictionResults`, `ProjectWarehouse`, `InsightReport`, `BehaviorProfile`, `NetworkGraph`) phải dùng DuckDB có giới hạn tài nguyên (`create_bounded_duckdb_connection`: 2 threads, 512MB RAM, spill temp dir) — **không** gọi `pd.read_csv`/`pd.read_parquet` tải toàn bộ file lên RAM trong tiến trình API (`ISS-012`, `ISS-044`).
- **Thực thi:** **Tầng 1 (ĐÃ KHÓA)** — [`test_architecture_guards.py`](../../usfds-core/tests/test_architecture_guards.py) (`test_large_data_modules_do_not_call_pandas_full_file_readers`) + **Tầng 3** (`usfds-review`).

### `INV-008` — An toàn hàng đợi, Idempotency & Không giữ DB session qua Network I/O
- **Quy tắc:**
  - Handler CPU-bound trên `usfds-worker` chạy qua `asyncio.to_thread` để event loop duy trì BullMQ lock; job fire-and-forget (`training_run`, `batch_inference`) bỏ qua ngay nếu trạng thái DB đã terminal.
  - Danh mục `JOB_*` và `QUEUE_*` trong `usfds-infra`, `usfds-worker`, và `InlineJobQueue` luôn đồng bộ 1-1; lỗi đầu vào/nghiệp vụ xác định bọc trong `UnrecoverableError` (không retry vô ích, `ISS-021`).
  - Các poller nền (như `RemoteTrainingPoller`) tách 3 pha *đọc DB → gọi network (không giữ session) → ghi DB*.
- **Thực thi:** **Tầng 1 (ĐÃ KHÓA)** ([`test_worker_guards.py`](../../usfds-worker/tests/test_worker_guards.py)) + **Tầng 2** (`test_queue_mode_api.py`, `test_queue_timeout_api.py`, `test_remote_poller.py`) + **Tầng 3**.

---

## Nhóm C — Toàn vẹn dữ liệu & Vòng đời tài nguyên

### `INV-009` — Chuẩn bị dữ liệu 2 tầng & Chống Data Leakage
- **Quy tắc:**
  - Artifact ở giai đoạn `FEATURE_ENGINEERED` bắt buộc bảo lưu `event_id`, `user_id`, `timestamp` (`BR-DM-07`, `critical_changes.md`).
  - Chia tập Train/Test theo thời gian diễn ra **trước** khi fit cleanser, target-rate encoder hoặc scaler; không bao giờ fit trên tập test.
  - Mọi cột có `ml_role != FEATURE` (theo `SystemColumnMetadata` snapshot của artifact) phải bị loại nhất quán khỏi vector đặc trưng ở cả Preprocessing, Training và Inference.
- **Thực thi:** **Tầng 2** ([`test_architecture_guards.py`](../../usfds-core/tests/test_architecture_guards.py), `test_feature_engineering_service.py`) + **Tầng 3** (`usfds-review`).

### `INV-010` — Một nguồn sự thật cho Chuẩn hóa cột & Nhãn (No Silent Corruption)
- **Quy tắc:**
  - Tra cứu tên cột hệ thống (`event_id`, `timestamp`, `amount`, `user_id`, `label`, entity columns) dùng chung `resolve_canonical_column()` (`ISS-027`).
  - Chuẩn hóa nhãn nhị phân `0/1` không được âm thầm ép nhãn không nhận diện được về `0` hay `-1` mà vẫn báo `PASSED` (`ISS-047`); phải fail-fast hoặc dùng bộ chuẩn hóa dùng chung xuyên suốt Mapping → Warehouse → Rule Backtest → Training.
- **Thực thi:** **Tầng 2** (`test_system_metadata.py`, `test_mapping_service.py`, `test_project_warehouse.py`, `test_rule_engine.py`) + **Tầng 3** (`usfds-review`).

### `INV-011` — Bảo vệ vòng đời xóa & Không để lại rác lưu trữ (Zero-Orphan)
- **Quy tắc:**
  - Không cho phép xóa tài nguyên đang được sử dụng (`dataset` đang có job active → `409`; `feature` có dependent / thuộc `FeatureSet` / đang dùng bởi `ACTIVE` rule → `400`; `CORE` metadata → `400`; `project` còn job active → `400`; `rule` đang active/in-use → *`ISS-002`*).
  - Xóa bản ghi DB sở hữu file (ví dụ `delete_dataset`) bắt buộc dọn file artifact tương ứng trên `IFileStorage` (`ISS-017`). Khóa ngoại `user_id` dùng `ON DELETE RESTRICT` (`ISS-023`).
- **Thực thi:** **Tầng 2** (`test_dataset_api.py`, `test_feature_api.py`, `test_migrations.py`) + **Tầng 3** (`usfds-review`).

### `INV-012` — Đồng thời lạc quan & Lịch sử bất biến
- **Quy tắc:**
  - Cập nhật `Case` bắt buộc kiểm tra `expected_version` (optimistic locking → `CaseConflictError`).
  - Sửa `condition` hoặc `action` của `Rule` luôn sinh `RuleVersion` mới bất biến; `ModelVersion` đánh số `v1, v2, ...` duy nhất trong `(project_id, model_id)` (có unique constraint + retry). `AuditLog` chỉ ghi thêm (append-only).
- **Thực thi:** **Tầng 2** (`test_case_repositories.py`, `test_model_version_uniqueness.py`, `test_rule_api.py`).

---

## Nhóm D — Ngữ nghĩa nghiệp vụ FDS, Frontend & Đồng bộ tài liệu

### `INV-013` — Chuẩn xác quyết định lai & Bất biến công thức phân tích
- **Quy tắc:**
  - Quyết định lai tuân thủ `BR-DT-07`: `Rule REJECT > Rule REVIEW | (score >= threshold) > ALLOW`.
  - Mọi chỉ số phân tích FDS trong `InsightReport` phải giữ bất biến toán học (funnel 4 tầng đơn điệu giảm `Stage1 >= Stage2 >= Stage3 >= Stage4`; các tỷ lệ nằm trong `[0, 1]`; không trộn `VERIFIED` với `PENDING` trong công thức sai lệch như `ISS-046`; không phát sinh `NaN`/`Infinity` trong payload JSON).
- **Thực thi:** **Tầng 2** ([`test_architecture_guards.py`](../../usfds-core/tests/test_architecture_guards.py) cho `BR-DT-07`, `test_insight_report_service.py`) + **Tầng 3** (`usfds-review`).

### `INV-014` — Phân lớp Frontend, Đồng bộ Policy & Truyền lỗi đầy đủ
- **Quy tắc:**
  - Code mới trong `usfds-web` theo đúng 3 lớp `component → hook → api client` (không gọi `api/*` trực tiếp trong component mới).
  - Hiển thị/ẩn tính năng đi qua `lib/feature-policy.ts` + `useActorContext` khớp với quyền backend; `api/client.ts` luôn reject `ApiClientError` cho mọi HTTP lỗi hoặc `success: false` (`ISS-028`).
- **Thực thi:** **Tầng 1/2** (`client.test.ts`, `feature-policy` tests, ESLint/build) + **Tầng 3** (`usfds-review`).

### `INV-015` — Đồng bộ tài liệu kiến trúc cùng PR
- **Quy tắc:** Bất kỳ task nào thay đổi contract (`C1–C5`), state machine, queue/storage layout, hoặc bất biến (`INV-001..015`) đều phải cập nhật `docs/arch/` trong cùng PR trước khi merge.
- **Thực thi:** **Tầng 3 (ĐÃ KÍCH HOẠT)** — `usfds-plan` (§4.5) + `usfds-review` + `usfds-task-workflow` (§5).

---

## Bảng tổng hợp mức độ tự động hóa (Guardrail Matrix)

| Mã | Tên ngắn | Tầng thực thi chính | Guard / Test đang chạy |
|---|---|---|---|
| `INV-001` | Auth-by-default & CORS | **Tầng 1** (Route Guard) | `usfds-server/tests/test_route_security_guard.py`, `test_auth_and_rbac_api.py` |
| `INV-002` | Project isolation & Storage auth | **Tầng 1 + Tầng 2** | `usfds-server/tests/test_route_security_guard.py`, `test_auth_and_rbac_api.py` |
| `INV-003` | 3-Scope RBAC & OWN | **Tầng 2 + Tầng 3** | `test_auth_and_rbac_api.py`, `usfds-review` *(open gap: `ISS-052`)* |
| `INV-004` | File I/O & Code Sandbox | **Tầng 2 + Tầng 3** | `test_feature_management.py`, `test_modal_provider.py`, `test_s3_storage.py` |
| `INV-005` | Clean Arch Layering | **Tầng 1** (AST Guard) | `usfds-core/tests/test_architecture_guards.py`, `usfds-server/tests/test_route_security_guard.py` |
| `INV-006` | PG Compat & Single-Head Alembic | **Tầng 1** (Guard) | `usfds-infra/tests/test_pg_compat_guard.py`, `test_migrations.py` |
| `INV-007` | Bounded DuckDB for Large Data | **Tầng 1** (AST Guard) | `usfds-core/tests/test_architecture_guards.py` *(open gap: `ISS-049`)* |
| `INV-008` | Queue Sync, Idempotency & DB Hygiene | **Tầng 1 + Tầng 2** | `usfds-worker/tests/test_worker_guards.py`, `test_queue_mode_api.py`, `test_remote_poller.py` |
| `INV-009` | Two-Tier Prep & Anti-Leakage | **Tầng 2 + Tầng 3** | `usfds-core/tests/test_architecture_guards.py`, `test_feature_engineering_service.py` *(open gap: `ISS-050`)* |
| `INV-010` | Single-Source Columns & Labels | **Tầng 2 + Tầng 3** | `test_system_metadata.py`, `test_mapping_service.py`, `test_project_warehouse.py`, `test_rule_engine.py` (`ISS-047` resolved) |
| `INV-011` | In-Use & Zero-Orphan Delete | **Tầng 2 + Tầng 3** | `test_dataset_api.py`, `test_feature_api.py`, `test_migrations.py` *(open gaps: `ISS-002`, `ISS-048`)* |
| `INV-012` | Optimistic Lock & Immutability | **Tầng 2** | `test_case_repositories.py`, `test_model_version_uniqueness.py`, `test_rule_api.py` |
| `INV-013` | Hybrid Decision & Metric Math | **Tầng 2 + Tầng 3** | `usfds-core/tests/test_architecture_guards.py` (`BR-DT-07`), `test_insight_report_service.py` (`ISS-046` resolved) |
| `INV-014` | FE Layering & Error Propagation | **Tầng 2 + Tầng 3** | `usfds-web` `client.test.ts`, `usfds-review` *(tech-debt: `ISS-032`)* |
| `INV-015` | Architecture Doc-Sync | **Tầng 3** | `usfds-plan` (§4.5) + `usfds-review` + `usfds-task-workflow` (§5) |

---

> [!WARNING]
> **Các lỗ hổng thực tế phát hiện trong kiểm toán As-Built (26-11-27) — đã ghi nhận vào `docs/issues/11-27-2026.md`:**
> 1. **`ISS-048` (`INV-011`):** `project_service.py:87-98` — `_check_active_workloads` bỏ sót `TrainingRun` đang chạy trên SQL DB.
> 2. **`ISS-049` (`INV-007`):** `inference/executor.py:594, 643` — model `BUILTIN` gọi `apply_domain_feature_engineers` 2 lần liên tiếp.
> 3. **`ISS-050` (`INV-009`):** `builtin_trainer.py:93-97` & `inference/executor.py:146-150` — bỏ qua `non_ml_columns` động từ `SystemColumnMetadata`.
> 4. **`ISS-051` (`C3` / liên quan `ISS-001`):** `training/executor.py:156` hardcode `main.py`; `training_service.py:213-243` chưa copy `fitted_pipeline.joblib` vào thư mục run.
> 5. **`ISS-052` (`INV-003`):** `feature_router.py:112, 241, 372, 434` — endpoint đọc feature/feature-set chưa lọc `GrantScope.OWN`.
> 6. **`ISS-053`:** `schema_validator.py:408-427` đối chiếu `raw_schema` và chưa whitelist `model_score` / `model.score`.
