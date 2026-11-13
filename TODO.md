# 12-11-2026 — Support Light Mode in `usfds-web` — plan: `.plan/light_mode_support.md`
- [x] [docs] Update `docs/design-system.md` with Light Mode Semantic Tokens (`[26-11-12]`)
- [x] [fe] Configure RGB CSS variable tokens for `dark.*`, `slate.*`, and status text shades (`300`/`400`) in `usfds-web/src/index.css` and `usfds-web/tailwind.config.js`
- [x] [fe] Create `ThemeProvider` and `useTheme()` hook (`usfds-web/src/hooks/useTheme.tsx`) supporting 2 modes (`dark` / `light`, default `dark`) with `localStorage` persistence and chart/canvas palette tokens
- [x] [fe] Add `Sun`/`Moon` theme toggle button to `Topbar.tsx` and `ProjectManagementView.tsx`
- [x] [fe] Replace non-button `text-white` headings/cells with `text-slate-100` and wire Recharts/SVG hex colors to `useTheme()` tokens
- [x] [tests/verify] Add unit test tripwire for theme state/token resolution and verify `npm run build` & `npm run lint` in `usfds-web`

# 12-11-2026 — Add `usfds-web` to `deploy/docker-compose.yml` — plan: `.plan/deploy_usfds_web.md`
- [x] [deploy] Add `deploy/nginx.conf` (SPA fallback + `/api/` proxy to `usfds-server:8000`) and `deploy/Dockerfile.web`
- [x] [deploy] Add `.dockerignore` to exclude `node_modules`, `dist`, `release`, `.venv`, `__pycache__`, `.git`
- [x] [deploy] Update `deploy/docker-compose.yml` (remove `profiles: ["app"]`, add `usfds-web` on `${USFDS_WEB_PORT:-5173}:80`)
- [x] [deploy] Update `deploy/.env.example` and `deploy/.env` with `USFDS_WEB_PORT=5173`
- [x] [verify] Validate `docker compose --env-file .env config -q` in `deploy/`

# 11-11-2026 — Client-Server Worker Design & Implementation — plan: `.plan/client_server_worker_design.md`
- [x] [infra] Extend `BullMQJobQueue` (`usfds-infra/src/usfds_infra/job_queue/bullmq_queue.py` & `__init__.py`) with `QUEUE_DATA_PIPELINE`, job constants (`JOB_PLUGIN_DRY_RUN`, `JOB_RULE_BACKTEST`, `JOB_DATASET_INGESTION`, `JOB_SCHEMA_MAPPING`, `JOB_FEATURE_ENGINEERING`), and `enqueue_and_wait()`
- [x] [core/infra] Ensure `DatasetIngestionService.import_dataset` and `S3FileStorage.save_file` support S3 storage keys seamlessly when invoked on `usfds-worker`
- [x] [worker] Implement all 7 handlers in `usfds-worker/src/usfds_worker/handlers.py` and register 3 queue workers (`usfds-training`, `usfds-batch-inference`, `usfds-data-pipeline`) in `usfds-worker/src/usfds_worker/main.py` by directly importing `usfds-core` services
- [x] [server] Wire `USFDS_DISPATCH_BACKEND=queue` in `dataset_router.py`, `training_router.py`, and `rule_router.py` to dispatch heavy tasks (`import_dataset`, `map_schema`, `execute_feature_engineering`, `register_plugged_model`, `backtest_rule_on_dataset`) via `BullMQJobQueue.enqueue_and_wait`
- [x] [fe] Add auto-polling (`2.5s`) while status is `PENDING` or `RUNNING` in `TrainingRunDetailView.tsx`, `ModelHubView.tsx`, `DetectionResultExplorerView.tsx`, and `DetectionJobsHubView.tsx`
- [x] [tests] Add unit tests in `usfds-worker/tests/test_handlers.py` and `usfds-infra/tests/test_job_queue.py` covering all 7 worker handlers and `enqueue_and_wait`
- [x] [core/infra] Sanitize non-finite floats (`Infinity`, `-Infinity`, `NaN`) in `MetricEvaluator` (`roc_curve.thresholds`) and `SqliteTrainingRunRepository.save` / `SqliteDetectionJobRepository.save` (with `session.rollback()` on flush failure) for strict PostgreSQL JSON compatibility

