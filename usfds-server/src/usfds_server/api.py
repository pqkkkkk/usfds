from contextlib import asynccontextmanager
from typing import Any, Dict
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
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
from usfds_server.routers import dataset_router
from usfds_server.schemas.base_response import ApiResponse


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


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiResponse.fail(
            error=exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            status_code=exc.status_code,
        ).model_dump(by_alias=True),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_msg = "; ".join(
        f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in exc.errors()
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ApiResponse.fail(
            error=error_msg,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message="Request validation error",
        ).model_dump(by_alias=True),
    )


# Register routers
app.include_router(dataset_router)


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
