# Changelog

Completed work, newest first. Updated at merge time (see `AGENTs.md` §0.1). Issue IDs refer to `docs/issues/README.md`.

## 2026-11-20 — ISS-010: Model Versioning Scheme (`v1, v2, v3...`) & Uniqueness
Plan: `.plan/model_versioning_scheme.md` · Board: `.plan/BOARD.md`

- Core (`base_model_version_repo.py`, `in_memory_repos.py`, `training_service.py`): simplified `ModelVersion` allocation to monotonic `v1, v2, v3...` (`_resolve_next_semver`), added numeric version sorting (`parse_version_sort_key` so `v10 > v2 > 1.0.0`), avoided `vv1` in `ModelLineageNode.label`, and added a 5-attempt retry loop in `handle_training_completion` on `DuplicateModelVersionError` (`ISS-010`).
- Infra (`tables/model.py`, `repos/model.py`, Alembic `14f998f68015`): added `UniqueConstraint("model_id", "semver", name="uq_model_versions_model_semver")` on `model_versions`, wrapped `SqliteModelVersionRepository.save()` in `begin_nested()` savepoints to map duplicate `IntegrityError` to `DuplicateModelVersionError`, and sorted `get_latest_version` / `list_by_model` by `parse_version_sort_key`.
- Web (`usfds-web/src/utils/formatters.ts`, `ModelHubView`, `ModelLineageModal`, `ModelLineagePanel`, `ActivateModelModal`, `TrainingRunDetailView`, `DetectionJobWizardView`, `DetectionJobsHubView`, `DetectionResultExplorerView`): added `formatModelVersion` so `v1` displays as `v1` (not `vv1`) while legacy `1.0.0` remains `v1.0.0`.
- Tests: `./scripts/test.sh core infra server` passed (`core` `154 passed, 15 skipped`, `infra` `39 passed`, `server` `33 passed`); `usfds-web` `18 test files / 30 passed`, `npm run build` & `npm run lint` 0 errors.
## 2026-11-21 — ISS-007 & ISS-027: System Metadata Management & Alias Consolidation
Plan: `.plan/system_metadata_management.md` · Board: `.plan/BOARD.md`

- Core (`system_metadata`, `mapping`, `preprocessing`, `inference`, `insight_report`, `rule_engine`, `training`): consolidated all canonical column alias lists into `DEFAULT_SYSTEM_COLUMN_ALIASES`, `resolve_canonical_column`, and `build_non_ml_columns` (`ISS-027`); added `SystemColumnMetadata`, `ISystemColumnMetadataRepository`, and `SystemMetadataService` (protecting the 5 `CORE` columns from deletion/structural edits while allowing alias/description updates); updated `DataMappingService` to enforce required `DOMAIN` columns, coerce `LogicalDataType`, write immutable `datasets/{dataset_id}/mapped/{artifact_id}/mapped.parquet` paths, and snapshot `non_ml_columns` + `metadata_snapshot` into `validation_report` (propagated through `FeatureEngineeringExecutionService` to `PreprocessingExecutionService` / `PreprocessingPipelineBuilder`) (`ISS-007`).
- Infra, Server & Worker: added `system_column_metadata` ORM table, `SqlSystemColumnMetadataRepository`, idempotent `seed_system_metadata`, `system_metadata:manage` RBAC permission in `seed_rbac.py`, Alembic migration `adb5e69392ae` (`if_not_exists=True`), `/api/v1/system-metadata/columns` CRUD router, and wired `SqlSystemColumnMetadataRepository` into `usfds-worker/handlers.py`.
- Web (`usfds-web`): added `systemMetadataApi`, `useSystemMetadata`, `SystemMetadataAdminTab` integrated into the `/admin` portal (`Quản trị hệ thống` with scroll & non-wrapping constraint badges), and dynamic `DOMAIN` fields + alias auto-matching + Schema Drift warnings in `SchemaMappingWorkspace`.
- Tests: `./scripts/test.sh` passed all 6 packages (`core` `156 passed, 15 skipped`, `infra` `37 passed`, `server` `35 passed`, `worker` `3 passed`, `cli` `5 passed`, `web` `19 files / 35 passed`); `usfds-web` build & lint 0 errors.