# 10-11-2026 — Client-Server Storage Interaction via Presigned URLs — plan: `.plan/client_server_storage_presigned_url.md`
- [x] [core] Fix local path leak in `DatasetIngestionService.import_dataset` (`usfds-core/src/usfds_core/services/data_management/ingestion.py`) to check `self.file_storage.exists()` and `get_file_size()` alongside `Path.is_file()`
- [x] [infra] Extend `S3FileStorage` (`usfds-infra/src/usfds_infra/storage/s3_storage.py`) with `public_endpoint_url`, server-side `copy_object` in `save_file()`, `generate_presigned_upload_url()`, `generate_presigned_download_url()`, and bucket CORS setup
- [x] [server] Add `USFDS_S3_PUBLIC_ENDPOINT_URL` config (`config.py`, `dependencies.py`, `deploy/`), create `storage_router.py` (`/api/v1/storage/presigned-upload`, `/api/v1/storage/presigned-download`), and support `presigned=true` on dataset/detection/report export endpoints
- [x] [tests] Add unit and API tests for storage-key dataset ingestion, S3 presigned URLs/copy, and storage/export endpoints in `usfds-core`, `usfds-infra`, and `usfds-server`
- [x] [fe] Create `src/api/storageApi.ts` (`resolveStoragePath` & presigned download helper) and wire into `useDatasetImport.ts`, `DetectionJobWizardView.tsx`, `ImportCustomModelModal.tsx`, `datasetApi.ts`, `detectionApi.ts`, and `insightReportApi.ts`
- [x] [verify] Verify `pytest` across `usfds-core`, `usfds-infra`, `usfds-server` and `npm run build` in `usfds-web`

# 10-11-2026 — Upgrade Model Training Evaluation Metrics (`TASK-105`) — plan: `.plan/training_evaluation_metrics.md`
- [ ] [docs] Update `docs/features/detection/training/suc-spec.md` (`SUC-09`, `SUC-27`) with the 11 metrics in `TASK-105` and remove unmentioned metrics (`[26-11-10]`)
- [ ] [core] Upgrade `MetricEvaluator` in `usfds-core/src/usfds_core/services/training/evaluators/metric_evaluator.py`: add `mcc`, `precision_at_k` ($k \in \{50, 100, 200, 500\}$, `daily_avg` & `overall`), `precision_at_0_2_recall`, `auc_pr_card`, `pr_curve_card`, `card_precision_at_k` (`CP@k`), and deprecate unmentioned metrics (`youden_j`, `high_recall_90`, `high_recall_95`, `score_distribution`)
- [ ] [core] Wire `card_ids` and `timestamps` into `BuiltinModelTrainer`, `ScriptPluginTrainer`, and `_usfds_runner.py` (deprecating `log_loss`)
- [ ] [core/tests] Update and add unit tests in `usfds-core/tests/training/test_metric_evaluator.py` and `test_builtin_trainer.py`
- [ ] [fe] Update TypeScript types (`src/types/metrics.ts`, `src/types/model.ts`) and UI (`TrainingRunDetailView.tsx`, `ModelHubView.tsx`) to display all 11 Notion metrics and remove unmentioned metrics
- [ ] [verify] Verify `pytest` in `usfds-core` & `usfds-server` and `npm run build` in `usfds-web`

# 10-11-2026 — Fix ReportScopeToolbar detectionJobs.filter TypeError
- [x] [fe] Defensively handle detectionJobs payload in `ReportScopeToolbar.tsx`
- [x] [fe] Normalize detectionJobs query and memoization in `InsightReportModule.tsx`
- [x] [fe] Verify `npm run build` and `npm run lint` in `usfds-web`

