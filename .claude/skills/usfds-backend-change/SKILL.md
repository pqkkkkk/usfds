---
name: usfds-backend-change
description: Where and how to change USFDS backend code following its Clean Architecture — entity, port, ORM table, repository, Alembic migration, service, provider, router, worker handler — with append-only rules for shared files so parallel agents do not conflict. Use when adding or changing a backend feature, endpoint, table, column, repository, queue job, or permission in usfds-core, usfds-infra, usfds-server or usfds-worker.
---

# USFDS backend change

Read first: `docs/arch/implementation-level-design.md` (layers) and the feature spec in `docs/features/**`.

## Layer map (dependencies point downward only)

| Step | Layer | Where | Notes |
|---|---|---|---|
| 1 | Entity / enum | `usfds-core/src/usfds_core/domain/entities/<domain>.py`, `enums.py` | Pure `dataclasses`, no third-party imports. `enums.py` is a hot spot: append only |
| 2 | Port | `usfds-core/src/usfds_core/repositories/base_<x>_repo.py` | ABC. Core never imports `usfds_infra` (not even in tests) |
| 3 | Service | `usfds-core/src/usfds_core/services/<domain>/` | Business rules; raise `ValueError` / `LookupError` / domain errors, not HTTP errors |
| 4 | ORM table | `usfds-infra/src/usfds_infra/database/tables/<domain>.py` | Then append the import to `database/models.py` |
| 5 | Migration | `poetry run python -m usfds_infra.database.migrate revision "<msg>"` (in `usfds-infra`) | Review the generated file; see Migrations below |
| 6 | Repository | `usfds-infra/src/usfds_infra/database/repos/<domain>.py` | Map ORM ↔ entity; `flush()` only, never `commit()`. Append the import to `database/repositories.py` and `database/__init__.py` |
| 7 | Providers | repo getter → `usfds-server/src/usfds_server/providers/repos.py`; service → `providers/<domain>.py` | Append the re-export in `dependencies.py` |
| 8 | Router + schemas | `usfds-server/src/usfds_server/routers/<domain>_router.py`, `schemas/<domain>_api_schemas.py` | Return `ApiResponse`; map domain errors to HTTP codes; new router → append to `api.py` |
| 9 | Queue job (heavy work) | constant in `usfds-infra/.../job_queue/bullmq_queue.py`, handler in `usfds-worker/.../handlers.py`, map entry in `worker/main.py` | Keep the sync branch and the queue branch equivalent; test both (`client` + `client_queue_mode`) |

## Rules
- **Hot spots** (append-only, never reorder or reformat): `domain/entities/enums.py`, `database/models.py`, `database/repositories.py`, `database/__init__.py`, `server/dependencies.py` (provider re-exports), `providers/repos.py`, `server/api.py` (router list), `worker/main.py` (handler maps), `job_queue/bullmq_queue.py` (constants), `deploy/.env.example`.
- **Config:** new settings go in `usfds-server/src/usfds_server/config.py` with an `USFDS_*` env var and a line in `deploy/.env.example`. No UI for secrets or API keys.
- **Heavy work** (pandas on whole files, training, inference) runs in a service invoked through a dispatcher or queue job, never inline in an `async def` endpoint.
- **Code style:** tabs in new files (some old files use spaces: follow the file). Do not reformat untouched lines. Comment out removed code with `# DEPRECATED [YY-MM-DD]: reason`. Tag unrelated problems with `# TODO: ISS-NNN` and add the issue to `docs/issues/`.

## Migrations (Alembic, ISS-020)
- Never call `Base.metadata.create_all` in product code. Startup runs `init_db(engine)` → `upgrade_database`, which migrates new, legacy and current databases without data loss.
- One revision per task. Generate: `cd usfds-infra && poetry run python -m usfds_infra.database.migrate revision "add xyz"`. Then:
  - Read it. Autogenerate misses renames (they show up as drop + add, which loses data) and server defaults. Add a backfill for new NOT NULL columns on existing rows.
  - `poetry run python -m usfds_infra.database.migrate check` must exit 0 (models == migrations).
  - `poetry run python -m usfds_infra.database.migrate heads` must print exactly one head. When rebasing onto `main`, set your `down_revision` to the new head.
- SQLite runs migrations in batch mode automatically (`render_as_batch`). Migrations must also work on PostgreSQL: `test_all_migrations_render_as_postgresql_sql_offline` checks them.

## Verify
`./scripts/test.sh core infra server worker`: all green, including the PostgreSQL guard. Then write the final report as described in skill `usfds-task-workflow`.
