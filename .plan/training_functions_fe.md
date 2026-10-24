# Plan: Model Training Use Case Specification & Front-End Implementation

## 1. Context & Facts
- **Specifications (`docs/features/detection/training/suc-spec.md`)**:
	- Contains `SUC-08`, `SUC-09`, `SUC-10`, and an empty stub for `SUC-17`.
	- Needs a dedicated Use Case `SUC-27: View models & training runs` for the Model Registry & Training Runs Hub (`D1`).
	- `SUC-08` and `SUC-09` contain draft `*(review: ...)*` comments that must be resolved: remove manual preprocessing configuration from `SUC-08` (handled via Model-Owned Normalization `preprocessor.joblib`) and remove SHAP from `SUC-09` (focusing on KPI Metrics, ROC/PR Curves, Score Distribution, and Interactive Threshold Slider from `MetricEvaluator`).
	- `SUC-10: Activate model` needs to reflect independent activation of `ModelVersion` (`APPROVED` status + `decision_threshold` update) with artifact checksum/existence verification.
	- `SUC-17: Import custom model` needs full specification matching the 2-stage validation pipeline (Static AST Check + Dynamic Dry-Run) for both `.zip` upload and local path (`model_artifact_path`), plus optional `manifest_override`.
- **Backend APIs (`usfds-core` & `usfds-server`)**:
	- Existing endpoints in `usfds-server/src/usfds_server/routers/training_router.py` (`/api/v1/training`):
		- `POST /api/v1/training/models/plugins`: Validate and register custom plugin via JSON `model_artifact_path`.
		- `GET /api/v1/training/models`: List models (`project_id` filter).
		- `GET /api/v1/training/models/{model_id}`: Get model details.
		- `GET /api/v1/training/models/{model_id}/versions`: List versions for a model.
		- `GET /api/v1/training/versions/{version_id}`: Get version by ID.
		- `POST /api/v1/training/runs`: Start training run (`model_id`, `dataset_artifact_id`, `hyperparameters`, `run_name`).
		- `GET /api/v1/training/runs`: List training runs (`model_id` filter).
		- `GET /api/v1/training/runs/{run_id}`: Get training run details & evaluation metrics.
	- Missing / Required Backend Enhancements for `SUC-10`, `SUC-17`, and `SUC-27`:
		- Propagate `project_id` onto `TrainingRun` and `ModelVersion` during `prepare_and_dispatch` / `handle_training_completion`, and support `project_id` filtering on `GET /api/v1/training/runs`.
		- `POST /api/v1/training/models/plugins/upload`: Accept `multipart/form-data` `.zip` file upload (plus optional `project_id`, `user_id`, `manifest_override_json`) calling `service.register_plugged_model(zip_bytes=...)`.
		- `POST /api/v1/training/versions/{version_id}/activate`: Independently activate a `ModelVersion` (verify artifact existence & SHA-256 checksum, update `decision_threshold` if provided, and set `status = ModelVersionStatus.APPROVED`).

## 2. Proposed Execution Steps
1. **Update Use Case Specification (`docs/features/detection/training/suc-spec.md`)**:
	- Standardize `SUC-08`, `SUC-09`, `SUC-10`.
	- Complete `SUC-17: Import custom model`.
	- Add `SUC-27: View models & training runs`.
	- Append `[26-10-24]` modification tag upon user approval.
2. **Backend Completions (`usfds-core` & `usfds-server`)**:
	- In `TrainingOrchestrationService`:
		- Set `project_id = artifact.project_id` on `TrainingRun` and `ModelVersion`; add `project_id` filter to `list_training_runs()`.
		- Implement `activate_model_version(version_id, decision_threshold=None)`: verify artifact existence and SHA-256 checksum in `file_storage`, update `decision_threshold`, and set `status = ModelVersionStatus.APPROVED`.
	- In `training_router.py` & `training_api_schemas.py`:
		- Add `project_id` query param to `GET /api/v1/training/runs` and include `dataset_artifact_id` in `TrainingRunResponse`.
		- Add `POST /api/v1/training/models/plugins/upload` (`UploadFile` `.zip` + optional form fields).
		- Add `POST /api/v1/training/versions/{version_id}/activate` (`ActivateModelVersionRequest` with optional `decision_threshold`).
3. **Frontend Types & API Client (`usfds-web`)**:
	- Update `usfds-web/src/types/model.ts` with TypeScript interfaces matching backend schemas (`ModelResponse`, `ModelVersionResponse`, `TrainingRunResponse`, `ThresholdGridPoint`, `RecommendedThresholds`, `RocCurveData`, `PrCurveData`, `ScoreDistributionData`, `ModelPluginManifest`, `RegisterPluggedModelRequest`, `StartTrainingRunRequest`, `ActivateModelVersionRequest`).
	- Create `usfds-web/src/api/trainingApi.ts` and export in `usfds-web/src/api/index.ts`.
