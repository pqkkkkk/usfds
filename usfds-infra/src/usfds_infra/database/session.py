from contextlib import contextmanager
from typing import Generator
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from usfds_infra.database.base import Base
from usfds_infra.database.case_migration import migrate_case_sources


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a configured sessionmaker bound to the given engine."""
    return sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations.
    
    Usage:
        with session_scope(factory) as session:
            repo = SqliteDatasetRepository(session)
            repo.save(entity)
    """
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """Dependency generator for FastAPI endpoints.
    
    Usage:
        app.dependency_overrides[...] or Depends(get_db)
    """
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(engine: Engine) -> None:
    """Migrate the database to the latest schema revision (Alembic). Safe for new, legacy and current databases."""
    from usfds_infra.database.migrate import upgrade_database

    upgrade_database(engine)
    # DEPRECATED [26-11-14]: create_all never altered existing tables (ISS-020); replaced by Alembic migrations.
    # Base.metadata.create_all(bind=engine)
    # migrate_case_sources(engine)  # now run once for legacy databases by migrate._run_legacy_fixups


def close_db(engine: Engine) -> None:
    """Dispose of the database engine connection pool."""
    engine.dispose()


__all__ = [
    "create_session_factory",
    "session_scope",
    "get_db",
    "init_db",
    "close_db",
]