## 2026-11-17 — ISS-016, ISS-018, ISS-019 & ISS-022: Quick Backend Hardening
Plan: `.plan/quick_backend_hardening.md` · Board: `.plan/BOARD.md`

- Core (`script_trainer.py`, `inference/executor.py`, `plugins/validator.py`): added explicit subprocess timeouts (`600s` default for `ScriptPluginTrainer`, `300s` for `execute_plugin_bundle_inference`) converting `TimeoutExpired` into `RuntimeError`, and handled `TimeoutExpired` in `ModelPluginValidator` dry-runs to return `PluginValidationResult(is_valid=False)` (`ISS-022`).
- Infra (`SqliteCaseRepository`): branched `rule_code` search filter by SQL dialect (`json_array_elements_text` on PostgreSQL, `sqlite_only()` + `json_each` on SQLite) and removed `@pytest.mark.xfail` from `test_case_search_by_rule_code_is_postgresql_compatible` (`ISS-018`).
- Server (`config.py`, `deploy/.env.example`, `training_router.py`): added `USFDS_MAX_PLUGIN_UPLOAD_MB` (default `10`), enforced bounded streaming body read (`413` on oversize in `_read_bounded_body`), and offloaded `_register_uploaded_plugin_sync` via `run_in_threadpool` so `POST /api/v1/training/models/plugins/upload` does not block the asyncio event loop (`ISS-016`, `ISS-019`).
- Tests: `./scripts/test.sh core infra server` passed (`core` `152 passed, 15 skipped`, `infra` `37 passed`, `server` `33 passed`).

## 2026-11-16 — ISS-028: Web API client error propagation
Plan: `.plan/web_api_client_error_propagation.md` · Board: `.plan/BOARD.md`

- Web (`usfds-web/src/api/client.ts`): added `ApiClientError` (`statusCode`, `details`), removed error-swallowing `try/catch` in `get`/`post`/`put`/`patch`/`delete`, and threw `ApiClientError` in `normalizeResponse` when `success === false` so `react-query` retries and error states work (`ISS-028`).
- Web (`hooks`, `components`, `pages`): wrapped imperative callers (`useAuth`, `ProfileModal`, `RuleCatalogView`, `RuleWorkspace`, `RuleVersionHistoryModal`, `AdminUsersPage`) with `try/catch` / `.catch` and migrated partial-failure `Promise.all` loads (`ModelHubView`, `TrainingWizardView`, `RuleDryRunWorkspace`, `DetectionJobWizardView`) to `Promise.allSettled`.
- Tests: added `src/api/client.test.ts` (3 passed) and partial-failure test in `ModelHubView.test.tsx` (2 passed); `npm run build` and `npm run lint` passed with 0 errors (`vitest run`: 26 passed, 1 pre-existing MSW+undici blob failure in `DatasetHubView.test.tsx`).
## 2026-11-16 — ISS-037: RBAC Feature Visibility Gating & Backend Router Hardening
Plan: `.plan/rbac_feature_visibility.md` · Board: `.plan/BOARD.md`

- Infra & Core (`seed_rbac.py`, `authz_service.py`): removed `rule:propose` (plus idempotent cleanup from existing DB rows), enforced Phương án A (`fraud_analyst` holds `rule:read` only; `data_scientist` holds all 7 rule permissions), added `detection:export` and `case:create`, and fixed `set_system_user_roles` (`user:update`) and `list_project_members` (`project_member:read`).
- Server (`user`, `dataset`, `rule`, `training`, `detection`, `investigation`, `insight_report` routers): enforced `authz` checks across remaining sub-endpoints, split `case:assign` vs `case:claim` on `POST /cases/{case_id}/claim`, and guarded export (`detection:export`) and case intake (`case:create`).
- Web (`usfds-web`): added centralized `feature-policy.ts` (`ACTOR_FEATURE`, `MODULE_FEATURE_MAP`) and `useActorContext(projectId?)` reusing `/api/v1/auth/me`; added `FeatureRouteGuard.tsx` and direct-route gating in `App.tsx`; hid unauthorized navigation items and actions across Sidebar, Omnisearch, UserAccountMenu, Project Portal/Settings, AdminUsersPage, Data Management, Model & Training, Rule Engine, Detection, Investigation, and Insight & Reports.
- Tests: `./scripts/test.sh` passed all 6 packages (`core` 149 passed / 15 skipped, `infra` 35 passed / 1 xfailed, `server` 31 passed, `worker` 3 passed, `cli` 5 passed, `web` 17 files / 28 tests passed); `usfds-web` build & lint 0 errors.

