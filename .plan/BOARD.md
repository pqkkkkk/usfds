# Task Board

> **1 task = 1 agent session = 1 plan file** (`.plan/<task_slug>.md`, task ID = file name). The user decides which issues form a task.
> Milestones are checkpoints inside the plan, not separate tasks.
> Updated **only at merge time** or when a task is claimed. Agents read it in skill `usfds-plan` to detect dependencies and file conflicts.
> Status: `Planning` → `Approved` → `In progress (M<n>)` → `Review` → `Done (YY-MM-DD)`.
> Issue index: [`docs/issues/README.md`](../docs/issues/README.md).

## Tasks <!-- [26-11-14] one row per plan file; created when the user starts a session with a set of issues -->

| Task (plan file) | Issues | Status | Milestone | Depends on | Owned files |
|---|---|---|---|---|---|
| [`parallel_agent_setup`](parallel_agent_setup.md) | ISS-013, ISS-020, ISS-024, ISS-025, ISS-026, ISS-028, ISS-029, ISS-034 | Done (26-11-14) | F0–F6 | — | `scripts/test.sh`, `usfds-infra/src/usfds_infra/{database,testing}/**`, `usfds-server/src/usfds_server/providers/**`, `.claude/skills/**` |
| [`user_management_rbac`](user_management_rbac.md) | ISS-006 | Done (26-11-15) | — | `parallel_agent_setup` | per plan §3 |
| [`ui_vietnamese_localization`](ui_vietnamese_localization.md) | ISS-005 | Done (26-11-14) | M5 | — | `usfds-web/src/**` (copy only) |
| [`model_version_lineage`](model_version_lineage.md) | ISS-008 | Done (26-11-14) | M3 | — | `usfds-core/services/training/**`, `usfds-server/routers/training_router.py`, `usfds-web/src/components/modules/model/**` |
| [`presigned_upload_and_file_io_guard`](presigned_upload_and_file_io_guard.md) | ISS-015, ISS-036 | Done (26-11-15) | M1–M2 | — | `usfds-core/storage/**`, `usfds-infra/storage/**`, `usfds-web/src/api/**`, `usfds-server/routers/dataset_router.py` |
| [`quick_bugfix_and_cors_hardening`](quick_bugfix_and_cors_hardening.md) | ISS-035, ISS-014, ISS-017, ISS-003 | Done (26-11-15) | M1–M2 | — | `usfds-core/services/data_management/service.py`, `usfds-infra/database/repos/{model,detection}.py`, `usfds-server/{api,config,providers/data,routers/dataset_router}.py` |
| [`web_api_client_error_propagation`](web_api_client_error_propagation.md) | ISS-028 | Done (26-11-16) | M1–M2 | — | `usfds-web/src/api/client.ts`, `usfds-web/src/hooks/useAuth.tsx`, `usfds-web/src/components/modules/**`, `usfds-web/src/pages/AdminUsersPage.tsx` |
| [`rbac_feature_visibility`](rbac_feature_visibility.md) | ISS-037 | Done (26-11-16) | M1–M5 | `user_management_rbac` | `usfds-infra/database/seed_rbac.py`, `usfds-core/services/auth/authz_service.py`, `usfds-server/routers/**`, `usfds-web/src/{lib/feature-policy.ts,hooks/useActorContext.ts,components/**,pages/**,App.tsx}` |
| [`quick_backend_hardening`](quick_backend_hardening.md) | ISS-016, ISS-018, ISS-019, ISS-022 | Done (26-11-17) | M1–M3 | — | `usfds-core/services/{training/models/script_trainer,inference/executor,training/plugins/validator}.py`, `usfds-infra/database/case_repositories.py`, `usfds-server/{config,routers/training_router}.py`, `deploy/.env.example` |
| [`model_versioning_scheme`](model_versioning_scheme.md) | ISS-010 | Done (26-11-21) | M1–M3 | — | `usfds-core/{repositories/{base_model_version_repo,in_memory_repos},services/training/training_service}.py`, `usfds-infra/database/{tables/model,repos/model,migrations/versions/{14f998f68015*,845d529c5502*}}.py`, `usfds-server/routers/training_router.py`, `usfds-web/src/{utils/formatters.ts,api/trainingApi.ts,components/modules/{model,detection}/**}` |
| [`system_metadata_management`](system_metadata_management.md) | ISS-007, ISS-027 | Done (26-11-21) | M1–M3 | `parallel_agent_setup`, `user_management_rbac`, `rbac_feature_visibility` | per plan §3 |
| [`project_scoped_access_control`](project_scoped_access_control.md) | ISS-042 | Done (26-11-22) | M1–M3 | `user_management_rbac`, `rbac_feature_visibility`, `model_versioning_scheme` | per plan §3 |
| [`own_scope_access_control`](own_scope_access_control.md) | ISS-043, ISS-023 | Done (26-11-22) | M1–M3 | `user_management_rbac`, `rbac_feature_visibility`, `project_scoped_access_control`, `model_versioning_scheme` | per plan §3 |
| [`resource_owner_and_cursor_pagination`](resource_owner_and_cursor_pagination.md) | ISS-031 | Done (26-11-22) | M1–M3 | `own_scope_access_control` | per plan §3 |
| [`large_data_analytics_duckdb`](large_data_analytics_duckdb.md) | ISS-012, ISS-021 | Done (26-11-22) | M0–M3 | `own_scope_access_control` | per plan §3 |
| [`investigation_redesign`](investigation_redesign.md) | ISS-045 | Done (26-11-22) | M1–M3 | `large_data_analytics_duckdb` | per plan §3 |
| [`graph_exploration`](graph_exploration.md) | ISS-041 | Done (26-11-24) | M1–M3 | `large_data_analytics_duckdb`, `investigation_redesign` | per plan §3 |
| [`feature_management`](feature_management.md) | ISS-040 | Done (26-11-24) | M1–M5 | `system_metadata_management`, `own_scope_access_control`, `large_data_analytics_duckdb`, `graph_exploration` | per plan §3 |