# 06-11-2026 — Insight & Report Module (SUC-22, SUC-23, SUC-24, SUC-25)
- [x] [docs] Create Use Case Specification `docs/features/insight_report/suc-spec.md` (`[26-11-06]`) and plan `.plan/insight_report.md`
- [x] [core] Implement `DuckDBInsightEngine`, `ComplianceReportBuilder`, and `InsightReportService` in `usfds-core/src/usfds_core/services/insight_report/`
- [x] [core/tests] Add unit tests in `usfds-core/tests/test_insight_report_service.py` covering SUC-22, SUC-23, SUC-24, SUC-25 and BR-IR-01/02/03
- [x] [server] Create `insight_report_api_schemas.py`, `insight_report_router.py` (`/api/v1/reports`), and register in `api.py` & `dependencies.py`
- [x] [server/tests] Add API tests in `usfds-server/tests/test_insight_report_api.py`
- [x] [fe] Create `src/types/insightReport.ts` and `src/api/insightReportApi.ts`
- [x] [fe] Build 4-tab Insight & Report UI (`ExecutiveOverviewTab`, `EffectivenessTab`, `TypologiesPatternsTab`, `ComplianceReportCenterTab`, `ReportScopeToolbar`) and wire `InsightReportModule.tsx` + `Export SAR` shortcut in `CaseWorkbenchView.tsx`
- [x] [fe] Verify `pytest` across backend packages and `npm run build` (`tsc -b && vite build`) in `usfds-web`

# 05-11-2026 — Setup infra (Client / Server / Worker) — plan: `.plan/setup_infra.md`
- [x] [deploy] `deploy/`: docker-compose (postgres `apache/age:release_PG17_1.7.0`, `rustfs/rustfs:1.0.4-glibc`, profile `app`), `initdb/`, `.env.example`, `Dockerfile.server`, `Dockerfile.worker`; move compose out of `usfds-server/`
- [x] [infra] `create_postgres_engine`; JSON column type portable across SQLite/Postgres
- [x] [infra] `S3FileStorage(IFileStorage)` for RustFS
- [x] [infra] BullMQ (postgres backend) queue wrapper + `QueueTrainingDispatcher`, `QueueBatchInferenceDispatcher`
- [x] [worker] `usfds-worker` package: BullMQ Worker, training + batch_inference handlers
- [x] [server] Config switches (`USFDS_DB_URL`, `USFDS_STORAGE_BACKEND`, `USFDS_DISPATCH_BACKEND`); DI selects adapters; `/health` backend-agnostic
- [x] [tests] Offline tests (no Docker): S3 storage via stub client (infra), dispatcher payload (infra), worker training handler. Server suite unchanged (10 passed); compose `config -q` parses
- [ ] [verify] User verifies docker compose + end-to-end (not run by agent)
# 05-11-2026 — Model Management PageHeader Synchronization
- [x] [fe] Synchronize Model Management headers with Design System PageHeader (ModelHubView, TrainingWizardView, TrainingRunDetailView)
- [x] [fe] Verify `npm run build` (`tsc -b && vite build`) in `usfds-web`

# 05-11-2026 — Investigation Front-end UI/UX Upgrade (SUC-17, SUC-18, SUC-20)
- [x] [fe] Upgrade `InvestigationModule.tsx` with `PageHeader`, breadcrumbs, project context, and view tabs
- [x] [fe] Modularize and upgrade `SUC-17` (`CaseQueueView`): elevated KPI cards, filter bar with reset, high-density queue table with score bars, assignee/timestamps, and `Claim` + `Investigate` actions
- [x] [fe] Modularize and upgrade `SUC-18` (`CaseWorkbenchView`): 3-column card layout, `common_hours_utc` baseline, enhanced SHAP/Timeline tooltips, searchable Key-Value snapshot, decoupled Resolution vs Workflow Actions (`Pending Customer` / `Escalate`), `Flag Noisy Rule` shortcut, and Auto-advance queue toggle
- [x] [fe] Upgrade `SUC-20` (`PoliciesView` & `RuleWorkspace.tsx`): summary stats, Blacklist management UI, Rule Feedback table with visual FPR bar, and `investigationDraft` banner in `RuleWorkspace.tsx`
- [x] [fe] Verify `npm run build` (`tsc -b && vite build`) in `usfds-web`

