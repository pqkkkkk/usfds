from datetime import datetime, timezone
from uuid import uuid4

import pytest

from usfds_core.domain.entities.case import Case, CaseStatus
from usfds_core.domain.entities.enums import RuleAction
from usfds_core.repositories.base_case_repo import CaseConflictError
from usfds_core.services.investigation.case_service import CaseService
from usfds_infra.database import create_session_factory, create_sqlite_engine, init_db
from usfds_infra.database.case_repositories import SqliteAuditRepository, SqliteBlacklistRepository, SqliteCaseRepository


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