## 2026-11-15 — ISS-035, ISS-014, ISS-017 & ISS-003: Quick Bugfix & CORS Hardening
Plan: `.plan/quick_bugfix_and_cors_hardening.md` · Board: `.plan/BOARD.md`

- Infra (`SqliteModelRepository`): imported `RiskLevel` in `repos/model.py` so reading models with non-null `risk_level` no longer raises `NameError` (`ISS-035`).
- Core & Infra (`DataManagementService.delete_dataset`): fixed `artifact_repo.list_by_dataset` call and removed the outer `except Exception: pass` so artifact files are deleted from storage (`ISS-017`); added `list_active_by_artifact_ids` (`ITrainingRunRepository`) and `list_active_by_target_artifact_ids` (`IDetectionJobRepository`) to block deleting datasets referenced by `PENDING`/`RUNNING` runs or jobs (`DatasetInUseError` → `409 Conflict`, `ISS-003`).
- Server (`api.py`, `config.py`): wired `settings.cors_origins` into `CORSMiddleware` via `build_cors_options`, changed default `USFDS_CORS_ORIGINS` to local dev origins, and disabled `allow_credentials` when wildcard `*` is configured (`ISS-014`).
- Tests: `core` (`149 passed, 15 skipped`), `infra` (`35 passed, 1 xfailed`), `server` (`30 passed`).

## 2026-11-15 — ISS-015 & ISS-036: Presigned Upload/Export & `IFileStorage` File I/O Guard
Plan: `.plan/presigned_upload_and_file_io_guard.md` · Board: `.plan/BOARD.md`

- Web (`usfds-web`): fixed `storageApi.resolveStoragePath`, `useDatasetImport`, `ImportDatasetModal` (`.pq,.txt`), and `DetectionJobWizardView` so browser S3 mode uploads via presigned URLs without fabricating `../datasets/...` paths, while Electron local mode keeps native paths; unified `datasetApi.exportDataset`, `detectionApi.exportResults`, and `insightReportApi.exportReport` (including `html`) to use presigned URLs on S3 and authenticated `apiClient.getRawAxios()` blobs on local mode.
- Core & Infra (`usfds-core`, `usfds-infra`): consolidated all file existence/read/copy checks into `IFileStorage` (`LocalFileStorage._resolve_path` handles local/Electron paths; `S3FileStorage.save_file` no longer reads server local paths, resolving `ISS-015`); removed 11 scattered `Path(...).is_file()` fallbacks across core services, `rule_router`, and `usfds-worker`.
- Server & Worker (`usfds-server`, `usfds-worker`): updated `dataset_router.import_dataset` and `handle_dataset_ingestion` to pass `actor.user_id` and `actor.username`.
- Tests: `./scripts/test.sh` passed across all 6 packages (`core` 149 passed / 15 skipped, `infra` 34 passed / 1 xfailed, `server` 23 passed, `worker` 3 passed, `cli` passed, `web` 12 files / 23 tests passed).

## 2026-11-14 — ISS-008: Model version & training run data lineage visualization
Plan: `.plan/model_version_lineage.md` · Board: `.plan/BOARD.md`

- Core (`TrainingOrchestrationService`): added `get_model_version_lineage` and `get_training_run_lineage` to trace upstream `DatasetArtifact` chain (`RAW → ... → FEATURE_ENGINEERED/PRE_PROCESSED`) → `TRAINING_RUN` → `MODEL_VERSION` with cycle protection.
- Server: added `GET /api/v1/training/versions/{version_id}/lineage` and `GET /api/v1/training/runs/{run_id}/lineage`.
- Web: extended `LineageCanvasView` for `FEATURE_ENGINEERED`, `TRAINING_RUN`, and `MODEL_VERSION` stages; added read-only `ModelLineagePanel` + `ModelLineageModal` and integrated them into `TrainingRunDetailView` and `ModelHubView` (Model Registry versions table).
- Tests: `core` 146 passed (15 skipped), `server` 16 passed, `web` 11 files / 19 tests passed (`build` + `lint` 0 errors).

