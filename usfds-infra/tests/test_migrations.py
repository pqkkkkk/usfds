"""Alembic migration contract (ISS-020) and PostgreSQL DDL compatibility (guard G1)."""
import io
from contextlib import redirect_stdout
from uuid import uuid4

from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from usfds_core.domain.entities.system import Project
from usfds_infra.database import Base, SqliteProjectRepository, create_session_factory, create_sqlite_engine, init_db
from usfds_infra.database.migrate import alembic_config, head_revisions, schema_drift


def _current_revision(engine) -> str:
	with engine.connect() as connection:
		return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()


def test_migrations_have_exactly_one_head():
	assert len(head_revisions()) == 1


def test_fresh_database_upgrades_to_head_and_matches_orm_models(tmp_path):
	engine = create_sqlite_engine(tmp_path / "fresh.db")

	init_db(engine)

	assert _current_revision(engine) == head_revisions()[0]
	assert schema_drift(engine) == []
	engine.dispose()


def test_legacy_database_created_by_create_all_keeps_rows_and_reaches_head(tmp_path):
	engine = create_sqlite_engine(tmp_path / "legacy.db")
	Base.metadata.create_all(engine)  # how databases were created before Alembic
	project_id = uuid4()
	factory = create_session_factory(engine)
	with factory() as session:
		SqliteProjectRepository(session).save(Project(project_id=project_id, user_id=uuid4(), project_name="Legacy"))
		session.commit()

	init_db(engine)
	init_db(engine)  # idempotent on every startup

	assert _current_revision(engine) == head_revisions()[0]
	with factory() as session:
		assert SqliteProjectRepository(session).get_by_id(project_id).project_name == "Legacy"
	engine.dispose()


def test_init_db_is_safe_to_call_on_every_startup(tmp_path):
	engine = create_sqlite_engine(tmp_path / "restart.db")
	init_db(engine)
	tables_before = set(inspect(engine).get_table_names())

	init_db(engine)

	assert set(inspect(engine).get_table_names()) == tables_before
	engine.dispose()


def test_all_migrations_render_as_postgresql_sql_offline():
	output = io.StringIO()
	with redirect_stdout(output):
		command.upgrade(alembic_config("postgresql+psycopg://usfds@localhost/usfds"), "head", sql=True)
	sql = output.getvalue()
	assert "CREATE TABLE projects" in sql
	assert "alembic_version" in sql


def test_every_orm_table_and_index_compiles_for_postgresql():
	dialect = postgresql.dialect()
	for table in Base.metadata.sorted_tables:
		if table.name.startswith(("dummy_", "test_")):
			continue
		str(CreateTable(table).compile(dialect=dialect))
		for index in table.indexes:
			str(CreateIndex(index).compile(dialect=dialect))
