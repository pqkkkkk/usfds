"""Shared test infrastructure for USFDS packages (no Docker, no network).

- Database: a fresh SQLite file per test, created by the same schema path as production startup.
- Storage: LocalFileStorage in a temp dir, or S3FileStorage backed by moto (in-process S3 emulator).

Use the pytest fixtures in `usfds_infra.testing.pytest_plugin` by adding to a package's `tests/conftest.py`:

	pytest_plugins = ["usfds_infra.testing.pytest_plugin"]
"""
from pathlib import Path
from typing import Tuple, Union

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from usfds_infra.database import create_session_factory, create_sqlite_engine, init_db


def create_test_database(db_path: Union[str, Path]) -> Tuple[Engine, sessionmaker[Session]]:
	"""Create a migrated SQLite database at `db_path` and return (engine, session_factory)."""
	engine = create_sqlite_engine(db_path=db_path)
	init_db(engine)
	return engine, create_session_factory(engine)


__all__ = ["create_test_database"]
