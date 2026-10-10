from contextlib import contextmanager
from typing import Generator
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from usfds_infra.database.base import Base


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
    """Create all registered database tables if they do not exist."""
    Base.metadata.create_all(bind=engine)


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