# 01-11-2026 — Training artifact priority
- [x] [core/tests] Prefer `model.joblib` over `model.json` as the primary XGBoost artifact; keep JSON as the final fallback

# 01-11-2026 — Detection / Investigation contract integration
- [x] [be/tests] Fix workbench query.days string parsing; verify default/30/90 accepted and other windows return 422
- [x] [be] One send-to-investigation endpoint writes fraud_cases via CaseService; public intake endpoint removed
- [x] [be] Production source resolved from detection_job_id/storage; no dataset_artifacts registration required
- [x] [be] Remove obsolete investigation_cases ORM/repository/writer/routes; schema migration preserves Case/blacklist/audit and prevents dropping populated legacy data
- [x] [fe] Consume accepted_count/skipped_event_ids and invalidate shared Investigation queries; remove obsolete case types/API
- [x] [docs/tests] Synchronize single-call contract; tests cover Detection -> Case Queue -> Workbench, retry, invalid/ALLOW events and file production

# 31-10-2026 — Investigation
- [x] [docs] Final scope: Case per transaction, blacklist only, shared audit, no bulk resolve
- [x] [core] Case, EntityBlacklist, AuditLog and repo interfaces
- [x] [core] Priority, case lifecycle, behavior profile, blacklist, rule feedback + focused tests
- [x] [infra] SQLAlchemy models + Sqlite repositories + tests
- [x] [server] `/api/v1/cases`, `/api/v1/blacklist` routers, schemas, DI + API test
- [x] [fe] Types, API client, project-scoped React Query queries/mutations
- [x] [fe] Case Queue view (KPIs, filters, table, claim, pagination)
- [x] [fe] Case Workbench (subject/baseline, evidence, timeline, deviation, resolution, audit)
- [x] [fe] Policies view (blacklist, rule feedback) + Rule Studio prefill/source artifact
- [x] [fe] `npm run build`; [be] 6 focused checks core/infra/server passed
- [x] [fe] Browser: live empty state, cached Case renders, two charts render, invalid decision disabled; mechanical UI detector clean
- [ ] [fe] Complete browser desktop/mobile mutation and Rule Studio handoff verification (shared browser route changed during checks; no real DB mutations performed)
- [x] [fe] Fix blank validation report page after schema mapping in DataPipelineWorkspace
	- [x] Fix navigation route in `DataPipelineWorkspace.tsx` from `/pipeline/step-validation` to `/workspace/step-validation`
	- [x] Add route alias `:datasetId/pipeline/:stepId` in `DataManagementPage.tsx`
- [x] [fe] Enable breadcrumb navigation in PageHeader and Detection views
	- [x] Update `PageHeader.tsx` to support `onClick` and `href` properties on breadcrumb items
	- [x] Add navigation to Detection Jobs hub on `DetectionResultExplorerView.tsx` and `DetectionJobWizardView.tsx`
- [x] [fe] Implement defensive optional chaining (`?.`) across DetectionResultExplorerView and unify single canonical schema (`lower`/`upper`)
	- [x] Backend `executor.py`: Output only 1 standard schema (`bin`, `lower`, `upper`, `count`, `flagged_count`), remove redundant alias fields
	- [x] Frontend `DetectionResultExplorerView.tsx`: Use optional chaining (`bin?.lower?.toFixed(1)`, `job?.score_threshold?.toFixed(2)`, `tx?.model_score?.toFixed(4)`) to prevent runtime crashes when backend properties are missing or undefined
	- [x] Verified `npm run build` in `usfds-web` and `pytest` in `usfds-server`
