"""The PostgreSQL compatibility guard (G2/G3) is active in every test and catches SQLite-only SQL."""
from uuid import uuid4

import pytest
from sqlalchemy import column, func, select, table, text

from usfds_infra.database.case_repositories import SqliteCaseRepository
from usfds_infra.database.compat import sqlite_only
from usfds_infra.testing.pg_compat import PostgresCompatibilityError, find_sqlite_only_sql


def test_guard_rejects_sqlite_only_function_in_orm_statement(db_engine):
	stmt = select(func.group_concat(column("name"))).select_from(table("projects"))
	with db_engine.connect() as connection:
		with pytest.raises(PostgresCompatibilityError, match="group_concat"):
			connection.execute(stmt)


def test_guard_rejects_sqlite_only_function_in_raw_sql(db_engine):
	with db_engine.connect() as connection:
		with pytest.raises(PostgresCompatibilityError, match="strftime"):
			connection.exec_driver_sql("SELECT strftime('%Y', 'now')")


def test_guard_allows_portable_sql_and_json_operators(db_engine):
	with db_engine.connect() as connection:
		assert connection.execute(select(func.coalesce(None, 1))).scalar_one() == 1
		assert connection.execute(text("SELECT 1")).scalar_one() == 1


def test_guard_skips_deliberate_dialect_branch_wrapped_in_sqlite_only(db_engine):
	with db_engine.connect() as connection, sqlite_only():
		assert connection.exec_driver_sql("SELECT ifnull(NULL, 7)").scalar_one() == 7


def test_denylist_finds_json_each():
	assert find_sqlite_only_sql("SELECT 1 FROM json_each(fraud_cases.triggered_rule_codes)")


@pytest.mark.xfail(strict=True, raises=PostgresCompatibilityError, reason="ISS-018: case rule_code filter uses SQLite json_each")
def test_case_search_by_rule_code_is_postgresql_compatible(db_session):
	SqliteCaseRepository(db_session).search(uuid4(), {"rule_code": "R1"}, "priority", 1, 20)
