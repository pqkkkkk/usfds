from uuid import uuid4

from usfds_core.domain.entities.enums import ExecutionType, RiskLevel
from usfds_core.domain.entities.model import Model
from usfds_infra.database import SqliteModelRepository, session_scope


def test_get_model_with_risk_level_returns_entity(session_factory):
	"""ISS-035: Reading a model with a non-null risk_level returns RiskLevel enum without NameError."""
	model = Model(
		model_id=uuid4(),
		project_id=uuid4(),
		user_id=uuid4(),
		model_name="xgb_fraud",
		display_name="XGB Fraud",
		execution_type=ExecutionType.BUILTIN,
		risk_level=RiskLevel.HIGH,
	)

	with session_scope(session_factory) as session:
		repo = SqliteModelRepository(session)
		repo.save(model)

	with session_scope(session_factory) as session:
		repo = SqliteModelRepository(session)
		loaded = repo.get_by_id(model.model_id)

	assert loaded is not None
	assert loaded.risk_level == RiskLevel.HIGH