- [x] [core/server] Fix missing feature-engineered columns (`tx_freq_last_*h`, `tx_sum_last_*h`) during batch inference on RAW inputs
	- [x] [core] Persist `column_mapping` and `retained_columns` in `MAPPED` and `FEATURE_ENGINEERED` artifact `validation_report` (`mapping.py`, `feature_engineering_service.py`)
	- [x] [core] Bundle `fitted_feature_engineers.joblib` and `column_mapping.json` into model run directory during training (`training_payload.py`, `training_service.py`, `executor.py`)
	- [x] [core] Enhance `InferenceService._trace_model_version_lineage`, `BatchInferenceExecutor.prepare_and_validate_input`, `VelocityFeatureEngineer`, and `CreditCardFeatureEngineer` with model-run artifact lookup and raw column alias resolution
	- [x] [server] Backfill `fitted_feature_engineers.joblib` and `column_mapping.json` into `storage_output/models/00000000-0000-0000-0000-000000000001/runs/7c8efb2f-c403-4d1c-87f7-2fa254cc669d/`
	- [x] [tests] Add end-to-end test in `test_detection_api.py` covering RAW schema mapping (`transaction_time` -> `timestamp`) + Velocity Feature Engineering + Model Training + RAW Batch Detection
- [x] [fe] Fix null property crashes on failed/pending detection jobs in DetectionJobsHubView and DetectionResultExplorerView
	- [x] [fe] Update DetectionJobResponse types (`total_records`, `fraud_records`, `fraud_rate` as nullable)
	- [x] [fe] Guard `toLocaleString()` and `toFixed()` in DetectionJobsHubView and DetectionResultExplorerView
	- [x] [fe] Display `error_message` banner and failed status badge on failed detection jobs

# 29-10-2026
- [x] [detection] Implement Detection & Inference functions (`SUC-15`, `SUC-16`, `SUC-19`)
	- [x] [docs] Update Use Case Specification (`SUC-19`, `SUC-15`, `SUC-16`) in `docs/features/detection/inference/suc-spec.md` (`[26-10-29]`)
	- [x] [core] Upgrade `DetectionJob`, `BatchInferencePayload`, `BatchInferenceExecutor`, and `InferenceService` for Hybrid Detection (RAW `target_artifact_id` or `input_file_path`, `APPROVED` `ModelVersion` / `Rule-Only`, `ACTIVE` `Rule` evaluation, `REJECT`/`REVIEW`/`ALLOW` decision aggregation, results query, export, and `InvestigationCase` dispatch)
	- [x] [infra] Add `DetectionJobModel`, `InvestigationCaseModel`, `SqliteDetectionJobRepository`, and `SqliteInvestigationCaseRepository` in `usfds-infra`
	- [x] [server] Expose `/api/v1/detection` endpoints (`GET/POST /jobs`, `GET /jobs/{job_id}`, `GET /jobs/{job_id}/results`, `GET /jobs/{job_id}/export`, `POST /jobs/{job_id}/send-to-investigation`, `GET /cases`)
	- [x] [tests] Add unit and API tests for Hybrid Detection in `usfds-core/tests/test_inference_service.py` and `usfds-server/tests/test_detection_api.py`
	- [x] [fe] Update `src/types/detection.ts` and create `src/api/detectionApi.ts`
	- [x] [fe] Build `DetectionJobsHubView` (`SUC-19`), `DetectionJobWizardView` (`SUC-15`), `DetectionResultExplorerView` (`SUC-16`), and connect `InvestigationModule` to live dispatched cases
	- [x] [fe] Verify `pytest` suite and `usfds-web` TypeScript build
- [x] [fe] Fix infinite loop in DataPipelineWorkspace and SchemaMappingWorkspace
	- [x] [fe] Wrap onConfigChange handler in DataPipelineWorkspace with useCallback
	- [x] [fe] Decouple onConfigChange in SchemaMappingWorkspace with useRef
	- [x] [fe] Decouple onConfigChange in FeatureEngineeringWorkspace with useRef
