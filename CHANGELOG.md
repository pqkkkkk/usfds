# Changelog

Completed work, newest first. Updated at merge time (see `AGENTs.md` §0.1). Issue IDs refer to `docs/issues/README.md`.

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
