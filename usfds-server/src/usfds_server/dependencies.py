from typing import Generator
from fastapi import Depends
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker
from usfds_core.services.data_management.service import DataManagementService

from usfds_infra.database import (
    SqliteDatasetArtifactRepository,
    SqliteDatasetRepository,
    close_db,
    create_session_factory,
    create_sqlite_engine,
    init_db,
)
from usfds_infra.storage.local_storage import LocalFileStorage
from usfds_server.config import settings

# Global singletons managed during application lifecycle
_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_storage: LocalFileStorage | None = None


def setup_infrastructure() -> tuple[Engine, LocalFileStorage]:
    """Initialize database engine, run table schema creation, and initialize storage."""
    global _engine, _session_factory, _storage

    # 1. Setup SQLite Database with WAL mode
    _engine = create_sqlite_engine(db_path=settings.db_path, echo=settings.db_echo)
    _session_factory = create_session_factory(_engine)
    init_db(_engine)

    # 2. Setup Local Storage
    _storage = LocalFileStorage(base_dir=settings.storage_dir)

    return _engine, _storage


def teardown_infrastructure() -> None:
    """Close and dispose of database connections."""
    global _engine
    if _engine is not None:
        close_db(_engine)
        _engine = None


def get_storage() -> LocalFileStorage:
    """FastAPI dependency to retrieve the active LocalFileStorage instance."""
    global _storage
    if _storage is None:
        _storage = LocalFileStorage(base_dir=settings.storage_dir)
    return _storage


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency to yield a database session per request."""
    global _session_factory
    if _session_factory is None:
        setup_infrastructure()

    assert _session_factory is not None
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_dataset_repo(session: Session = Depends(get_db)) -> SqliteDatasetRepository:
    return SqliteDatasetRepository(session)


def get_artifact_repo(session: Session = Depends(get_db)) -> SqliteDatasetArtifactRepository:
    return SqliteDatasetArtifactRepository(session)

def get_data_management_service(
    dataset_repo: SqliteDatasetRepository = Depends(get_dataset_repo),
    artifact_repo: SqliteDatasetArtifactRepository = Depends(get_artifact_repo),
    storage: LocalFileStorage = Depends(get_storage),
) -> DataManagementService:
    return DataManagementService(
        dataset_repo=dataset_repo,
        artifact_repo=artifact_repo,
        file_storage=storage,
    )


__all__ = [
    "setup_infrastructure",
    "teardown_infrastructure",
    "get_storage",
    "get_db",
    "get_dataset_repo",
    "get_artifact_repo",
    "get_data_management_service",
    "get_validation_service",
    "get_raw_ingestion_service",
    "get_mapping_service",
    "get_feature_engineering_service",
    "get_lineage_service",
    "get_export_service",
]
