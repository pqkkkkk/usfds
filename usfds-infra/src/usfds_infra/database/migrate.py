"""Schema migrations (Alembic) for USFDS — single entry point for startup, tests and developers.

Runtime:
	upgrade_database(engine)   called by init_db(); brings any database (new, legacy or current) to head.

Developer CLI (run inside usfds-infra: `poetry run python -m usfds_infra.database.migrate <cmd>`):
	revision "<message>"       autogenerate a new revision from model changes (diffs against a temp SQLite at head)
	check                      exit 1 if ORM models and migrations disagree (also used by tests)
	sql [dialect_url]          print the offline SQL of all migrations (default: PostgreSQL)
	heads                      print current head revision(s); must be exactly one before merge
"""
import logging
import sys
import tempfile
from pathlib import Path
from typing import Any, List, Optional

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, inspect

from usfds_infra.database.base import Base

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def alembic_config(url: Optional[str] = None) -> Config:
	cfg = Config()
	cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
	if url:
		cfg.set_main_option("sqlalchemy.url", url)
	return cfg


def _run_legacy_fixups(engine: Engine) -> None:
	"""Pre-Alembic, hand-written SQLite fix-ups for databases created by `create_all` (kept for old desktop DBs)."""
	from usfds_infra.database.case_migration import migrate_case_sources

	if inspect(engine).has_table("fraud_cases"):
		migrate_case_sources(engine)


def upgrade_database(engine: Engine) -> None:
	"""Upgrade `engine`'s database to the latest revision without touching existing data.

	- New database: every revision runs, starting with the baseline.
	- Legacy database (created by the old `create_all`, no `alembic_version`): the baseline revision only creates
	  tables that are missing, so existing tables and rows are kept; later revisions then apply normally.
	- Afterwards, any remaining difference between the database and the ORM models is logged as a warning.
	"""
	if not inspect(engine).has_table("alembic_version"):
		_run_legacy_fixups(engine)
	with engine.begin() as connection:
		cfg = alembic_config()
		cfg.attributes["connection"] = connection
		command.upgrade(cfg, "head")
	drift = schema_drift(engine)
	if drift:
		logger.warning(
			"Database schema differs from ORM models after migration (%d differences). "
			"Write an Alembic revision for them: %s",
			len(drift),
			drift,
		)


def schema_drift(engine: Engine) -> List[Any]:
	"""Differences between the live database schema and `Base.metadata` (empty list = in sync)."""
	from usfds_infra.database import case_models, models  # noqa: F401  (register tables)

	with engine.connect() as connection:
		context = MigrationContext.configure(connection, opts={"compare_type": False})
		diffs = compare_metadata(context, Base.metadata)
	# Tables defined only by tests (declared on Base inside test modules) are not part of the product schema.
	return [d for d in diffs if not _is_test_only_table(d)]


def _is_test_only_table(diff: Any) -> bool:
	table = diff[1] if isinstance(diff, tuple) and len(diff) > 1 else None
	name = getattr(table, "name", None) or getattr(getattr(table, "table", None), "name", "")
	return str(name).startswith(("dummy_", "test_"))


def head_revisions() -> List[str]:
	return list(ScriptDirectory.from_config(alembic_config()).get_heads())


def _temp_sqlite_at_head(tmp_dir: str) -> Engine:
	from usfds_infra.database.engine import create_sqlite_engine

	engine = create_sqlite_engine(Path(tmp_dir) / "migrate_scratch.db")
	upgrade_database(engine)
	return engine


def _cli(argv: List[str]) -> int:
	if not argv:
		print(__doc__)
		return 2
	cmd, args = argv[0], argv[1:]
	if cmd == "heads":
		heads = head_revisions()
		print("\n".join(heads))
		return 0 if len(heads) == 1 else 1
	if cmd == "sql":
		url = args[0] if args else "postgresql+psycopg://usfds@localhost/usfds"
		command.upgrade(alembic_config(url), "head", sql=True)
		return 0
	with tempfile.TemporaryDirectory() as tmp_dir:
		engine = _temp_sqlite_at_head(tmp_dir)
		try:
			if cmd == "check":
				drift = schema_drift(engine)
				for d in drift:
					print(d)
				return 1 if drift else 0
			if cmd == "revision":
				if not args:
					print('usage: revision "<message>"')
					return 2
				cfg = alembic_config(str(engine.url))
				command.revision(cfg, message=args[0], autogenerate=True)
				return 0
		finally:
			engine.dispose()
	print(__doc__)
	return 2


if __name__ == "__main__":
	sys.exit(_cli(sys.argv[1:]))