- [x] [fe] Remove SUC-<number> from all UI elements
	- [x] [fe] ActivateModelModal.tsx: Remove SUC-10 and SUC-15
	- [x] [fe] ImportCustomModelModal.tsx: Remove SUC-17
	- [x] [fe] ModelHubView.tsx: Remove SUC-27 badge and SUC-15 text
	- [x] [fe] TrainingRunDetailView.tsx: Remove SUC-09 text and badge
	- [x] [fe] TrainingWizardView.tsx: Remove SUC-08 badge
	- [x] [fe] RuleDryRunWorkspace.tsx: Remove SUC-12 text
- [x] [docs] Update docs/bugs.md with resolved items
- [x] [fe] Verify usfds-web build (tsc -b && vite build)

# 22-10-2026
- [x] [core] Finish register_plugged_model in TrainingService.
- [x] [server] Expose training functions in `usfds-core` through APIs in `usfds-server`
- [x] [fe] Implement front-end for project management
	- [x] [docs] Draft Use Case Specification (`SUC-22` to `SUC-26`) in `docs/features/project_management/suc-spec.md`
	- [x] [fe] Create TypeScript interfaces (`src/types/project.ts`) and API client (`src/api/projectApi.ts`) for `/api/v1/projects`
	- [x] [fe] Implement `ProjectContext` & `useProject` hook for active project selection and CRUD/schema operations
	- [x] [fe] Build `ProjectManagementPage` (`/projects`), `ProjectFormModal`, and `ProjectSchemaDrawer` (inspect & reset `raw_schema`)
	- [x] [fe] Integrate `Topbar` Project Switcher with live projects, quick create modal, and `/projects` navigation
	- [x] [fe] Connect active `project_id` to `DataManagementPage` (`DatasetHubView`, `ImportDatasetModal`) and `RuleEnginePage` (`RuleCatalogView`, `RuleWorkspace`)
- [x] [fe] Implement front-end for training functions
	- [x] [docs] Update Use Case Specification (`SUC-08`, `SUC-09`, `SUC-10`, `SUC-17`, `SUC-27`) in `docs/features/detection/training/suc-spec.md`
	- [x] [core/server] Add `activate_model_version`, `.zip` plugin upload endpoint, `project_id` scoping for runs/versions, and unit tests in `tests/`
	- [x] [fe] Update TypeScript interfaces (`src/types/model.ts`) and create API client (`src/api/trainingApi.ts`) for `/api/v1/training`
	- [x] [fe] Build `ModelHubView` (`SUC-27`), `ImportCustomModelModal` (`SUC-17`), and `ActivateModelModal` (`SUC-10`)
	- [x] [fe] Build `TrainingWizardView` (`SUC-08`) and `TrainingRunDetailView` (`SUC-09`) with interactive Threshold Simulator & ROC/PR/Distribution charts
	- [x] [fe] Wire nested routes in `ModelTrainingPage.tsx` and verify build/tests
- [fe] Connect final step of data management to training run in model management
- [x] [fe] Integrate front-end rule management with back-end
	- [x] [docs] Update Use Case Specification (`SUC-11`, `SUC-12`, `SUC-13`, `SUC-14`, `SUC-18`) in `docs/features/detection/rule_management/suc-spec.md`
	- [x] [core/server] Add `RuleExecutor.backtest_dataframe` and `POST /api/v1/rules/backtest` endpoint for historical `DatasetArtifact` dry-run (`SUC-12`) with unit/API tests
	- [x] [fe] Update TypeScript interfaces (`src/types/rule.ts`) and `src/api/ruleApi.ts` (remove mock overrides, surface backend validation errors, add `backtestRule` & `evaluateProjectRules`)
	- [x] [fe] Connect `RuleCatalogView` (`SUC-18`, `SUC-14`), `RuleWorkspace`, `RuleStudioWorkspace`, and `RuleClauseRow` (`SUC-11`) to live backend APIs and active project `raw_schema` (`BR-PM-04`, `BR-PM-05`)
	- [x] [fe] Connect `RuleDryRunWorkspace` (`SUC-12`) to real project `DatasetArtifact` backtesting and single-transaction evaluation (`/evaluate`)
	- [x] [fe] Verify backend `pytest` suite and `usfds-web` TypeScript build
