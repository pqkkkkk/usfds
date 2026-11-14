from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import MetaData, inspect

from usfds_core.domain.entities.case import BlacklistEntityType, Case, CaseStatus, EntityBlacklist
from usfds_core.domain.entities.enums import RuleAction
from usfds_core.repositories.base_case_repo import CaseConflictError
from usfds_core.services.investigation.case_service import BlacklistService, CaseService
from usfds_infra.database import create_session_factory, create_sqlite_engine, init_db
from usfds_infra.database.case_repositories import SqliteAuditRepository, SqliteBlacklistRepository, SqliteCaseRepository
from usfds_infra.database.case_models import AuditLogModel, CaseModel, EntityBlacklistModel


def test_case_unique_cas_and_transactional_audit(tmp_path):
	engine = create_sqlite_engine(tmp_path / "cases.db")
	init_db(engine)
	factory = create_session_factory(engine)
	project_id = uuid4()
	case = Case(project_id, "TX-1", "U1", datetime.now(timezone.utc), 100, RuleAction.REVIEW, uuid4())
	with factory() as session:
		service = CaseService(SqliteCaseRepository(session), SqliteAuditRepository(session), SqliteBlacklistRepository(session))
		assert service.intake([case], "A")["accepted_count"] == 1
		session.commit()
	with factory() as session:
		service = CaseService(SqliteCaseRepository(session), SqliteAuditRepository(session), SqliteBlacklistRepository(session))
		assert service.intake([case], "A")["accepted_count"] == 0
		claimed, _ = service.update(project_id, case.case_id, 1, "claim", "A")
		assert claimed.version == 2
		session.commit()
	with factory() as session:
		repo = SqliteCaseRepository(session)
		stale = repo.get_by_id(case.case_id)
		with pytest.raises(CaseConflictError):
			repo.save(stale, 1)
		session.rollback()
	with factory() as session:
		service = CaseService(SqliteCaseRepository(session), SqliteAuditRepository(session), SqliteBlacklistRepository(session))
		service.update(project_id, case.case_id, 2, "resolve-fraud", "A", reason="OTHER_FRAUD", summary="Confirmed evidence of fraudulent payment")
		session.rollback()
	with factory() as session:
		repo, audit = SqliteCaseRepository(session), SqliteAuditRepository(session)
		assert repo.get_by_id(case.case_id).status == CaseStatus.IN_PROGRESS
		assert len(audit.list_for_entity(project_id, "CASE", str(case.case_id))) == 2
		assert repo.search(project_id, {"q": "TX-1"}, "priority", 1, 10)[1] == 1
	engine.dispose()


def test_case_source_migration_preserves_data_and_blocks_legacy_data_loss(tmp_path):
	engine = create_sqlite_engine(tmp_path / "upgrade.db")
	old_metadata = MetaData()
	old_table = CaseModel.__table__.to_metadata(old_metadata)
	old_table.c.dataset_artifact_id.nullable = False
	old_metadata.create_all(engine)
	AuditLogModel.__table__.create(engine)
	EntityBlacklistModel.__table__.create(engine)
	factory = create_session_factory(engine)
	project_id = uuid4()
	case = Case(project_id, "OLD-TX", "U1", datetime.now(timezone.utc), 100, RuleAction.REVIEW, uuid4())
	with factory() as session:
		CaseService(SqliteCaseRepository(session), SqliteAuditRepository(session), SqliteBlacklistRepository(session)).intake([case], "local-analyst")
		BlacklistService(SqliteBlacklistRepository(session), SqliteAuditRepository(session)).add(EntityBlacklist(
			project_id, BlacklistEntityType.USER_ID, "U1", "Confirmed suspicious account", "local-analyst", source_case_id=case.case_id))
		session.commit()
	with engine.begin() as connection:
		connection.exec_driver_sql("CREATE TABLE investigation_cases (case_id TEXT)")
	init_db(engine)
	assert not inspect(engine).has_table("investigation_cases")
	assert next(column for column in inspect(engine).get_columns("fraud_cases") if column["name"] == "dataset_artifact_id")["nullable"]
	with factory() as session:
		assert SqliteCaseRepository(session).get_by_id(case.case_id).event_id == "OLD-TX"
		assert len(SqliteAuditRepository(session).list_for_entity(project_id, "CASE", str(case.case_id))) == 1
		assert SqliteBlacklistRepository(session).list_by_project(project_id)[0].source_case_id == case.case_id
	with engine.begin() as connection:
		# Simulate a pre-Alembic database again: legacy fix-ups only run when there is no alembic_version table.
		connection.exec_driver_sql("DROP TABLE alembic_version")
		connection.exec_driver_sql("CREATE TABLE investigation_cases (case_id TEXT)")
		connection.exec_driver_sql("INSERT INTO investigation_cases VALUES ('preserve-me')")
	with pytest.raises(RuntimeError, match="contains data"):
		init_db(engine)
	with engine.connect() as connection:
		assert connection.exec_driver_sql("SELECT COUNT(*) FROM investigation_cases").scalar_one() == 1
	engine.dispose()