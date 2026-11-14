# Task Board

> **1 task = 1 agent session = 1 plan file** (`.plan/<task_slug>.md`, task ID = file name). The user decides which issues form a task.
> Milestones are checkpoints inside the plan, not separate tasks.
> Updated **only at merge time** or when a task is claimed. Agents read it in skill `usfds-plan` to detect dependencies and file conflicts.
> Status: `Planning` → `Approved` → `In progress (M<n>)` → `Review` → `Done (YY-MM-DD)`.
> Issue index: [`docs/issues/README.md`](../docs/issues/README.md). Master plan: [`parallel_agent_setup.md`](parallel_agent_setup.md).

## Phase 0 — Foundation (done 26-11-14)

| ID | Task | Issues | Status | Depends on | Owned files |
|---|---|---|---|---|---|
| F6 | Agent context: skills, BOARD, AGENTs.md, CHANGELOG, issue index | ISS-034 | Done (26-11-14) — SUC ID fix pending Notion | — | `.claude/skills/**`, `.plan/BOARD.md`, `AGENTs.md`, `CHANGELOG.md`, `docs/issues/**` |
| F0 | Python 3.12 pin, `scripts/test.sh`, fix broken tests, moto, untrack `.env` | ISS-024, ISS-013 | Done (26-11-14) | — | `scripts/test.sh`, `usfds-*/pyproject.toml`, `usfds-*/poetry.lock`, `.gitignore` |
| F1 | Testkit fixtures, conftest, server tests without global mutation, `InlineJobQueue` | ISS-025 | Done (26-11-14) | F0 | `usfds-infra/src/usfds_infra/testing/**`, `usfds-worker/src/usfds_worker/testing.py`, `usfds-*/tests/conftest.py` |
| F2 | Alembic baseline (idempotent for legacy DBs); PG-compat guards G1–G3 | ISS-020 | Done (26-11-14) | F1 | `usfds-infra/src/usfds_infra/database/{migrate,compat,session}.py`, `database/migrations/**` |
| F3 | Split ORM / repositories / server providers by domain | ISS-026 | Done (26-11-14) | F2 | `usfds-infra/src/usfds_infra/database/{tables,repos}/**`, `usfds-server/src/usfds_server/providers/**` |
| F4 | Auth seam (`get_current_user`, permission map) — **reverted 26-11-14**: auth/RBAC moves to its own session | ISS-006 | Reverted | — | — |
| F5 | Web test harness (vitest + MSW), unify ports; ISS-028 assessed → C4 | ISS-028, ISS-029 | Done (26-11-14) | — | `usfds-web/{package.json,vite.config.ts,src/test/**,.env.example}` |

## Tasks <!-- [26-11-14] one row per plan file; created when the user starts a session with a set of issues -->

| Task (plan file) | Issues | Status | Milestone | Depends on | Owned files |
|---|---|---|---|---|---|
| [`user_management_rbac`](user_management_rbac.md) | ISS-006 | Planning (plan drafted before 26-11-14; re-check against the new template) | — | Phase 0 | per plan §3 |
| [`ui_vietnamese_localization`](ui_vietnamese_localization.md) | ISS-005 | Done (26-11-14) | M5 | — | `usfds-web/src/**` (copy only) |
| [`model_version_lineage`](model_version_lineage.md) | ISS-008 | Done (26-11-14) | M3 | — | `usfds-core/services/training/**`, `usfds-server/routers/training_router.py`, `usfds-web/src/components/modules/model/**` |

## Backlog
Every issue without a task: see [`docs/issues/README.md`](../docs/issues/README.md) (rows whose *Plan / Task* column is `—`).

## Needs product decision before a task can be planned
ISS-004, ISS-007, ISS-009, ISS-010, ISS-011.
