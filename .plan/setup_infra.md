# Setup infra — Client / Server / Worker (TASK-103)

Source: `docs/arch/high-level-design.md` (section "Kiến trúc triển khai đề xuất").

## Current state (verified)
- DB: SQLite only (`create_sqlite_engine`, `Sqlite*Repository`). Repos use SQLAlchemy, so Postgres needs a new engine factory, not new repos.
- Storage: `LocalFileStorage` only. `IFileStorage` = `save_bytes/read_bytes/exists/delete`. Executors work on local workspaces (`TrainingWorkspace`, `InferenceWorkspace`) with paths from `*_storage_path`.
- Async: `ITrainingRunDispatcher` / inference dispatcher already exist (Synchronous + daemon-thread). This is the seam for a queue dispatcher.
- No `usfds-worker`, no Dockerfile, no `.env.example`. `usfds-server/docker-compose.yml` is copied from another project (`promoguardian-*`, `postgres:15`, hard-coded password default).
- Docker daemon is not running on this machine, so compose/PG/MinIO cannot be verified until Docker Desktop is started.

## Decisions (approved)
- Scope: infra + adapters; SQLite/Local stay the default via config. No data migration, no AGE graph sync.
- Postgres image: `apache/age`, container names `usfds-*`, secrets from `.env`.
- Files go in `/deploy`; existing `usfds-server/docker-compose.yml` is moved there.

## Queue decision (resolved)
- Use the official Python BullMQ with its Postgres backend (docs.bullmq.io/python/introduction#postgresql-backend): `pip install "bullmq[postgres]"` (psycopg, Python 3.10+, PG 13+), `opts = {"backend": "postgres", "connection": <url>, "schema": "bullmq"}`; tables/functions auto-migrate on first use.
- Constraints from the docs: `QueueEvents` is Redis-only, `prefix` unsupported (use `schema`). So the server learns job outcome from DB state written by the worker, not from QueueEvents.
- BullMQ Python API is async; dispatchers/executors are sync. Bridge with `asyncio.run` / a server-side event loop on enqueue, and `asyncio.to_thread` in the worker so CPU-heavy executors don't block the loop.
- To verify when Docker is up: exact `Queue.add` options (attempts/backoff) and `Worker` concurrency/lock settings in the installed version.

## Phases
1. `deploy/`: `docker-compose.yml` (postgres+AGE, minio, minio-init bucket), `initdb/01-age.sql` (`CREATE EXTENSION age`), `.env.example`, `Dockerfile.server`, `Dockerfile.worker`, compose profile `app` for server+worker.
   - Check: `docker compose config` passes; `docker compose up -d` healthy; `SELECT * FROM ag_catalog.ag_graph` works; bucket exists.
2. `usfds-infra` adapters (+ extras in `pyproject.toml`: `psycopg[binary]`, `boto3` or `minio`):
   - `database/engine.py`: `create_postgres_engine(url)`; AGE `LOAD`/`search_path` on connect.
   - `storage/minio_storage.py`: `MinioFileStorage(IFileStorage)` + `download_to(path, local)` / `upload_from(local, path)` for workspace staging.
   - `queue/bullmq_queue.py`: thin wrapper over `bullmq.Queue` (postgres backend) with sync `enqueue(name, payload, attempts, backoff)`.
   - `queue/dispatchers.py`: `QueueTrainingDispatcher`, `QueueInferenceDispatcher` implementing existing interfaces; payload = `model_dump(mode="json")`.
   - Check: unit tests, PG/MinIO tests skipped unless `USFDS_TEST_PG_URL` / `USFDS_TEST_MINIO_ENDPOINT` set.
3. `usfds-worker` package: `bullmq.Worker` on the postgres backend, handler registry (`training`, `batch_inference`), stage inputs from MinIO into workspace, run existing executors, upload outputs, report result.
   - Check: enqueue one training job against compose stack; run completes; `model_bundle` in MinIO.
4. `usfds-server`: `config.py` backend switch (`USFDS_DB_URL`, `USFDS_STORAGE_BACKEND`, `USFDS_DISPATCH_BACKEND`); `dependencies.py` selects adapters. Defaults unchanged.
   - Check: existing server pytest suite unchanged and green.

## Not in this task
- SQLite -> Postgres data migration; AGE graph schema/sync; K8s; auth/TLS for MinIO.
