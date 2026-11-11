# Plan: AutoML (Optuna Bayesian Optimization) Integration into Model Training Flow

> **Notion Document:** [Tích hợp autoML vào luồng huấn luyện mô hình (`TASK-113`)](https://app.notion.com/p/T-ch-h-p-autoML-v-o-lu-ng-hu-n-luy-n-m-h-nh-413b99c6a9508045a01bddf734e4614a)

## 1. Context & Approved Architectural Decisions
- **Mandatory Step in `SUC-08`:** Bayesian Optimization (powered by `optuna` TPE — Tree-structured Parzen Estimator) is a mandatory step in every model training run (`SUC-08: Start model training`).
- **Universal Model Support (`BUILTIN` & `SCRIPT`):**
	- **`BUILTIN` Models (`random_forest`, `xgboost`):** Jointly optimize preprocessing pipeline steps (`SimpleImputer`, `Scaler`, `CategoricalEncoder`, `DimReduction`, `Resampling`, and engineered feature group selection via `PreprocessingPipelineBuilder`) AND model estimator hyperparameters (`model.hyperparameter_schema`).
	- **`SCRIPT` Plugin Models (`custom-models/`, LSTM, 2D-CNN, GNN):** Optimize all hyperparameters (including plugin-owned preprocessing and architecture parameters) declared in `plugin_manifest.json` (`hyperparameter_schema`) within a single `_usfds_runner.py` subprocess execution.
- **Anti-Leakage Temporal Validation & Final Refit:**
	- Split `train_enriched.parquet` chronologically (`1 - val_split_ratio` `sub_train` / `val_split_ratio` `val_holdout`) to evaluate each Optuna trial on the chosen `optimization_metric` (`pr_auc`, `f2_score`, `f1_score`, `roc_auc`).
	- After completing `n_trials`, refit the best discovered preprocessing pipeline and model hyperparameters on 100% of `train_enriched.parquet`, save `preprocessor.joblib` and `model.joblib` (or `model_bundle.zip`), and run `MetricEvaluator.evaluate()` once on `test_enriched.parquet`.

## 2. Implementation Steps
1. **Phase 1 — Core Domain & Optuna Bayesian Engine (`usfds-core`)**:
	- Add `optuna>=3.6.0` to `usfds-core/pyproject.toml`.
	- Extend `usfds_core/domain/schemas/training_config.py` with `OptimizationMetric`, `AutoMLConfig`, and attach `automl_config: AutoMLConfig` to `TrainingRunConfig`.
	- Extend `usfds_core/domain/schemas/training_payload.py` (`TrainingRunPayload`) with `automl_config` and `hyperparameter_schema`.
	- Enhance `PreprocessingPipelineBuilder` (`usfds_core/services/preprocessing/pipeline_builder.py`) to embed `SimpleImputer` in numeric/categorical branches and support optional column dropping (`ColumnDropperTransformer`) while preserving 100% compatibility with `BatchInferenceExecutor.run()`.
	- Create `usfds_core/services/training/automl/bayesian_optimizer.py` implementing `BayesianPipelineOptimizer` (Optuna TPE study, chronological train/val split with stratified fallback on single-class edge cases, joint preprocessing + model hyperparameter sampling, parameter importance computation, and final refit).
	- Update `BuiltinModelTrainer` (`builtin_trainer.py`), `ScriptPluginTrainer` (`script_trainer.py`), `_usfds_runner.py` (`runner_template.py`), `ModelPluginValidator` (`validator.py` with `n_trials=1` dry-run), `TrainingRunExecutor` (`executor.py`), and `TrainingOrchestrationService` (`training_service.py`).
2. **Phase 2 — Backend API & Built-in Model Seeding (`usfds-server`)**:
	- Add `automl_config` to `StartTrainingRunRequest` in `usfds_server/schemas/training_api_schemas.py` and wire it in `usfds_server/routers/training_router.py`.
	- Enrich `seed_builtin_models()` in `usfds_server/dependencies.py` with comprehensive search space schemas (`minimum`, `maximum`, `enum`) for `random_forest` and `xgboost`.
3. **Phase 3 — Frontend Wizard & Results Visualization (`usfds-web`)**:
	- Update `usfds-web/src/types/model.ts` with `AutoMLConfig`, `AutoMLSummary`, `AutoMLTrialRecord`, and `StartTrainingRunRequest`.
	- Update `TrainingWizardView.tsx` (`/models/train` — `SUC-08`) Step 2 & Step 3 to configure Optuna Bayesian Optimization (`optimization_metric`, `n_trials`, `timeout_seconds`, `optimize_preprocessing`, and per-parameter Auto-Tune Range vs. Pinned Fixed Value).
	- Update `TrainingRunDetailView.tsx` (`/models/runs/:runId` — `SUC-09`) to display the AutoML Optimization Report (Best Validation Score, Convergence Chart across trials, Best Discovered Preprocessing Pipeline & Model Hyperparameters, Parameter Importances, and Trials History Table).
4. **Phase 4 — Verification & Unit Tests (`tests/`)**:
	- Add unit tests in `usfds-core/tests/training/` verifying joint preprocessing + model Bayesian optimization for `BUILTIN` and `SCRIPT` models and end-to-end compatibility with `BatchInferenceExecutor`.
	- Run `pytest` across `usfds-core` and `npm run build` in `usfds-web`.

## 3. Verifiable Success Criteria
- [ ] Notion page `TASK-113` updated and approved by user.
- [ ] `BuiltinModelTrainer` and `ScriptPluginTrainer` execute mandatory Optuna TPE Bayesian Optimization on chronological validation split and refit on full training set.
- [ ] `metrics.json` and `TrainingRun.custom_metrics["automl"]` contain `best_validation_score`, `best_preprocessing_config`, `best_hyperparameters`, `param_importances`, and `trials_history`.
- [ ] `usfds-core` unit tests and `usfds-web` TypeScript build pass with zero errors.

