from uuid import uuid4

from usfds_core.domain.entities.enums import ExecutionType, RiskLevel
from usfds_core.domain.entities.model import Model
from usfds_core.domain.entities.system import Project, User
from usfds_infra.database import SqliteModelRepository, SqliteProjectRepository, SqlUserRepository, session_scope


def test_get_model_with_risk_level_returns_entity(session_factory):
	"""ISS-035: Reading a model with a non-null risk_level returns RiskLevel enum without NameError."""
	user_id = uuid4()
	project_id = uuid4()
	model = Model(
		model_id=uuid4(),
		project_id=project_id,
		user_id=user_id,
		model_name="xgb_fraud",
		display_name="XGB Fraud",
		execution_type=ExecutionType.BUILTIN,
		risk_level=RiskLevel.HIGH,
	)

	with session_scope(session_factory) as session:
		SqlUserRepository(session).save(
			User(user_id=user_id, username="u_model", email="u_model@usfds.local", full_name="U", password_hash="h")
		)
		SqliteProjectRepository(session).save(
			Project(project_id=project_id, user_id=user_id, project_name="P")
		)
		repo = SqliteModelRepository(session)
		repo.save(model)

	with session_scope(session_factory) as session:
		repo = SqliteModelRepository(session)
		loaded = repo.get_by_id(model.model_id)

	assert loaded is not None
	assert loaded.risk_level == RiskLevel.HIGH
