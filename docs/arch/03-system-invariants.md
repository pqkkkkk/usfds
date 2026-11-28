# 03 — Architecture Principles, System Invariants & Guardrail Matrix
<!-- [26-11-27] Created (INV-001..015). [26-11-28] English rewrite; principles P-01..P-04 and INV-016 added; bug details moved to docs/issues. -->

Read this file for **every** task (plan and review).

- **Principles (`P-01..P-04`)** are design rules for new and changed code. Existing code does not fully conform yet; gaps are tracked as issues. A change must not widen a gap.
- **Invariants (`INV-001..016`)** must never be broken. Each one is enforced at one or more tiers:
  - **Tier 1 — static / structural guard:** automated test in `./scripts/test.sh` that scans the app / AST / schema; catches violations even when the author forgot a unit test.
  - **Tier 2 — contract / property test:** cross-module integration test or lifecycle / math property test on sample data.
  - **Tier 3 — plan checklist + `usfds-review`:** semantic check during planning (§4.5) and independent review.

---

## Architecture principles

### `P-01` — Configurable
- **Rule:** Business-significant values — thresholds, limits, column roles, label mappings, compute routing — live in **system metadata**: an extensible registry with defaults, editable via UI. `SystemColumnMetadata` is the first kind; new features extend system metadata instead of adding constants. `USFDS_*` env vars are only for deployment infrastructure and secrets (DB URL, storage endpoint, credentials). Never hardcode a business value in a service.
- **Conformance:** column roles, label mappings and per-run parameters (`score_threshold`, split ratio, hyperparameters) are configurable. Limits and routing are still constants or env vars.
- **Gaps:** `ISS-058`.
- **Enforcement:** Tier 3.

### `P-02` — Pluggable
- **Rule:** A variant (trainer, model plugin, feature script, compute provider, storage backend, queue, analytic / graph engine) is added by implementing a port and registering it. Never by adding `if/else` on a type at call sites.
- **Conformance:** mature in model management (`BUILTIN` / `SCRIPT` trainers, `IRemoteComputeProvider` + `RemoteProviderRegistry`), storage (`IFileStorage`), dispatchers (local / queue / routing). Other modules adopt it as they evolve.
- **Gaps:** engines without a port (`ISS-057`).
- **Enforcement:** Tier 3.

### `P-03` — Compute-isolated workloads
- **Rule:**
  - The API runs only business logic: validate, authorize, persist, dispatch.
  - All computation runs as a **self-contained job**: payload DTO in → data via `IFileStorage` / presigned URLs → result via notifier out. A job may use only explicitly allowed services (ideally none) and never a DB session or credentials (`INV-004`, `INV-005`).
  - The same job can run in-process, on a dedicated worker, on K8s, or on a third-party provider, selected via system metadata (`P-01`) and a provider registry (`P-02`).
  - Each job pulls only the dependencies it needs.
  - **Exception:** bounded interactive reads (result pagination, graph neighbor expansion, dataset preview) stay in the API, behind a port, with bounded resources (`INV-007`). Full-dataset computation is always a job.
- **Conformance:** training runs in-process, on BullMQ, or on Modal. Other job types run in-process or on BullMQ only. No K8s adapter. All jobs share one `usfds-core` dependency set. Some routers still compute on full data.
- **Gaps:** `ISS-056`.
- **Enforcement:** Tier 3 + Tier 1 executor guard of `INV-005`.

### `P-04` — Dependency inversion
- **Rule:** `usfds-core` depends only on ports (abstract classes). Concrete adapters live in `usfds-infra` and are wired at composition roots (`usfds-server/providers`, `usfds-worker/main`). Stateful engines (warehouse store, graph DB) are always behind a port. **Sole exception:** job executors may import compute libraries directly.
- **Conformance:** repositories, `IFileStorage`, dispatchers, notifiers, compute providers, token / password providers are ports. `ProjectWarehouse`, the LadybugDB graph implementation and some API-called DuckDB readers live in core.
- **Gaps:** `ISS-057`.
- **Enforcement:** Tier 1 — `INV-005` import guard + `test_core_engine_imports_limited_to_allowlist` (frozen, shrink-only allowlist of core files importing `duckdb` / `ladybug`).

---

## Group A — Security, authorization & project isolation

