# Plan: Vietnamese UI copy in usfds-web

> **Task ID:** `ui_vietnamese_localization` (= this file name) · **Issues:** ISS-005 (one task, no split, user decision 26-11-14) · **Spec:** — (no copy spec; glossary in §2) · **Notion:** —
> **Conflict verdict:** PARALLEL-SAFE (overlap with planned RBAC noted in §4) · **Status:** Approved (26-11-14) — milestones checkpoint-approved one by one

## 1. Context (facts)
- No i18n layer. `usfds-web/package.json` has no i18n dependency; strings are hardcoded in JSX. Decision: no i18n library (user, 26-11-14).
- Mixed copy, both directions:
  - English: `usfds-web/src/components/modules/data_management/DatasetHubView.tsx:69,82,97,101` (`Import Dataset`, `Total Managed Datasets`, `Model-Ready Datasets`).
  - Vietnamese: `usfds-web/src/hooks/useDatasetPipeline.ts:183,245` (`alert(...)`).
  - Sidebar module labels are English: `usfds-web/src/components/layout/Sidebar.tsx:38,44,50,56,62,68,74`.
  - Topbar and modal copy is English: `usfds-web/src/components/layout/Topbar.tsx:71,89,95,114,193,204,221`, `OmnisearchModal.tsx:32-37,49,60,112`.
- Number/date locale is inconsistent:
  - `usfds-web/src/utils/formatters.ts:18` `formatNumber` uses `en-US`.
  - `usfds-web/src/utils/formatters.ts:33` `formatDate` returns `'N/A'`; `:36` uses `vi-VN`.
  - `usfds-web/src/components/modules/model/ModelHubView.tsx:483,669` call `toLocaleString('vi-VN')` directly (already correct; left as is).
- Existing rule: `.claude/skills/usfds-frontend-change/SKILL.md` ("UI text is Vietnamese (ISS-005)") covers only new or changed code. This task converts the existing code.
- Scale: ~111 non-test `.ts/.tsx` files under `usfds-web/src` (~20k lines of TSX). The 26-11-14 facts estimate ~60–65% of UI text is English.
- Test impact: `usfds-web/src/components/modules/investigation/PoliciesView.test.tsx:38` asserts an English label. It is updated in the milestone that translates that module (M3). Existing tests are updated, never deleted.

## 2. Goal, scope verdict & non-goals
- **Goal:** every user-visible string in `usfds-web/src` (non-test) is Vietnamese, in Vietnamese (only hard-to-translate terms get `Vietnamese (English)`, see R1), and the web suite stays green.
- **Scope:** OK. One task, five milestones, one checkpoint approval per milestone (user decision 26-11-14: no split, approve each milestone before the next).
- **Non-goals / omitted:**
  - No i18n library and no `en`/`vi` switch.
  - No change to API payloads, enum values, route paths, or backend strings.
  - No layout redesign. Only fixes needed for longer Vietnamese labels (truncation, wrapping) are in scope; each one is listed in the report.
  - No edits under `docs/` (agent policy needs approval; not needed here).
  - No edits to `CHANGELOG.md`, `.plan/BOARD.md`, or `docs/issues/` in this branch (merge-time only).
- **Copy rules (user decision 26-11-14):**
  - R1 **Hard-to-translate terms** (ML metrics and terms with no exact Vietnamese equivalent, e.g. `Recall`, `PR-AUC`, `ROC-AUC`, `Precision`): `Vietnamese term (English term)`, e.g. `Độ chính xác (Precision)`. Applied only to these; every other term is Vietnamese only (user decision, 26-11-14, revised from the earlier all-terms version). Current list: `Precision`. Extend it only with the user's approval.
  - R2 **Everything else** (module names, headings, buttons, labels, status words, sub-labels, placeholders, tooltips, `aria-label`, empty states, toasts, alerts, errors, hints): Vietnamese only. Example: `Quản lý dữ liệu`, `Nhập tập dữ liệu`, `Chạy kỹ nghệ đặc trưng`.
  - R3 **Acronyms, proper names and technical nouns kept in English** (`USFDS`, `F1`, `JSON`, `CSV`, `SHAP`, `API`, `PII`, `Apache Parquet`, `Artifact`). No parentheses. `Artifact` is an assumption, see §8.
  - R3 **Acronyms and proper names** (`USFDS`, `F1`, `JSON`, `CSV`, `SHAP`, `API`) stay as they are, with no parentheses. Assumption, reviewed at M1.
  - R4 `formatNumber` switches to `vi-VN` (`1.234.567`). `formatDate` placeholder is `Không có`.
