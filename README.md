# USFDS (US Fraud Detection System)

## 1. Overview
- **USFDS** is a machine learning–driven platform designed for detecting credit card transaction fraud. The system provides an end-to-end workflow covering dataset management, automated feature preprocessing, model training, evaluation, batch detection, and explainability, investigation, related insight generation & reporting.
- **USFDS** is result of research and development efforts for graduation thesis, specifically aimed at creating a robust and scalable fraud detection system for credit card transactions.
- All related documentation and resources can be found within the Notion page [Task](https://app.notion.com/p/325b99c6a9508074ba72e26e509260bf?v=325b99c6a9508078acdc000cad8d9232)

---

## 2. Project Structure
<!-- [26-11-28] Synced with docs/arch/01-context-and-runtime.md. -->
The repository is organized into modular packages under the `usfds-*` prefix (packages not listed are out of current scope):

- **`usfds-core`**: Domain models, business logic, ML pipelines, and ports (repositories, storage, compute).
- **`usfds-infra`**: Infrastructure adapters: SQLAlchemy persistence (SQLite in WAL mode locally, PostgreSQL in client–server), Alembic migrations, local / S3 storage, BullMQ queue, Modal remote compute.
- **`usfds-server`**: FastAPI REST API and composition root.
- **`usfds-worker`**: BullMQ consumer that runs heavy jobs (training, batch inference, data pipeline, analytics).
- **`usfds-web`**: React UI (browser SPA or Electron desktop): dashboards, model management, investigation, visual analytics.

Architecture, data model, principles and invariants: [`docs/arch/README.md`](docs/arch/README.md).

---

## 3. Architecture: Local Desktop Application
USFDS support both local application development and deployment as client-server architecture. 


With standalone desktop application architecture:
```
+-----------------------------------------------------------+
|                    User's Local Machine                   |
|                                                           |
|   +--------------------+         +--------------------+   |
|   |     usfds-web      |  HTTP   |    usfds-server    |   |
|   |  (Desktop UI /     |<------->| (Local App Engine, |   |
|   |   Frontend Client) |         |  FastAPI Backend)  |   |
|   +--------------------+         +---------+----------+   |
|                                            |              |
|                                   +--------+--------+     |
|                                   |   usfds-infra   |     |
|                                   +----+-------+----+     |
|                                        |       |          |
|                    +-------------------+       +----+     |
|                    |                                |     |
|            +-------v-------+               +--------v--+  |
|            | SQLite (.db)  |               |   Local   |  |
|            |  (WAL Mode)   |               | Storage   |  |
|            +---------------+               +-----------+  |
+-----------------------------------------------------------+
```

With client-server architecture:
```
+-----------------------------------------------------------+
|                   Client-server                           |
|                                                           |
|   +--------------------+         +--------------------+   |
|   |     usfds-web      |  HTTP   |    usfds-server    |   |
|   | (Frontend Client)  |<------->| (FastAPI Backend)  |   |
|   +--------------------+         +---------+----------+   |
|                                            |              |
|                                   +--------+--------+     |
|                                   |   usfds-infra   |     |
|                                   +----+-------+----+     |
|                                        |       |          |
|                    +-------------------+       +----+     |
|                    |                                |     |
|            +-------v-------+               +--------v--+  |
|            | PostgreSQL    |               |   Cloud   |  |
|            |               |               | Storage   |  |
|            |               |               | (S3, R2,  |  |
|            |               |               | MinIO)    |  |
|            +---------------+               +------------+ |
+-----------------------------------------------------------+
```

In client–server mode, `usfds-worker` consumes heavy jobs from BullMQ on PostgreSQL, and training can optionally run on Modal remote compute. Runtime details: [`docs/arch/01-context-and-runtime.md`](docs/arch/01-context-and-runtime.md). <!-- [26-11-28] -->