### `INV-001` — Authenticated-by-default API & safe CORS
- **Rule:** Every FastAPI route outside `PUBLIC_ALLOWLIST` (`/health`, `/api/health`, `/api/v1/auth/{mode,login,refresh,logout}`) goes through an auth dependency (`get_actor_context` / `get_current_user` / `require_system_permission`). If `USFDS_CORS_ORIGINS` contains `*`, `allow_credentials` must be `False` (`ISS-014`).
- **Enforcement:** Tier 1 — `usfds-server/tests/test_route_security_guard.py` + `test_auth_and_rbac_api.py`.

### `INV-002` — Project isolation & anti-404-oracle
- **Rule:**
  - Every query on a project resource (`dataset`, `feature`, `rule`, `training`, `detection`, `case`, `network`, `report`, `storage`) authorizes `project_id` **before** revealing whether the record exists. Cross-project access returns `404` / `403` and never leaks data (`ISS-042`).
  - `GET /api/v1/storage/presigned-download` signs a URL only after anti-path-traversal, registered-prefix and project / ownership checks.
- **Enforcement:** Tier 1 (`test_route_security_guard.py`) + Tier 2 (`test_auth_and_rbac_api.py`).

### `INV-003` — 3-scope RBAC (`OWN < PROJECT < SYSTEM`) & no privilege escalation
- **Rule:**
  - `GrantScope.OWN` allows read / update / delete only where `user_id == actor.user_id`; list queries under `OWN` filter `owner_id = actor.user_id` (`ISS-043`).
  - `SYSTEM_ONLY_PERMISSIONS` are never granted to `RoleScope.PROJECT` roles; a non-`system_admin` cannot grant more than they hold; the last `project_admin` of a project cannot be removed or demoted.
- **Enforcement:** Tier 2 (`test_auth_and_rbac_api.py`, `test_authz_enforcement.py`, `test_authz_management.py`) + Tier 3 for every new router / endpoint.

### `INV-004` — File I/O boundary & user-code sandbox
- **Rule:**
  - In S3 mode the server never reads a client-supplied local filesystem path (`ISS-015`). Plugin uploads are size-capped (`USFDS_MAX_PLUGIN_UPLOAD_MB`) and do not block the event loop (`ISS-016`, `ISS-019`).
  - User code (`SCRIPT` model plugins, `PYTHON_CODE` features) passes an AST validator (blocks dangerous imports / builtins) and runs in a subprocess with a timeout (`ISS-022`).
  - Remote compute receives only `PresignedUrlStorage` with bounded TTL — **never** S3 or DB credentials.
- **Enforcement:** Tier 2 (`test_feature_management.py`, `test_modal_provider.py`, `test_s3_storage.py`) + Tier 3.

---

## Group B — Layering, persistence & performance

### `INV-005` — Clean Architecture boundary & DB-free executors
- **Rule:**
  - `usfds-core` never imports `usfds_infra`, `usfds_server`, `usfds_worker`, `sqlalchemy`, `fastapi`, `boto3`, `bullmq`, or `modal`.
  - `TrainingRunExecutor` and `BatchInferenceExecutor` never receive a SQLAlchemy session or repository; they use only DTO payloads, `IFileStorage`, and notifier / result objects.
  - FastAPI routers never import ORM tables / models from `usfds_infra.database.{models,tables,case_models}`.
- **Enforcement:** Tier 1 — `usfds-core/tests/test_architecture_guards.py` + `usfds-server/tests/test_route_security_guard.py`.

### `INV-006` — PostgreSQL compatibility & single migration path
- **Rule:**
  - All SQL / ORM / DDL is PostgreSQL-compatible even though tests run on SQLite (`ISS-018`).
  - Schema changes go only through Alembic, with **exactly one head**, `schema_drift == []`, and offline-renderable PostgreSQL SQL (`ISS-020`).
- **Enforcement:** Tier 1 — `usfds-infra/tests/test_pg_compat_guard.py` + `test_migrations.py`.

### `INV-007` — Bounded memory for large data
- **Rule:** Large-data reads in API / worker (ingestion, mapping, prediction results, warehouse, insight report, behavior profile, network graph) use bounded DuckDB (`create_bounded_duckdb_connection`: capped threads, RAM, spill directory) — never a full-file pandas load in the API process (`ISS-012`, `ISS-044`).
- **Enforcement:** Tier 1 — `test_large_data_modules_do_not_call_pandas_full_file_readers` + Tier 3.

