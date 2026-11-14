"""PostgreSQL compatibility guard for SQLite-backed tests (guards G2 + G3, see .plan/parallel_agent_setup.md §3.3).

Installed for every test by `usfds_infra.testing.pytest_plugin`. On every statement executed on a SQLite engine:
- G2: the SQLAlchemy statement is compiled with the PostgreSQL dialect; a compile error fails the test.
- G3: the PostgreSQL-compiled SQL (or raw driver SQL) is scanned for functions/operators that exist only in SQLite.

Limits: semantic differences are NOT detected (LIKE case sensitivity, SQLite's loose typing, implicit row order,
timezone comparisons). Those are covered by conventions in skill `usfds-testing` and by end-to-end tests on PostgreSQL.
Deliberate dialect branches: wrap them in `usfds_infra.database.compat.sqlite_only()`.
"""
import re
from typing import List, Tuple

from sqlalchemy import event
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Engine
from sqlalchemy.exc import CompileError

from usfds_infra.database.compat import in_sqlite_only_block

# (pattern, PostgreSQL alternative). Patterns match function calls / operators, case-insensitive.
SQLITE_ONLY_SQL: List[Tuple[str, str]] = [
	(r"\bjson_each\s*\(", "json_array_elements(_text) / jsonb_array_elements(_text); or filter in Python"),
	(r"\bjson_tree\s*\(", "jsonb_path_query"),
	(r"\bjson_extract\s*\(", "SQLAlchemy JSON index operators (column['key']) which compile per dialect"),
	(r"\bjson_group_array\s*\(", "json_agg / func.json_agg"),
	(r"\bjson_group_object\s*\(", "json_object_agg"),
	(r"\bgroup_concat\s*\(", "string_agg / func.string_agg"),
	(r"\bstrftime\s*\(", "func.to_char / extract(); or compute in Python"),
	(r"\bjulianday\s*\(", "extract(epoch from ...)"),
	(r"\bdatetime\s*\(", "now() / CAST(... AS timestamp)"),
	(r"\bifnull\s*\(", "coalesce / func.coalesce"),
	(r"\binstr\s*\(", "strpos / position(... in ...)"),
	(r"\bprintf\s*\(", "format()"),
	(r"\bglob\b", "LIKE / ~ (regex)"),
	(r"\bcollate\s+nocase\b", "ilike / lower()"),
	# PRAGMA is not listed: SQLAlchemy's own SQLite inspector issues PRAGMA table_info; PRAGMA fails loudly on PostgreSQL anyway.
]
_COMPILED = [(re.compile(p, re.IGNORECASE), alt) for p, alt in SQLITE_ONLY_SQL]
_PG_DIALECT = postgresql.dialect()


class PostgresCompatibilityError(AssertionError):
	"""Raised (as a test failure) when SQL executed in tests would not run correctly on PostgreSQL."""


def find_sqlite_only_sql(sql: str) -> List[str]:
	"""Return human-readable violations for SQLite-only constructs in `sql` (empty list = OK)."""
	return [f"{rx.pattern} -> use {alt}" for rx, alt in _COMPILED if rx.search(sql)]


def _check(sql: str, origin: str) -> None:
	violations = find_sqlite_only_sql(sql)
	if violations:
		raise PostgresCompatibilityError(
			f"SQLite-only SQL in {origin} would fail or behave differently on PostgreSQL:\n"
			f"  {'; '.join(violations)}\n  SQL: {sql[:500]}"
		)


def _skip(conn) -> bool:
	return conn.dialect.name != "sqlite" or in_sqlite_only_block()


def _before_execute(conn, clauseelement, multiparams, params, execution_options):
	if _skip(conn) or not hasattr(clauseelement, "compile"):
		return
	try:
		pg_sql = str(clauseelement.compile(dialect=_PG_DIALECT))
	except CompileError as e:
		raise PostgresCompatibilityError(f"Statement does not compile for PostgreSQL: {e}") from e
	_check(pg_sql, "SQLAlchemy statement")


def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
	# Statements compiled from SQLAlchemy constructs were checked in _before_execute (in PostgreSQL form);
	# here only raw driver SQL (exec_driver_sql) is left.
	if _skip(conn) or (context is not None and getattr(context, "compiled", None) is not None):
		return
	_check(statement, "raw driver SQL")


def install() -> None:
	if not event.contains(Engine, "before_execute", _before_execute):
		event.listen(Engine, "before_execute", _before_execute)
		event.listen(Engine, "before_cursor_execute", _before_cursor_execute)


def uninstall() -> None:
	if event.contains(Engine, "before_execute", _before_execute):
		event.remove(Engine, "before_execute", _before_execute)
		event.remove(Engine, "before_cursor_execute", _before_cursor_execute)
