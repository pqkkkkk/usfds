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
	from usfds_core.domain.entities.system import User
	from usfds_infra.database import SqlUserRepository

	engine = create_sqlite_engine(tmp_path / "legacy.db")
	Base.metadata.create_all(engine)  # how databases were created before Alembic
	project_id = uuid4()
	user_id = uuid4()
	factory = create_session_factory(engine)
	with factory() as session:
		SqlUserRepository(session).save(
			User(user_id=user_id, username="legacy_owner", email="legacy@usfds.local", full_name="Legacy", password_hash="h")
		)
		SqliteProjectRepository(session).save(Project(project_id=project_id, user_id=user_id, project_name="Legacy"))
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


def test_user_id_and_fk_migration_backfills_enforces_fks_and_renders_pg(tmp_path):
	"""ISS-043 & ISS-023: Migration adds NOT NULL user_id with backfill, cleans builtin model user_id, and enforces FKs."""
	import pytest
	from sqlalchemy.exc import IntegrityError
	from usfds_infra.database.models import DatasetModel, DetectionJobModel, MLModel, ModelVersionModel, RuleModel, TrainingRunModel, UserModel

	db_file = tmp_path / "fk_mig.db"
	engine = create_sqlite_engine(db_file)
	cfg = alembic_config(f"sqlite:///{db_file.as_posix()}")
	command.upgrade(cfg, "845d529c5502")

	alice_id = str(uuid4())
	proj_id = str(uuid4())
	builtin_model_id = str(uuid4())
	custom_model_id = str(uuid4())
	rule_id = str(uuid4())
	job_id = str(uuid4())
	run_id = str(uuid4())
	ver_id = str(uuid4())

	with engine.begin() as conn:
		conn.execute(
			text(
				"INSERT INTO users (user_id, username, email, full_name, password_hash, status, created_at, updated_at) "
				"VALUES (:uid, 'alice', 'alice@usfds.local', 'Alice', 'hash', 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
			),
			{"uid": alice_id},
		)
		conn.execute(
			text(
				"INSERT INTO projects (project_id, project_name, user_id, status, created_at, updated_at) "
				"VALUES (:pid, 'Proj A', :uid, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
			),
			{"pid": proj_id, "uid": alice_id},
		)
		conn.execute(
			text(
				"INSERT INTO models (model_id, project_id, user_id, model_name, execution_type, created_at, updated_at) "
				"VALUES (:mid, NULL, '00000000-0000-0000-0000-000000000000', 'random_forest', 'BUILTIN', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
			),
			{"mid": builtin_model_id},
		)
		conn.execute(
			text(
				"INSERT INTO models (model_id, project_id, user_id, model_name, execution_type, created_at, updated_at) "
				"VALUES (:mid, :pid, :uid, 'custom_rf', 'SCRIPT', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
			),
			{"mid": custom_model_id, "pid": proj_id, "uid": alice_id},
		)
		conn.execute(
			text(
				"INSERT INTO rules (rule_id, project_id, rule_code, name, status, created_by, created_at, updated_at) "
				"VALUES (:rid, :pid, 'R-01', 'Rule 1', 'ACTIVE', 'alice', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
			),
			{"rid": rule_id, "pid": proj_id},
		)
		conn.execute(
			text(
				"INSERT INTO detection_jobs (job_id, project_id, input_path, score_threshold, use_rules, status, created_by, created_at) "
				"VALUES (:jid, :pid, 'raw.csv', 0.5, 1, 'COMPLETED', 'alice', CURRENT_TIMESTAMP)"
			),
			{"jid": job_id, "pid": proj_id},
		)
		conn.execute(
			text(
				"INSERT INTO training_runs (run_id, project_id, model_id, run_name, status, default_threshold, created_by, created_at) "
				"VALUES (:run_id, :pid, :mid, 'Run 1', 'COMPLETED', 0.5, 'alice', CURRENT_TIMESTAMP)"
			),
			{"run_id": run_id, "pid": proj_id, "mid": custom_model_id},
		)
		conn.execute(
			text(
				"INSERT INTO model_versions (version_id, model_id, project_id, run_id, semver, artifact_uri, decision_threshold, status, registered_by, registered_at) "
				"VALUES (:vid, :mid, :pid, :run_id, 'v1', 'models/v1.zip', 0.5, 'CANDIDATE', NULL, CURRENT_TIMESTAMP)"
			),
			{"vid": ver_id, "mid": custom_model_id, "pid": proj_id, "run_id": run_id},
		)

	init_db(engine)
	assert schema_drift(engine) == []

	factory = create_session_factory(engine)
	with factory() as session:
		assert session.get(MLModel, builtin_model_id).user_id is None
		assert session.get(MLModel, custom_model_id).user_id == alice_id
		assert session.get(RuleModel, rule_id).user_id == alice_id
		assert session.get(DetectionJobModel, job_id).user_id == alice_id
		assert session.get(TrainingRunModel, run_id).user_id == alice_id
		assert session.get(ModelVersionModel, ver_id).user_id == alice_id

		# FK violation: non-existent user_id
		with pytest.raises(IntegrityError):
			with session.begin_nested():
				session.add(
					DatasetModel(
						dataset_id=str(uuid4()),
						project_id=proj_id,
						user_id=str(uuid4()),
						dataset_name="bad_user_ds",
					)
				)
				session.flush()

		# FK violation: non-existent project_id
		with pytest.raises(IntegrityError):
			with session.begin_nested():
				session.add(
					RuleModel(
						rule_id=str(uuid4()),
						project_id=str(uuid4()),
						user_id=alice_id,
						rule_code="R-BAD",
						name="Bad Proj",
					)
				)
				session.flush()

		# ON DELETE RESTRICT prevents deleting user who owns resources
		with pytest.raises(IntegrityError):
			with session.begin_nested():
				session.delete(session.get(UserModel, alice_id))
				session.flush()

	engine.dispose()