- **Glossary (draft; R2 applies unless the term is on the R1 list):**

| English | Copy (R2 unless noted) | Used in |
|---|---|---|
| Data Management | Quản lý dữ liệu | Sidebar, Omnisearch |
| Model Management | Quản lý mô hình | Sidebar, Omnisearch |
| Rule Management | Quản lý luật | Sidebar, Omnisearch |
| Detection | Phát hiện gian lận | Sidebar, Omnisearch |
| Investigation | Điều tra | Sidebar, Omnisearch |
| Insight & Report | Phân tích & Báo cáo | Sidebar, Omnisearch |
| Project Settings | Cài đặt dự án | Sidebar |
| Project | Dự án | Topbar |
| Search | Tìm kiếm | Topbar, Omnisearch |
| Notifications | Thông báo | Topbar |
| Lineage | Nguồn gốc dữ liệu | Sidebar sub-label, nav copy |
| Precision | Độ chính xác (Precision) (R1) | Schema mapping copy |
| Artifact | Artifact (R3, kept in English) | Data management copy |

- **Assumptions:**
  - Sub-labels and descriptions are R2 (Vietnamese only), so `Datasets & Lineage` becomes `Tập dữ liệu & nguồn gốc` with no parentheses.
  - Existing Vietnamese strings are kept as they are unless the file is in the milestone.
  - Where no glossary entry exists, the agent proposes a term at the milestone checkpoint instead of guessing silently.

## 3. Files
Scope per milestone. Each milestone lists its files in its checkpoint; the list below is the planned scope.

| Action | File | Milestone | Note |
|---|---|---|---|
| modify | `usfds-web/src/components/layout/{Sidebar,Topbar,OmnisearchModal,PageHeader,InspectorDrawer,WorkspaceStepper}.tsx` | M1 | `Sidebar.tsx` is a shell hot spot: text-only edits |
| modify | `usfds-web/src/components/common/*.tsx` | M1 | only if English copy is found |
| modify | `usfds-web/src/utils/formatters.ts` | M1 | `vi-VN`, `N/A` placeholder |
| create | `usfds-web/src/components/layout/Sidebar.test.tsx` | M1 | acceptance test |
| create | `usfds-web/src/components/layout/Topbar.test.tsx` | M1 | acceptance test |
| modify | `usfds-web/src/utils/formatters.test.ts` (existing file; 2 tests added) | M1 | acceptance tests |
| modify | `usfds-web/src/components/modules/data_management/*`, `project_management/*`, `pages/{DataManagement,ProjectManagement,ProjectSettings}Page.tsx`, `hooks/useDatasetPipeline.ts` (alert text) | M2 | |
| modify | `usfds-web/src/components/modules/{detection,investigation,reports}/*`, `pages/{DetectionJob,Investigation,InsightReport}Page.tsx`, `components/modules/{DetectionJob,Investigation,InsightReport}Module.tsx`, `PoliciesView.test.tsx` | M3 | |
| modify | `usfds-web/src/components/modules/{model,rule}/*`, `components/modules/{ModelTraining}Module.tsx`, `LineageCanvasView.tsx`, `pages/{ModelTraining,RuleEngine}Page.tsx` | M4 | |
| modify | any remaining non-test `usfds-web/src` file with English-only UI copy | M5 | found by sweep |

