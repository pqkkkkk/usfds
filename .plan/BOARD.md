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
