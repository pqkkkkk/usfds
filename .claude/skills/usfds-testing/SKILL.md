---
name: usfds-testing
description: How to write and run USFDS tests without Docker — SQLite-per-test fixtures, moto S3, InlineJobQueue for queue mode, the PostgreSQL compatibility guard, and vitest + MSW for the web. Use when writing acceptance tests, reproducing a bug, adding fixtures, or when a test fails with PostgresCompatibilityError.
---

# USFDS testing

## Run
```bash
./scripts/test.sh                      # all: core infra server worker cli web
./scripts/test.sh server               # one package
./scripts/test.sh server -- -k delete  # extra args go to pytest / vitest
```
- Python is pinned to 3.12 (`uv python install 3.12`). The script creates and syncs Poetry envs, and unsets every `USFDS_*` env var so the shell never leaks into tests.
- Nothing needs Docker. Real PostgreSQL + BullMQ + S3 is covered by the user's end-to-end runs, not by agents.
- Temp files: `tmp_path` and `tempfile` in tests land in one per-run folder `usfds-pytest-*` under the system temp dir. It is removed automatically when the run passes. If any test fails, the folder is kept and its path is printed, so you can inspect the files. Do not write test output into the repo (for example `storage_output/`).

## Where a test goes

| Behavior | Level | Location | Fixtures |
|---|---|---|---|
| Endpoint / feature with an API (default for acceptance tests) | API | `usfds-server/tests/test_<domain>_api.py` | `client`, `client_queue_mode`, `server_settings`, `server_session_factory` |
| Repository, migration, SQL | Infra | `usfds-infra/tests/` | `db_engine`, `session_factory`, `db_session`, `local_storage`, `s3_storage` |
| Worker handler | Worker | `usfds-worker/tests/` | `worker_context`, `inline_job_queue` + infra fixtures |
| Pure domain logic (no DB, no storage) | Core | `usfds-core/tests/` | none; never import `usfds_infra` from core tests |
| UI component / hook | Web | next to the component: `*.test.tsx` | `renderWithProviders`, MSW `server`, `API` |

Database-backed tests always use SQLite through the fixtures. Do not write new tests on `InMemory*Repository` (kept only for legacy tests).

## Backend fixtures (all per-test, isolated)
- **`server_settings`** (autouse in server tests): temp SQLite + temp local storage + `dispatch_backend="sync"`. Never assign `settings.x = ...`; use `monkeypatch.setattr(server_settings, "x", value)`.
- **`client`**: `TestClient` on the real app (lifespan runs migrations).
- **`client_queue_mode`**: runs the `if settings.dispatch_backend == "queue"` branches. Jobs go router → JSON payload → worker handler in-process through `InlineJobQueue`. Assert on `client_queue_mode.job_queue.jobs` (`queue`, `name`, `data`, `state`, `failed_reason`, `return_value`). Example: `usfds-server/tests/test_queue_mode_api.py`.
- **`server_session_factory`**: the running app's session factory, for seeding and asserting DB state.
- **`db_engine` / `session_factory` / `db_session`**: fresh SQLite migrated with Alembic (`usfds_infra.testing.create_test_database`).
- **`local_storage`**: `LocalFileStorage` in `tmp_path/storage`. **`s3_storage`**: `S3FileStorage` on moto (no network).

## PostgreSQL compatibility guard (always on in infra, worker and server tests)
Every SQL statement executed on SQLite is also compiled for PostgreSQL (G2) and scanned for SQLite-only functions (G3: `json_each`, `json_extract`, `group_concat`, `strftime`, `datetime(`, `ifnull`, `instr`, `printf`, `glob`, `collate nocase`, …). A violation fails the test with `PostgresCompatibilityError`, which names the PostgreSQL alternative. Migrations are checked separately (G1, `usfds-infra/tests/test_migrations.py`).
- Fix the query: use SQLAlchemy constructs that compile per dialect (JSON index operators, `func.coalesce`, `ilike`).
- If a branch is deliberately dialect-specific (`if dialect.name == "sqlite":`), wrap it in `usfds_infra.database.compat.sqlite_only()`.
- What the guard **cannot** catch, so follow these conventions:
  - Always `ORDER BY` when order matters.
  - Use `ilike` for case-insensitive matching (`LIKE` is case-sensitive on PostgreSQL).
  - Store values in the declared column type (SQLite accepts anything).
  - Compare timezone-aware datetimes.
  - No raw SQL in repositories.

## Writing acceptance tests
- Name tests as business sentences, e.g. `test_delete_dataset_used_by_training_run_returns_409`. One requirement per test, tagged in the docstring with SUC/BR/ISS.
- Assert observable behavior: HTTP status, the `ApiResponse` envelope (`success`, `statusCode`, `data`), DB state, storage objects, queued jobs. Do not assert private functions.
- Bugs: write the reproducing test first and confirm it fails. A known, not-yet-fixed bug can be pinned with `@pytest.mark.xfail(strict=True, reason="ISS-NNN: ...")`; strict makes it fail once fixed, so the marker gets removed.
- Keep data small (tens of rows); create files under `server_settings.storage_dir` or `tmp_path`.

## Web tests
```tsx
import { http, HttpResponse } from 'msw';
import { API, server } from '@/test/server';
import { renderWithProviders } from '@/test/renderWithProviders';

server.use(http.get(`${API}/v1/blacklist`, () => HttpResponse.json({ success: true, data: [] })));
renderWithProviders(<PoliciesView projectId="p-1" readOnly={false} />);
expect(await screen.findByText('...')).toBeInTheDocument();
```
- Unhandled requests fail the test (`onUnhandledRequest: 'error'`). Add handlers for every call a component makes. `GET /v1/projects` has a default handler.
- Tests always call `/api` (`VITE_API_BASE_URL` is forced empty in `vite.config.ts`).
- Cover the loaded state **and** the error state (HTTP 4xx/5xx) for data-fetching components. Example: `src/components/modules/investigation/PoliciesView.test.tsx`.
- `apiClient` currently returns `{success:false}` instead of throwing (ISS-028). Test what the component actually shows.
