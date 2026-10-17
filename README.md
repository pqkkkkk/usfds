# USFDS (US Fraud Detection System)

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