## 4. Dependencies & conflicts (with other tasks on BOARD)
| # | Check | Answer |
|---|---|---|
| D1 | Needs unfinished task? | No |
| D2 | Needed by unfinished task? | No |
| C1 | Modified files owned by in-progress task? | No. Overlap with the planned RBAC task (not in progress): `Topbar.tsx`, `useProjects.tsx`, `useDatasetImport.ts`, `ProjectSettingsView.tsx` (`.plan/user_management_rbac.md:123-124`). Merge conflicts likely if RBAC merges first. User accepted parallel work (26-11-14). |
| C2 | Hot-spot files touched | `usfds-web/src/components/layout/Sidebar.tsx` (text-only, one line per label). No other hot spot. |
| C3 | Schema change | No |
| C4 | Public contract change | No (labels only; no API, route or payload change) |
| C5 | Shared UI shell change | Yes: `Sidebar.tsx` labels, `Topbar.tsx` and `OmnisearchModal.tsx` copy. No route or nav-structure change. |

## 5. Acceptance tests (user reviews this section)
Each milestone's tests are written first, confirmed red, then implemented.

| Milestone | Test | Given | When | Then | Covers |
|---|---|---|---|---|---|
| M1 | `test_sidebar_module_labels_are_vietnamese` (`usfds-web/src/components/layout/Sidebar.test.tsx`) | Sidebar rendered with all modules | Rendered | Each module label shows the glossary copy, e.g. `Quản lý dữ liệu` | ISS-005 |
| M1 | `test_format_number_uses_vi_vn_separator` (`usfds-web/src/utils/formatters.test.ts`) | `formatNumber(1234567)` | Called | Returns `1.234.567` | ISS-005 |
| M1 | `test_format_date_missing_value_is_vietnamese` (`usfds-web/src/utils/formatters.test.ts`) | `formatDate(undefined)` | Called | Returns `Không có`, not `N/A` | ISS-005 |
| M1 | `test_topbar_project_menu_labels_are_vietnamese` (`usfds-web/src/components/layout/Topbar.test.tsx`) | Topbar rendered with no project selected | Project menu opened | Shows `Dự án` and the Vietnamese no-project text (R2) | ISS-005 |
| M2 | `test_dataset_hub_headings_are_vietnamese` (`usfds-web/src/components/modules/data_management/DatasetHubView.test.tsx`) | Dataset list handler returns `[]` (MSW) | DatasetHubView rendered | Import button and stat tiles show Vietnamese copy | ISS-005 |
| M2 | `test_pipeline_proceed_and_back_labels_are_vietnamese` (`usfds-web/src/hooks/useDatasetPipeline.test.tsx`; replaces the alert test, see checkpoint log) | Hook with step `step-profiling` | `proceedButtonText`, `backButtonText` read | Bilingual term labels | ISS-005 |
| M2 | `test_project_management_actions_are_vietnamese` (`usfds-web/src/components/modules/project_management/ProjectManagementView.test.tsx`) | No projects | View rendered | `Dự án mới` shown | ISS-005 |
| M3 | `test_policies_view_column_labels_are_vietnamese` (`PoliciesView.test.tsx`, new test in the existing file) | Blacklist handler returns one row | PoliciesView rendered | Table headers show Vietnamese copy; the existing data assertion at line 38 is unchanged (fixture data, not UI copy) | ISS-005 |
| M3 | `test_detection_jobs_hub_headings_are_vietnamese` (`usfds-web/src/components/modules/detection/DetectionJobsHubView.test.tsx`) | Jobs handler returns `[]` | Hub rendered | Headings and primary button use Vietnamese copy | ISS-005 |
| M4 | `test_model_hub_headings_are_vietnamese` (`usfds-web/src/components/modules/model/ModelHubView.test.tsx`) | Model handler returns `[]` | ModelHubView rendered | Headings and primary button use Vietnamese copy | ISS-005 |
| M4 | `test_rule_catalog_headings_are_vietnamese` (`usfds-web/src/components/modules/rule/RuleCatalogView.test.tsx`) | Rule handler returns `[]` | RuleCatalogView rendered | Headings and primary button use Vietnamese copy | ISS-005 |
| M5 | — (sweep, no new test) | All milestones merged | Grep for English-only UI copy in non-test `usfds-web/src` | Remaining hits are R3 terms or listed in the report as residuals | ISS-005 |

