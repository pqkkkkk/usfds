# Plan: Detection & Inference Use Case Specification & End-to-End Implementation

## 1. Context & Approved Decisions
- **Specifications (`docs/features/detection/inference/suc-spec.md`)**:
	- Standardize `SUC-15` (**Start detection job**), `SUC-16` (**View detection result**), and add detailed specification for `SUC-19` (**View detection jobs**).
	- Align with the implemented USFDS architecture:
		- **Input Data Source (Dual-Option)**:
			1. **Option 1 (`target_artifact_id`)**: Select an existing `DatasetArtifact` in the project that **MUST be at stage `RAW`** (`pipeline_stage == PipelineStage.RAW`).
			2. **Option 2 (`input_file_path`)**: Provide a direct local/server file path (`.csv`, `.parquet`, `.pq`, `.json`) or pick a file directly via the UI file picker (`window.electronAPI.openFileDialog` / drag-and-drop). The file is validated against `project.raw_schema` (`allow_missing_target=True`).
		- **AI Engine (`ModelVersion`)**: Select an `APPROVED` `ModelVersion` (or `Rule-Only` mode without AI model). Lineage is automatically traced back via `ModelVersion.run_id -> RunDataset -> DatasetArtifact` to resolve `fitted_engineers` (`FEATURE_ENGINEERED`), `preprocessor.joblib` / `fitted_pipeline.joblib`, and `column_mapping` (`MAPPED`) so the `RAW` input data is automatically mapped, cleansed, feature-engineered, and normalized before inference.
		- **Rule Engine (`Rule` + `RuleVersion`)**: Evaluates all `ACTIVE` project rules using `JsonLogicEvaluator` / `RuleExecutor`.
		- **Decision Aggregation (`BR-DT-07`)**:
			- If any triggered `ACTIVE` rule has `action = REJECT` $\rightarrow$ `final_action = REJECT`.
			- Else if any triggered `ACTIVE` rule has `action = REVIEW` OR (`model_score >= score_threshold`) $\rightarrow$ `final_action = REVIEW`.
			- Else $\rightarrow$ `final_action = ALLOW`.
			- Flagged transactions are those with `final_action in (REJECT, REVIEW)`.
		- **Send to Investigation (`SUC-16`)**: Persist selected flagged transactions into `investigation_cases` table (SQLite) with full detection context (`job_id`, `event_id`, `user_id`, `amount`, `model_score`, `triggered_rules`, `final_action`, `condition_snapshot`) and navigate to `/investigation`.
- **Assumptions**:
	- Existing `InferenceService.online_inference` and `InferenceService.batch_inference` (using `IPipelineRepository` and `deployment_id`) are preserved for backward compatibility with existing unit tests (`test_inference_service.py`).
	- New project-scoped hybrid detection orchestration methods (`start_detection_job`, `list_detection_jobs`, `get_detection_job`, `get_detection_job_results`, `export_detection_job_results`, `send_to_investigation`) are added to `InferenceService` (and exposed under `/api/v1/detection`).

## 2. Proposed Execution Steps
1. **Update Documentation (`docs/features/detection/inference/suc-spec.md`)**:
	- Add detailed specification for `SUC-19: View detection jobs`.
	- Update `SUC-15: Start detection job` and `SUC-16: View detection result` to match the approved hybrid detection architecture (`ModelVersion` `APPROVED` + `Rule` `ACTIVE` + `REJECT / REVIEW / ALLOW` + `investigation_cases` dispatch).
	- Append `[26-10-29]` tag upon user approval.
2. **Core Domain & Hybrid Detection Engine (`usfds-core`)**:
	- Extend `DetectionJob` entity (`usfds_core/domain/entities/detection.py`) with optional fields (`target_artifact_id`, `model_version_id`, `score_threshold`, `use_rules`, `summary_metrics` dict) while keeping `deployment_id` optional/defaulted so legacy callers remain 100% compatible.
	- Extend `BatchInferencePayload` and `BatchInferenceResult` (`usfds_core/domain/schemas/inference_payload.py`) to carry `active_rules` (list of rule snapshots: `rule_id`, `rule_code`, `rule_name`, `version_number`, `action`, `condition`), `use_rules`, `model_artifact_uri` (optional for Rule-Only mode), and `summary_metrics` (`reject_count`, `review_count`, `allow_count`, `rule_trigger_breakdown`, `score_distribution`, `amount_at_risk`).
	- Update `BatchInferenceExecutor.run()` (`usfds_core/services/inference/executor.py`) to support:
		- Optional AI model scoring (when `model_artifact_uri` is provided) producing `model_score` (`0.0 - 1.0`).
		- Batch evaluation of `active_rules` via `JsonLogicEvaluator` producing per-row `triggered_rules` (JSON/list of codes), `triggered_rule_details` (JSON with `matched_clauses`), `rule_action`, and `final_action` (`REJECT`, `REVIEW`, `ALLOW`).
		- Saving enriched `predictions.parquet` and computing `summary_metrics`.
	- Add `start_detection_job`, `get_detection_job_results`, `export_detection_job_results`, and `dispatch_cases_to_investigation` in `InferenceService`.
