# USFDS Worker (`usfds-worker`)

Stateless compute worker of the `Client - Server - Worker` deployment. It consumes jobs that `usfds-server`
enqueues through BullMQ (PostgreSQL backend), runs the existing `usfds-core` executors, reads/writes files
through S3-compatible storage (RustFS) and records the outcome in PostgreSQL.

| Queue | Job | Executor |
| --- | --- | --- |
| `usfds-training` | `training_run` | `TrainingRunExecutor` |
| `usfds-batch-inference` | `batch_inference` | `BatchInferenceExecutor` |

## Run

```bash
cd usfds-worker && poetry install
export USFDS_DB_URL=postgresql+psycopg://usfds:***@localhost:5432/usfds
export USFDS_S3_ENDPOINT_URL=http://localhost:9000 USFDS_S3_BUCKET=usfds \
       USFDS_S3_ACCESS_KEY=... USFDS_S3_SECRET_KEY=...
poetry run usfds-worker
```

Environment: `USFDS_DB_URL` (required), `USFDS_S3_*` (see `deploy/.env.example`), `USFDS_WORKER_CONCURRENCY` (default 1),
`USFDS_BULLMQ_SCHEMA` (default `bullmq`). Full stack: `deploy/docker-compose.yml`.