### `INV-008` — Queue safety, idempotency & no DB session across network I/O
- **Rule:**
  - CPU-bound handlers in `usfds-worker` run via `asyncio.to_thread` so the event loop keeps the BullMQ lock; fire-and-forget jobs (`training_run`, `batch_inference`) exit immediately if the DB status is already terminal.
  - `JOB_*` / `QUEUE_*` catalogs in `usfds-infra`, `usfds-worker` and `InlineJobQueue` stay 1:1; deterministic input / business errors are wrapped in `UnrecoverableError` (`ISS-021`).
  - Background pollers (e.g. `RemoteTrainingPoller`) split *read DB → network call without a session → write DB*.
- **Enforcement:** Tier 1 (`usfds-worker/tests/test_worker_guards.py`) + Tier 2 (`test_queue_mode_api.py`, `test_queue_timeout_api.py`, `test_remote_poller.py`) + Tier 3.

### `INV-016` — No pandas for data processing
- **Rule:** New code never imports `pandas` in `usfds-core`, `usfds-infra`, `usfds-server`, or `usfds-worker`. Use bounded DuckDB (`INV-007`) or PyArrow; at the model fit / predict boundary pass NumPy / Arrow. Legacy files are frozen in a shrink-only allowlist; migrating a file means removing its entry.
- **Enforcement:** Tier 1 — `test_pandas_imports_limited_to_allowlist` + `test_pandas_allowlist_has_no_stale_entries` (`usfds-core/tests/test_architecture_guards.py`). Migration: `ISS-055`.

---

## Group C — Data integrity & resource lifecycle

