"""Marker for deliberately dialect-specific SQL.

Tests run on SQLite but production also runs on PostgreSQL. The test-only PostgreSQL compatibility guard
(`usfds_infra.testing.pg_compat`) rejects SQLite-only SQL. Code that branches on the dialect on purpose
(e.g. `if engine.dialect.name == "sqlite": ...PRAGMA...`) wraps that branch in `sqlite_only()` so the guard skips it.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_SQLITE_ONLY: ContextVar[bool] = ContextVar("usfds_sqlite_only", default=False)


@contextmanager
def sqlite_only() -> Iterator[None]:
	token = _SQLITE_ONLY.set(True)
	try:
		yield
	finally:
		_SQLITE_ONLY.reset(token)


def in_sqlite_only_block() -> bool:
	return _SQLITE_ONLY.get()


__all__ = ["sqlite_only", "in_sqlite_only_block"]