## 2026-11-14 — ISS-005: Vietnamese UI copy in usfds-web
Plan: `.plan/ui_vietnamese_localization.md` · Board: `.plan/BOARD.md`

- User-visible copy in `usfds-web` (layout, data management, project, detection, investigation, reports, model, rule) is Vietnamese. Hard-to-translate terms use `Vietnamese (English)`; only `Precision` does so for now. `Artifact` and acronyms stay English.
- Formatters: numbers use `vi-VN`; the missing-date placeholder is `Không có`.
- Tests added for sidebar, topbar, formatters, dataset hub, project management, pipeline labels, detection hub, PoliciesView headers, model hub and rule catalog. `./scripts/test.sh web`: 10 files, 16 tests passed.
- Not done: `docs/issues/` status for ISS-005 (needs approval for `docs/` edits).

## 2026-11-14 — Phase 0: Foundation for parallel AI agents
Plan: `.plan/parallel_agent_setup.md` · Board: `.plan/BOARD.md`

### Agent context
- Skills in `.claude/skills/`: `usfds-plan` (+ `template.md`), `usfds-task-workflow`, `usfds-testing`, `usfds-backend-change`, `usfds-frontend-change`.
- `.plan/BOARD.md`: task status, dependencies and file ownership.
- `AGENTs.md`: fixed the architecture link, added "Parallel Agent Work", and changed the TODO/CHANGELOG rule so these files are updated only at merge.
- Issues restructured with stable IDs (ISS-001..035) and an index in `docs/issues/README.md`. New findings are in `docs/issues/11-14-2026.md`.

### Test environment (no Docker)
- `scripts/test.sh [core|infra|server|worker|cli|web]` is the single entrypoint. Python is pinned to 3.12, Poetry envs are synced from their locks, and `USFDS_*` env vars are isolated. (ISS-024)
- Shared fixtures in `usfds_infra.testing.pytest_plugin`: per-test SQLite migrated with Alembic, local storage, and moto S3. Server tests use `conftest.py` with `server_settings`, `client` and `client_queue_mode`. (ISS-025)
- `usfds_worker.testing.InlineJobQueue` runs queue-mode routes through the real worker handlers with JSON payloads.
- PostgreSQL compatibility guard (G1 DDL/migrations, G2 PostgreSQL compile, G3 SQLite-only function denylist) is on in every backend test. ISS-018 is pinned as a strict xfail.
- Web: vitest + Testing Library + MSW (`npm test`), with the `renderWithProviders` helper and example tests.
- Fixed broken tests: 2 core tests imported infra / used a removed entity; the S3 tests used a fake that had drifted (now moto).

### Backend
- Alembic migrations (`usfds_infra.database.migrate`, baseline `0001_baseline`). `init_db` now migrates instead of `create_all`. Legacy databases keep their data: verified on a copy of the demo DB, where all 13 tables kept their row counts and no drift was reported. (ISS-020)
- ORM tables and repositories split into `database/tables/<domain>.py` and `database/repos/<domain>.py`; server providers split into `usfds_server/providers/`. The old modules are kept as re-export shims. (ISS-026)
- Auth seam drafted and then reverted on 26-11-14: auth and RBAC will be planned and built in a separate session (ISS-006). No auth code remains in `usfds-server`.
- `teardown_infrastructure` now resets every lifecycle global, so a stale session factory or storage no longer leaks across app restarts.

### Web / config
- Dev ports unified on 8200 (Vite proxy, Electron); added `usfds-web/.env.example`. (ISS-029)
- `usfds-agent/.env`, `usfds-server/.env` and `usfds-web/.env` removed from git tracking, and `usfds-agent/.env.example` added. (ISS-013; key rotation by the user)

### Test results
core 143 passed / 15 skipped · infra 32 passed / 1 xfailed (ISS-018) · server 14 passed · worker 3 passed · cli 5 passed · web 6 passed. Total ~28 s.