### `INV-009` — Two-tier preparation & anti-leakage
- **Rule:**
  - `FEATURE_ENGINEERED` artifacts keep `event_id`, `user_id`, `timestamp` (`BR-DM-07`, `critical_changes.md`).
  - Train/test is split by event time **before** fitting any cleanser, target-rate encoder or scaler; nothing is ever fit on test data.
  - Every column with `ml_role != FEATURE` (from the artifact's `SystemColumnMetadata` snapshot) is excluded from the feature vector consistently in preprocessing, training and inference.
- **Enforcement:** Tier 2 (`test_architecture_guards.py`, `test_feature_engineering_service.py`) + Tier 3.

### `INV-010` — Single source for column & label normalization (no silent corruption)
- **Rule:**
  - System column lookup (`event_id`, `timestamp`, `amount`, `user_id`, `label`, entity columns) always uses `resolve_canonical_column()` (`ISS-027`).
  - Binary label normalization never silently coerces unknown labels to `0` / `-1` while reporting `PASSED` (`ISS-047`); it fails fast or uses the shared normalizer across mapping → warehouse → rule backtest → training (`C4`).
- **Enforcement:** Tier 2 (`test_system_metadata.py`, `test_mapping_service.py`, `test_project_warehouse.py`, `test_rule_engine.py`) + Tier 3.

### `INV-011` — Safe deletion & zero orphans
- **Rule:**
  - In-use resources cannot be deleted: dataset with an active job → `409`; feature with dependents / in a `FeatureSet` / used by an `ACTIVE` rule → `400`; `CORE` metadata → `400`; project with active jobs → `400`; active / in-use rule (`ISS-002`).
  - Deleting a DB record that owns files (e.g. `delete_dataset`) also deletes its artifacts on `IFileStorage` (`ISS-017`). `user_id` foreign keys use `ON DELETE RESTRICT` (`ISS-023`).
- **Enforcement:** Tier 2 (`test_dataset_api.py`, `test_feature_api.py`, `test_migrations.py`) + Tier 3.

### `INV-012` — Optimistic concurrency & immutable history
- **Rule:**
  - `Case` updates check `expected_version` (optimistic locking → `CaseConflictError`).
  - Editing a `Rule`'s `condition` or `action` always creates a new immutable `RuleVersion`; `ModelVersion` numbers `v1, v2, ...` are unique per `(project_id, model_id)` (unique constraint + retry). `AuditLog` is append-only.
- **Enforcement:** Tier 2 (`test_case_repositories.py`, `test_model_version_uniqueness.py`, `test_rule_api.py`).

---

## Group D — FDS semantics, frontend & doc sync

### `INV-013` — Hybrid decision & analytic formula invariants
- **Rule:**
  - Hybrid decision follows `BR-DT-07`: `Rule REJECT > Rule REVIEW | (score >= threshold) > ALLOW`.
  - Insight metrics keep their math invariants: the 4-stage funnel is monotonically non-increasing (`Stage1 >= Stage2 >= Stage3 >= Stage4`); rates are in `[0, 1]`; `VERIFIED` and `PENDING` are never mixed in one formula (`ISS-046`); no `NaN` / `Infinity` in JSON payloads.
- **Enforcement:** Tier 2 (`test_architecture_guards.py` for `BR-DT-07`, `test_insight_report_service.py`) + Tier 3.

### `INV-014` — Frontend layering, policy sync & full error propagation
- **Rule:**
  - New `usfds-web` code follows `component → hook → api client` (no direct `api/*` calls in new components).
  - Feature visibility goes through `lib/feature-policy.ts` + `useActorContext`, matching backend permissions; `api/client.ts` always rejects with `ApiClientError` for HTTP errors or `success: false` (`ISS-028`).
- **Enforcement:** Tier 1/2 (`client.test.ts`, feature-policy tests, ESLint / build) + Tier 3.

### `INV-015` — Architecture doc sync in the same PR
- **Rule:** Any task that changes a contract (`C1–C5`), state machine, queue / storage layout, table relation, principle or invariant updates `docs/arch/` in the same PR before merge (policy: [`README.md`](README.md) §4).
- **Enforcement:** Tier 3 — `usfds-plan` (§4.5) + `usfds-review` + `usfds-task-workflow` (§5).

---

## Guardrail matrix

| ID | Short name | Main tier | Guard / tests | Open gaps |
|---|---|---|---|---|
| `P-01` | Configurable | 3 | `usfds-review` | `ISS-058` |
| `P-02` | Pluggable | 3 | `usfds-review` | `ISS-057` |
| `P-03` | Compute-isolated | 1 + 3 | `INV-005` executor guard, `usfds-review` | `ISS-056` |
| `P-04` | Dependency inversion | 1 | `test_architecture_guards.py` (`INV-005` + engine allowlist) | `ISS-057` |
| `INV-001` | Auth-by-default & CORS | 1 | `test_route_security_guard.py`, `test_auth_and_rbac_api.py` | — |
| `INV-002` | Project isolation & storage auth | 1 + 2 | `test_route_security_guard.py`, `test_auth_and_rbac_api.py` | — |
| `INV-003` | 3-scope RBAC & `OWN` | 2 + 3 | `test_auth_and_rbac_api.py`, `usfds-review` | `ISS-052` |
| `INV-004` | File I/O & code sandbox | 2 + 3 | `test_feature_management.py`, `test_modal_provider.py`, `test_s3_storage.py` | — |
| `INV-005` | Clean Architecture layering | 1 | `test_architecture_guards.py`, `test_route_security_guard.py` | — |
| `INV-006` | PG compat & single-head Alembic | 1 | `test_pg_compat_guard.py`, `test_migrations.py` | — |
| `INV-007` | Bounded memory for large data | 1 + 3 | `test_architecture_guards.py` | `ISS-049` |
| `INV-008` | Queue sync, idempotency, DB hygiene | 1 + 2 | `test_worker_guards.py`, `test_queue_mode_api.py`, `test_remote_poller.py` | — |
| `INV-009` | Two-tier prep & anti-leakage | 2 + 3 | `test_architecture_guards.py`, `test_feature_engineering_service.py` | `ISS-050` |
| `INV-010` | Single-source columns & labels | 2 + 3 | `test_system_metadata.py`, `test_mapping_service.py`, `test_project_warehouse.py`, `test_rule_engine.py` | — |
| `INV-011` | In-use & zero-orphan delete | 2 + 3 | `test_dataset_api.py`, `test_feature_api.py`, `test_migrations.py` | `ISS-002`, `ISS-048` |
| `INV-012` | Optimistic lock & immutability | 2 | `test_case_repositories.py`, `test_model_version_uniqueness.py`, `test_rule_api.py` | — |
| `INV-013` | Hybrid decision & metric math | 2 + 3 | `test_architecture_guards.py`, `test_insight_report_service.py` | — |
| `INV-014` | FE layering & error propagation | 2 + 3 | `client.test.ts`, `usfds-review` | `ISS-032` |
| `INV-015` | Architecture doc sync | 3 | `usfds-plan`, `usfds-review`, `usfds-task-workflow` | — |
| `INV-016` | No pandas | 1 | `test_architecture_guards.py` (pandas allowlist) | `ISS-055` |