4. **Frontend UI Components (`usfds-web`)**:
	- `ModelHubView.tsx` (`/models` - `SUC-27`):
		- KPI summary cards (Total Runs, Completed/Active Versions, Registered Models, Best PR-AUC).
		- Tabs: **Training Runs** (filter by status/model, status badges, PR-AUC/F1/Precision/Recall, quick actions `View Result`, `Activate`) & **Model Registry** (list `BUILTIN` and `SCRIPT` models, expandable `ModelVersion` rows with `semver`, `checksum_sha256`, `decision_threshold`, `status`, and `Activate` button).
		- Header CTAs: `[ + Import Custom Model ]` and `[ + New Training Run ]`.
	- `ImportCustomModelModal.tsx` (`SUC-17`):
		- Supports switching between **Upload `.zip` Package** (`multipart/form-data`) and **Local Path** (`model_artifact_path` with native Electron file/folder picker support).
		- Optional **Manifest Override** section (`model_name`, `display_name`, `framework`, `data_modality`, `data_format`, `default_hyperparameters` JSON).
		- Displays 2-Stage Validation feedback (Static AST + Dynamic Dry-Run errors if rejected).
	- `TrainingWizardView.tsx` (`/models/train` - `SUC-08`):
		- Step 1: Select Dataset & `FEATURE_ENGINEERED` / `PRE_PROCESSED` Artifact (scoped to `currentProject.project_id`, supports `?artifactId=...` query prefill).
		- Step 2: Select Target Model from Registry (`BUILTIN` or `SCRIPT`) & configure `hyperparameters` dynamically from `hyperparameter_schema` / `default_hyperparameters` (with JSON editor toggle and Reset to Defaults).
		- Step 3: Review & Launch (`run_name`, summary, dispatch run, navigate to `/models/runs/:runId`).
	- `TrainingRunDetailView.tsx` (`/models/runs/:runId` - `SUC-09`):
		- Header with Lineage Metadata (`run_name`, `model`, `semver`, `status`, `duration_seconds`, `dataset_artifact_id`) and `[ Activate Model ]` button.
		- Failed Run View: Execution Error Log + `[ Retry Training ]`.
		- Succeeded Run View:
			- Core KPI Cards (`ROC-AUC`, `PR-AUC`, `F1-Score`, `F2-Score`, `Precision`, `Recall`, `Accuracy`).
			- Interactive Decision Threshold Simulator: Slider (`0.01` to `0.99`) + preset buttons (`Best F1`, `Best F2`, `Youden J`, `Recall >= 90%`, `Recall >= 95%`) dynamically updating the 2x2 Confusion Matrix (`TP`, `FP`, `TN`, `FN`) and threshold metrics from `threshold_tuning_grid`.
			- Visual Charts: `ROC Curve`, `Precision-Recall Curve`, and `Score Distribution Histogram` (Legit vs Fraud with active threshold marker).
			- Configuration & Artifact Metadata (`hyperparameters` JSON, `checksum_sha256`, `artifact_uri`).
	- `ActivateModelModal.tsx` (`SUC-10`):
		- Confirmation modal displaying model name, `semver`, `checksum_sha256`, selected `decision_threshold` (editable, pre-filled from Threshold Simulator or `recommended_threshold`), and triggering `POST /api/v1/training/versions/{version_id}/activate`.
	- Update `ModelTrainingPage.tsx` with nested routes (`/models`, `/models/train`, `/models/runs/:runId`).
5. **Verification & Tests**:
	- Add backend unit/API tests in `tests/` for `activate_model_version`, `.zip` plugin upload, and `project_id` filtering on runs.
	- Run `pytest` and `npm run build` in `usfds-web` to verify zero TypeScript/build errors.

## 3. Success Criteria
- [x] `docs/features/detection/training/suc-spec.md` approved and updated with `SUC-08`, `SUC-09`, `SUC-10`, `SUC-17`, and `SUC-27` (`[26-10-24]`).
- [x] Backend supports `POST /api/v1/training/versions/{version_id}/activate`, `POST /api/v1/training/models/plugins/upload`, and project-scoped training runs.
- [x] Frontend `/models` implements `SUC-27`, `SUC-08`, `SUC-09`, `SUC-10`, and `SUC-17` end-to-end against live `/api/v1/training` endpoints.
- [x] All backend unit tests and `usfds-web` TypeScript build pass with zero errors.
