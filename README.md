# USFDS (Universal Software Fault Detection System)

## 1. Overview
**USFDS** is a machine learning–driven platform designed for detecting credit card transaction fraud. The system provides an end-to-end workflow covering dataset management, automated feature preprocessing, model training, evaluation, batch detection, and explainability, investigation, related insight generation & reporting.

---

## 2. Project Structure
The repository is organized into modular packages under the `usfds-*` prefix:

- **`usfds-core`**: Core domain models, business logic, ML pipelines, and abstract interfaces (repositories, storage).
- **`usfds-infra`**: Infrastructure implementations, including SQLite database persistence (WAL mode) and local filesystem storage.
- **`usfds-server`**: Local application runtime and REST API service (FastAPI) powering the desktop backend.
- **`usfds-web`**: User interface frontend providing interactive dashboards, model management, and visual analytics.
- **`usfds-cli`**: Command-line interface for headless execution of pipelines, training runs, and inspection.
- **`usfds-agent`**: Intelligent assistant integration for conversational queries, investigation, and analysis workflows.

---

## 3. Architecture: Local Desktop Application
Unlike traditional distributed client-server systems, **USFDS is architected as a standalone, local-first Desktop Application**:

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

### Key Architectural Highlights:
- **Local-First & Offline Execution**: The entire system runs locally on the user's machine without requiring external cloud services, remote DBMS, or internet connectivity.
- **Embedded Persistence**:
  - **Database (SQLite)**: Persists application state, run configurations, and metrics in a single file database with Write-Ahead Logging (WAL) for concurrent reads/writes.
  - **Storage (Filesystem)**: Manages datasets, checkpoints, and serialized model artifacts directly on the host file system.
- **Embedded Engine**: `usfds-server` acts as a local sidecar engine communicating with the UI over local loopback (`127.0.0.1`), ensuring zero remote data leakage and full utilization of local hardware (CPU/GPU).