3. **Infrastructure Persistence (`usfds-infra`)**:
	- Add `DetectionJobModel` and `InvestigationCaseModel` in `usfds_infra/database/models.py`.
	- Implement `SqliteDetectionJobRepository` and `SqliteInvestigationCaseRepository` in `usfds_infra/database/repositories.py` (and `InMemoryInvestigationCaseRepository` in `in_memory_repos.py`).
4. **REST API Endpoints (`usfds-server`)**:
	- Create `usfds_server/schemas/detection_api_schemas.py` and `usfds_server/routers/detection_router.py` (`/api/v1/detection`):
		- `GET /api/v1/detection/jobs`: List detection jobs for a `project_id` (`SUC-19`).
		- `POST /api/v1/detection/jobs`: Start a hybrid batch detection job (`SUC-15`).
		- `GET /api/v1/detection/jobs/{job_id}`: Get detection job metadata & summary (`SUC-16`, `SUC-19`).
		- `GET /api/v1/detection/jobs/{job_id}/results`: Query paginated/filtered transaction detection results, score distribution, rule trigger breakdown, and evidence snapshots (`SUC-16`).
		- `GET /api/v1/detection/jobs/{job_id}/export`: Export detection results as `.csv` or `.parquet` (`SUC-16`).
		- `POST /api/v1/detection/jobs/{job_id}/send-to-investigation`: Create `InvestigationCase` records for selected transactions (`SUC-16`).
		- `GET /api/v1/detection/cases`: List created `InvestigationCase` records for the project.
	- Register `detection_router` in `usfds_server/api.py` and wire dependencies in `usfds_server/dependencies.py`.
5. **Frontend Implementation (`usfds-web`)**:
	- Update `src/types/detection.ts` and create `src/api/detectionApi.ts` (exported in `src/api/index.ts`).
	- Build Detection UI components in `src/components/modules/detection/`:
		- `DetectionJobsHubView.tsx` (`/detection` - `SUC-19`): KPI summary cards, search & status filter, jobs table with engine badges, flagged rate, action breakdown, and quick navigation to results or new job wizard.
		- `DetectionJobWizardView.tsx` (`/detection/new` - `SUC-15`): 3-step workspace (`1. Target Dataset Artifact`, `2. Hybrid Engine Config (Approved ModelVersion / Rule-Only + Active Ruleset)`, `3. Decision Threshold & Launch`).
		- `DetectionResultExplorerView.tsx` (`/detection/jobs/:jobId` - `SUC-16`): Summary cards (`REJECT`, `REVIEW`, `ALLOW`, `Flagged Rate`, `Amount at Risk`), Score Distribution chart & Rule Trigger Breakdown, filterable Transaction Detection Table, slide-over **Detection Evidence Drawer** (Model Score + Matched Rule Clauses + Feature Snapshot), Export `.csv`/`.parquet`, and **Send to Investigation** modal/action.
	- Update `DetectionJobModule.tsx` / `DetectionJobPage.tsx` with nested routes (`/detection`, `/detection/new`, `/detection/jobs/:jobId`) and connect `InvestigationModule.tsx` to display the dispatched investigation cases from `/api/v1/detection/cases`.
6. **Verification & Testing**:
	- Add unit and API tests in `usfds-core/tests/test_inference_service.py` and `usfds-server/tests/test_detection_api.py`.
	- Run `pytest` across backend packages and `npm run build` in `usfds-web`.

## 3. Verifiable Success Criteria
- [ ] `docs/features/detection/inference/suc-spec.md` updated with `SUC-19`, `SUC-15`, `SUC-16` and annotated with `[26-10-29]`.
- [ ] Hybrid batch detection (`ModelVersion` + `Active Rules` + `Rule-Only` mode) executes end-to-end and persists `DetectionJob` & `predictions.parquet`.
- [ ] `/api/v1/detection/*` endpoints pass all unit and integration tests.
- [ ] Frontend `/detection` supports viewing jobs (`SUC-19`), launching jobs (`SUC-15`), inspecting results & evidence drawer, exporting files, and dispatching cases to `/investigation` (`SUC-16`), building with zero TypeScript errors.