## 6. Milestones & to-do (checkpoints; the agent waits for user approval after each one)
The user approves each milestone before the next starts (decision 26-11-14). The agent ticks items as it works.

- [x] **M1 — Shell & formatters** (`usfds-web`): Sidebar, Topbar, Omnisearch, layout/common copy; `formatNumber` vi-VN; `formatDate` placeholder
  - [x] [tests] Write M1 tests from §5 (Sidebar, formatters, Topbar); confirmed red (4 failing for missing copy/locale)
  - [x] [web] `Sidebar.tsx` module labels and sub-labels
  - [x] [web] `Topbar.tsx` and `OmnisearchModal.tsx` copy
  - [x] [web] `InspectorDrawer.tsx`, `PageHeader.tsx`, `WorkspaceStepper.tsx`, `common/*` (no English copy found beyond the brand `USFDS`)
  - [x] [web] `utils/formatters.ts`
  - [x] [verify] `./scripts/test.sh web`, `npm run build`, `npm run lint` in `usfds-web`
- [x] **M2 — Data & project screens** (`usfds-web`): `data_management/*`, `project_management/*`, `pages/{DataManagement,ProjectManagement,ProjectSettings}Page.tsx`, `useDatasetPipeline.ts` labels
  - [x] [tests] Write M2 tests from §5; confirmed red (3 failing for missing copy)
  - [x] [web] Translate copy per R1/R2 (data_management, project_management, `useDatasetPipeline.ts` labels and button texts; `N/A` in M2 files → `Không có`)
  - [x] [verify] web suite, build, lint
- [x] **M3 — Detection, investigation, reports** (`usfds-web`): `detection/*`, `investigation/*`, `reports/*`, the three `*Module.tsx` files, related pages; PoliciesView header test added
  - [x] [tests] Write M3 tests from §5; confirmed red (2 failing for missing copy: hub title, PoliciesView headers)
  - [x] [web] Translate copy per R1/R2 (Artifact and Apache Parquet kept English; Precision bilingual; Recall Vietnamese only)
  - [x] [web] `PoliciesView.test.tsx:38` left unchanged: it asserts the fixture value `Confirmed account takeover` (user data, not UI copy)
  - [x] [verify] web suite, build, lint
- [x] **M4 — Model & rule** (`usfds-web`): `model/*`, `rule/*`, `ModelTrainingModule.tsx`, `LineageCanvasView.tsx` (no UI copy), related pages (no UI copy)
  - [x] [tests] Write M4 tests from §5 (ModelHubView, RuleCatalogView); confirmed red
  - [x] [web] Translate copy per R1/R2 (`Precision` bilingual; `Recall` → `Độ nhạy`; `PR-AUC`, `F1-Score`, `ROC`, `FPR`, `TPR` kept as acronyms; `N/A` → `Không có`)
  - [x] [verify] web suite, build, lint
- [x] **M5 — Sweep & verification** (`usfds-web`): grep non-test `src` for remaining English-only copy; fix or list each residual
  - [x] [web] Fixed leftovers: hook and API error fallbacks, sample dataset descriptions, confirm texts, `RAW Schema` / `Dataset` in Vietnamese prose, parenthesized English labels, a few repeated buttons (`Back`, `Cancel`, `Refresh`, `Dispatch`)
  - [x] [verify] `./scripts/test.sh web` (10 files, 16 tests), `npm run build` exit 0, `npm run lint` exit 0; final sweep output in the report

