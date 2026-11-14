"""Alembic environment for USFDS (SQLite desktop + PostgreSQL client-server).

Normally driven programmatically by `usfds_infra.database.migrate` (startup, tests, CLI helpers).
A live connection may be passed via `config.attributes["connection"]`; otherwise `sqlalchemy.url` is used.
"""
from alembic import context
from sqlalchemy import create_engine, pool

from usfds_infra.database.base import Base
from usfds_infra.database import case_models, models  # noqa: F401  (register every table on Base.metadata)

config = context.config
target_metadata = Base.metadata


def _configure_kwargs(dialect_name: str) -> dict:
	return {
		"target_metadata": target_metadata,
		# SQLite cannot ALTER most constraints; batch mode recreates the table instead.
		"render_as_batch": dialect_name == "sqlite",
		"compare_type": True,
	}


def run_migrations_offline() -> None:
	url = config.get_main_option("sqlalchemy.url")
	dialect_name = url.split(":", 1)[0].split("+", 1)[0]
	context.configure(url=url, literal_binds=True, dialect_opts={"paramstyle": "named"}, **_configure_kwargs(dialect_name))
	with context.begin_transaction():
		context.run_migrations()


def _run_with_connection(connection) -> None:
	context.configure(connection=connection, **_configure_kwargs(connection.dialect.name))
	with context.begin_transaction():
		context.run_migrations()


def run_migrations_online() -> None:
	connection = config.attributes.get("connection")
	if connection is not None:
		_run_with_connection(connection)
		return
	engine = create_engine(config.get_main_option("sqlalchemy.url"), poolclass=pool.NullPool)
	with engine.begin() as connection:
		_run_with_connection(connection)
	engine.dispose()


if context.is_offline_mode():
	run_migrations_offline()
else:
	run_migrations_online()
