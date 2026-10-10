# USFDS Server

FastAPI-based Backend Server for the Universal Software Fault Detection System (USFDS).

## How to Run

Navigate to the `usfds-server` directory:

```bash
cd usfds-server
```

### Option 1: Standard Run (CLI Entrypoint)
```bash
poetry run usfds-server
```

### Option 2: Development Mode (Auto-reload on code change)
```bash
poetry run uvicorn usfds_server.api:app --reload --port 8000
```

### Option 3: Run with Python module
```bash
poetry run python -m usfds_server.api
```

## Health Check & API Docs

After running the server:
- **API Documentation (Swagger UI)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check Endpoint**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

## Environment Variables Configuration

| Variable | Default | Description |
| :--- | :--- | :--- |
| `USFDS_DB_PATH` | `usfds.db` | Path to SQLite database file |
| `USFDS_STORAGE_DIR` | `storage_output` | Directory for local file/dataset storage |
| `USFDS_HOST` | `127.0.0.1` | Host address |
| `USFDS_PORT` | `8000` | Port number |
| `USFDS_DB_ECHO` | `false` | Enable SQL statement logging |