Checkpoint log (the agent appends one line per finished milestone):
- 26-11-14 M1 done, approved by user 26-11-14: `./scripts/test.sh web` 4 files, 9 passed; `npm run build` exit 0; `npm run lint` exit 0 (existing warnings only). Deviations: `formatters.test.ts` was an existing file, so the two M1 tests were added to it; `Topbar.test.tsx` is new. Glossary additions: Workspace Projects, Archived, Locked/Unlocked, Rules, New/Manage Projects, Search, Notifications, Data Scientist, Module.
- 26-11-14 M2 done (approved by user together with the start of M3): `./scripts/test.sh web` 7 files, 12 passed; `npm run build` exit 0; `npm run lint` exit 0. Deviations: (1) the planned alert test `test_dataset_pipeline_alert_is_vietnamese_only` was replaced by `test_pipeline_proceed_and_back_labels_are_vietnamese`. The alert text is already Vietnamese (R2), so that test would pass before any change and gives no red-first check. (2) The hook test file is `useDatasetPipeline.test.tsx` (JSX wrapper). (3) `ProjectManagementView.test.tsx` was added (no M2 test covered project screens in §5). (4) M2 `N/A` → `Không có` applied per the recommendation in §8. Glossary additions: Dataset, Profiling, Lineage (Vietnamese term + English), Stage, Preprocessed, Fraud Label, Raw Schema, Physical/Logical type, Records, Columns, Attributes, Export, Download, Projects, Active/Archived, Base Dataset.
- 26-11-14 Rule revised by user: the `Vietnamese (English)` format only for hard-to-translate terms (R1). Stripped the English part from the M1 and M2 copy (168 distinct strings across 22 web files and the new tests), renamed the `*_are_bilingual` tests to `*_are_vietnamese`. Kept `Precision` (R1) and `(PII)` (acronym). Re-verified: `./scripts/test.sh web` 7 files, 12 passed; `npm run build` exit 0; `npm run lint` exit 0.
- 26-11-14 M3 done (awaiting approval): `./scripts/test.sh web` 8 files, 14 passed; `npm run build` exit 0; `npm run lint` exit 0. Deviations: (1) `PoliciesView.test.tsx:38` is data, not UI copy, so it is unchanged; the new header test `test_policies_view_column_labels_are_vietnamese` was added to the same file. (2) `test_detection_jobs_hub_headings_are_vietnamese` asserts the hub title only. (3) Enum codes (`REJECT`, `REVIEW`, `ALLOW`, `ACTIVE`, `REMOVED`, `RESOLVED_*`) and rule codes stay as-is in parentheses or code spans; they are identifiers, not translations. (4) `N/A` in M3 files → `Không có`.
- 26-11-14 M4 done (awaiting approval): `./scripts/test.sh web` 10 files, 16 passed; `npm run build` exit 0; `npm run lint` exit 0. Deviations: (1) `N/A` in `RuleDryRunWorkspace.tsx` → `Không có`. (2) Rule operators `NOT IN`, `ALL/ANY/NONE` labels kept as logic keywords; `EXECUTION OUTCOME (THEN)` keeps `THEN`. (3) Several status labels in rule/dry-run views are now Vietnamese uppercase (for example `TỔNG SỐ LẦN LUẬT KÍCH HOẠT`). The CSS keeps uppercase, so layout is unchanged.
- 26-11-14 M5 done (awaiting approval): `./scripts/test.sh web` 10 files, 16 passed; `npm run build` exit 0; `npm run lint` exit 0. Residual English kept on purpose: developer-only messages (`useProject must be used within a ProjectProvider`), code identifiers and comments, acronyms and codes (`SHAP`, `XGBoost`, `JSON`, `UTC`, `TP/FP/FN`, `FPR/TPR`, `PR-AUC`, `F1/F2-Score`, `SAR`, `PII`, `SemVer`, `BR-*`, `SUC-*`, `REJECT/REVIEW/ALLOW`, `ACTIVE`, `APPROVED`, `FEATURE_ENGINEERED`, `NOT IN`, `THEN`, `IF`), proper names (`Sparkov`, `IEEE-CIS`, `JsonLogic`, `Stitch DSL`, `Apache Parquet`), and R3 nouns (`Artifact`). `Precision` is the only bilingual term (R1).

