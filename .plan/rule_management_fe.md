# Plan: Rule Management Use Case Specification & Front-End Integration

## 1. Context & Facts
- **Specifications (`docs/features/detection/rule_management/suc-spec.md`)**:
	- Currently lists `SUC-11`, `SUC-12`, `SUC-13` (deferred/advanced), `SUC-14`, and `SUC-18` (`View rules`) in the summary table, but lacks the detailed section for `SUC-18`.
	- `SUC-11`, `SUC-12`, and `SUC-14` still reference legacy concepts (`CompositeCondition`/`SingleCondition`, `mapped.*`/`feature.*`/`model.*`, `priority`, `risk_weight`, `RuleAction: ALERT/SCORE_BOOST/PASS`) instead of the implemented `Rule` + `RuleVersion` architecture (`JsonLogic` AST, `RuleAction: ALLOW | REVIEW | REJECT`, `RuleStatus: DRAFT | ACTIVE | INACTIVE`, and `project.raw_schema` validation `BR-PM-04` & `BR-PM-05`).
- **Backend APIs (`usfds-core` & `usfds-server`)**:
	- Existing endpoints in `usfds-server/src/usfds_server/routers/rule_router.py` (`/api/v1/rules`):
		- `POST /api/v1/rules`: Create rule + initial `RuleVersion` (v1).
		- `GET /api/v1/rules`: List rules by `project_id` with optional `status` filter.
		- `GET /api/v1/rules/{rule_id}`: Get rule details with `current_version`.
		- `PUT /api/v1/rules/{rule_id}`: Update rule metadata or `condition`/`action` (auto-increments `RuleVersion`).
		- `PATCH /api/v1/rules/{rule_id}/status`: Toggle status (`ACTIVE | INACTIVE | DRAFT`).
		- `GET /api/v1/rules/{rule_id}/versions`: Get full historical version audit trail.
		- `DELETE /api/v1/rules/{rule_id}`: Delete rule and all its versions.
		- `POST /api/v1/rules/{rule_id}/evaluate`: Evaluate single rule against a transaction context.
		- `POST /api/v1/rules/evaluate-batch`: Evaluate all active rules in a project against a transaction context.
	- Missing Backend Capability for `SUC-12` (Dataset Backtest / Dry-Run):
		- `RuleExecutor.backtest_rule(...)` in `usfds-core` & `POST /api/v1/rules/backtest` in `usfds-server` to evaluate a rule (by `rule_id` or ad-hoc `condition` + `action`) against a project's `DatasetArtifact` (`RAW`, `MAPPED`, or `FEATURE_ENGINEERED`), returning total rows evaluated, triggered count, hit rate, execution time, `has_ground_truth`, `tp`/`fp`/`tn`/`fn`, `precision`/`recall`/`fpr`, `fraud_amount_caught`, and sample triggered transactions (`sample_hits`).
- **Frontend (`usfds-web`)**:
	- `ruleApi.ts` currently falls back to `SAMPLE_MOCK_RULES` whenever `res.data.length === 0` (preventing empty projects from showing empty state) and swallows backend validation errors (`400 Bad Request` from `BR-PM-04` / `BR-PM-05`).
	- `RuleClauseRow.tsx` uses static `AVAILABLE_FEATURE_FIELDS` instead of dynamically populating columns from `currentProject.raw_schema.columns` (which causes `BR-PM-05` validation errors when saving rules on real projects).
	- `RuleDryRunWorkspace.tsx` uses hardcoded `SAMPLE_TRANSACTIONS` and static KPI metrics instead of calling the backend Dataset Backtest API and Single-Transaction Evaluation API (`/evaluate`).

## 2. Proposed Execution Steps
1. **Update Use Case Specification (`docs/features/detection/rule_management/suc-spec.md`)**:
	- Add detailed specification for `SUC-18: View rules & version history`.
	- Update `SUC-11: Create & update rule`, `SUC-12: Test rule (Dry-run & Backtest)`, and `SUC-14: Activate rule` to align with `Rule` + `RuleVersion`, `JsonLogic`, `project.raw_schema` governance (`BR-PM-04`, `BR-PM-05`), and keep `SUC-13` marked as deferred/advanced.
	- Annotate with `[26-10-25]`.
2. **Backend Dataset Backtest (`usfds-core` & `usfds-server`)**:
	- Add `RuleBacktestSampleHit` and `RuleBacktestResult` schemas in `usfds_core/domain/schemas/rule_schemas.py` and `RuleExecutor.backtest_dataframe(...)` in `usfds_core/services/rule_engine/executor.py`.
	- Add `POST /api/v1/rules/backtest` in `rule_router.py` and DTOs in `rule_api_schemas.py` (loads the target `DatasetArtifact` parquet/csv from `IFileStorage`, validates `project_id`, runs `RuleExecutor.backtest_dataframe`, and returns telemetry + sample hits).
	- Add unit and API tests in `usfds-core/tests/test_rule_engine.py` and `usfds-server/tests/test_rule_api.py`.
3. **Frontend API Client & Types (`usfds-web/src/types/rule.ts`, `usfds-web/src/api/ruleApi.ts`)**:
	- Add TypeScript interfaces for `BacktestRuleRequest`, `RuleBacktestSampleHit`, `RuleBacktestResultResponse`, and `EvaluateRulesRequest`.
	- Remove silent mock fallbacks in `ruleApi.ts` so real API responses (including empty lists `[]` and `400 Bad Request` schema validation errors) are surfaced accurately to the UI, and add `backtestRule` and `evaluateProjectRules` methods.
4. **Frontend UI Integration (`usfds-web/src/components/modules/rule/*`)**:
	- Connect `RuleStudioWorkspace`, `RuleGroupCard`, `RuleClauseRow`, and `jsonLogicParser.ts` to `currentProject.raw_schema` so field dropdowns prioritize the active project's locked RAW schema columns (with appropriate `LogicalDataType` -> operator/input mapping) and display a clear warning banner when `raw_schema` is unlocked (`BR-PM-04`).
	- Surface backend validation/error banners and status transitions in `RuleCatalogView.tsx` (`SUC-18`, `SUC-14`) and `RuleWorkspace.tsx` (`SUC-11`, `SUC-14`).
	- Connect `RuleDryRunWorkspace.tsx` (`SUC-12`) to real project datasets/artifacts via `datasetApi` and `ruleApi.backtestRule`, displaying real KPI telemetry, sample hits, AST inspection modal, plus an interactive Single-Transaction Evaluator tab/drawer calling `ruleApi.evaluateSingleRule`.
5. **Verification**:
	- Run `pytest` on `usfds-core` and `usfds-server` rule tests.
	- Run `npm run build` in `usfds-web` to verify zero TypeScript/build errors.

## 3. Success Criteria
- [x] `docs/features/detection/rule_management/suc-spec.md` updated with `SUC-18`, `SUC-11`, `SUC-12`, `SUC-13` (deferred), `SUC-14` (`[26-10-25]`).
- [x] `POST /api/v1/rules/backtest` implemented and tested in `usfds-core` and `usfds-server`.
- [x] `ruleApi.ts` and all Rule Management UI views (`RuleCatalogView`, `RuleWorkspace`, `RuleStudioWorkspace`, `RuleDryRunWorkspace`, `RuleVersionHistoryModal`) integrated end-to-end with live backend APIs and `project.raw_schema`.
- [x] All backend unit tests and `usfds-web` build pass with zero errors.
