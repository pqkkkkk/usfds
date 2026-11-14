"""Pytest fixtures shared by usfds-infra, usfds-worker and usfds-server tests.

Enable in `tests/conftest.py`:  pytest_plugins = ["usfds_infra.testing.pytest_plugin"]
"""
import shutil
import tempfile
from pathlib import Path
from typing import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from usfds_infra.storage.local_storage import LocalFileStorage
from usfds_infra.testing import create_test_database, pg_compat


def pytest_configure(config):
	"""Give each run its own temp root (unless --basetemp is given) so it can be removed as a whole."""
	if not config.option.basetemp:
		config.option.basetemp = tempfile.mkdtemp(prefix="usfds-pytest-")
		config._usfds_owned_basetemp = True


def pytest_sessionfinish(session, exitstatus):
	"""Remove this run's temp files when every test passed; keep them when something failed, for debugging."""
	config = session.config
	basetemp = config.option.basetemp
	if not getattr(config, "_usfds_owned_basetemp", False) or not basetemp:
		return
	if exitstatus == 0:
		shutil.rmtree(basetemp, ignore_errors=True)
	else:
		print(f"\nTemp files kept for debugging: {basetemp}")


@pytest.fixture(autouse=True, scope="session")
def _postgres_compatibility_guard():
	"""Fail any test whose SQL would not run on PostgreSQL (guards G2 + G3). See usfds_infra.testing.pg_compat."""
	pg_compat.install()
	yield
	pg_compat.uninstall()


@pytest.fixture
def db_engine(tmp_path: Path) -> Iterator[Engine]:
	"""Fresh, fully migrated SQLite database for one test."""
	engine, _ = create_test_database(tmp_path / "usfds_test.db")
	yield engine
	engine.dispose()


@pytest.fixture
def session_factory(db_engine: Engine) -> sessionmaker[Session]:
	from usfds_infra.database import create_session_factory

	return create_session_factory(db_engine)


@pytest.fixture
def db_session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
	"""One session; the test decides when to commit. Rolled back and closed afterwards."""
	session = session_factory()
	try:
		yield session
	finally:
		session.rollback()
		session.close()


@pytest.fixture
def local_storage(tmp_path: Path) -> LocalFileStorage:
	return LocalFileStorage(base_dir=tmp_path / "storage")


@pytest.fixture
def s3_storage():
	"""S3FileStorage against moto's in-process S3 (requires `moto[s3]` in the package's dev dependencies)."""
	from moto import mock_aws

	from usfds_infra.storage.s3_storage import S3FileStorage

	with mock_aws():
		yield S3FileStorage(bucket="usfds-test", access_key="test", secret_key="test", region="us-east-1")
