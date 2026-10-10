from contextlib import asynccontextmanager
from typing import Any, Dict
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
import uvicorn

from usfds_infra.storage.local_storage import LocalFileStorage
from usfds_server.config import settings
from usfds_server.dependencies import (
    get_db,
    get_storage,
    setup_infrastructure,
    teardown_infrastructure,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB tables and Storage directories
    setup_infrastructure()
    yield
    # Shutdown: Clean up connections
    teardown_infrastructure()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Backend API server for USFDS desktop and local environments.",
    lifespan=lifespan,
)


@app.get("/health", tags=["System"])
def health_check(
    db: Session = Depends(get_db),
    storage: LocalFileStorage = Depends(get_storage),
) -> Dict[str, Any]:
    """Health check endpoint validating SQLite connection and Local File Storage."""
    # Verify DB connection & SQLite pragmas
    try:
        db.execute(text("SELECT 1")).scalar()
        journal_mode = db.execute(text("PRAGMA journal_mode;")).scalar()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database check failed: {e}")

    # Verify Storage directory
    storage_accessible = storage.base_dir.is_dir()

    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "database": {
            "status": "connected",
            "type": "sqlite",
            "path": settings.db_path,
            "journal_mode": str(journal_mode).upper(),
        },
        "storage": {
            "status": "ready" if storage_accessible else "error",
            "type": "local_filesystem",
            "base_dir": str(storage.base_dir),
        },
    }


def run_server():
    """CLI Entrypoint to start the server."""
    uvicorn.run(
        "usfds_server.api:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run_server()