## 7. Review hotspots (filled in after implementation)
- `usfds-web/src/utils/formatters.ts:18` (M1): `formatNumber` now uses `vi-VN`; 5 call sites display counts and sizes. Check that no table or chart expects `en-US` separators. Covered by `formatters.test.ts`.
- `usfds-web/src/utils/formatters.ts:33` (M1): `formatDate` placeholder changed from `N/A` to `Không có`. All `'N/A'` literals in `usfds-web/src` are now `Không có` (checked at M4).
- `usfds-web/src/components/modules/investigation/WorkbenchResolutionColumn.tsx` (M3): the reopen, dispatch and "Submit Confirmed Fraud / Submit Legitimate (False Positive)" labels now name the action taken on the case. The wording must still match what the handler does (confirmed fraud vs. false positive).
- `usfds-web/src/components/modules/detection/DetectionJobWizardView.tsx` (M3): the "Start Detection Job" button and the "Rule-Only Mode" / "Chỉ dùng luật" branch copy describe the job mode. Check that the Vietnamese label matches the value sent to the API.
- `usfds-web/src/components/modules/project_management/ProjectManagementView.tsx` (M2, delete flow `window.confirm` near line 110): the warning text lists the cascade (`BR-PM-08`) and now reads `tập dữ liệu, luật`. Check that the wording still states the cascade delete clearly. The logic is unchanged.
- `usfds-web/src/hooks/useDatasetPipeline.ts:213-234` (M2): proceed/back labels are built in a switch on `currentStepId`. Only text changed, but check that the labels still match the step they name.
- `usfds-web/src/components/layout/OmnisearchModal.tsx:32-37` (M1): the search filter matches `label` text, which now includes Vietnamese descriptions. English terms still match because they stay in the label. The `type` value is now `Mô-đun (Module)`, which the filter also reads.
- `usfds-web/src/components/modules/model/ActivateModelModal.tsx` (M4): the confirm button `Xác nhận kích hoạt` activates a model version. Check it still matches the action (status moves to APPROVED).
- `usfds-web/src/components/modules/rule/RuleDryRunWorkspace.tsx` (M4): the dry-run result labels (`ĐÃ KÍCH HOẠT (KHỚP)` / `CHƯA KÍCH HOẠT`) and the `TRIGGERED` / `NOT TRIGGERED` state must still map to the same boolean.
- `usfds-web/src/components/modules/model/TrainingRunDetailView.tsx` (M4): metric labels (`PR-AUC (Độ chính xác (Precision) trung bình)`, `F2-Score (ưu tiên độ nhạy)`). Check that the labels still name the right metric.

## 8. Open questions
- Glossary entries beyond the M1 list: the agent proposes them at each milestone checkpoint; the user approves.
- R3 (acronyms stay English) is an assumption; confirm at M1.
- `N/A` consistency: applied in M2 files (`Không có`). Applied to M3 and M4 as well.
- Resolved (user, 26-11-14): `Artifact` stays English (R3). `Apache Parquet` stays English as a format name (R3).
- Resolved (user, 26-11-14): no extra R1 terms. `Recall`, `PR-AUC`, `ROC-AUC` stay Vietnamese only (`Độ nhạy` for Recall; acronyms like PR-AUC remain as written). Only `Precision` keeps the `Vietnamese (English)` format. Please say if you meant that Recall and the AUC metrics should be bilingual.
- Scope note: the M2 sweep is not an exhaustive check. M5 runs the final grep over all of `usfds-web/src`.
