from typing import Generator
from uuid import UUID
from fastapi import Depends
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker
from usfds_core.domain.entities.enums import ExecutionType
from usfds_core.domain.entities.model import Model
from usfds_core.domain.schemas.training_payload import TrainingRunPayload
from usfds_core.services.data_management.service import DataManagementService
from usfds_core.services.inference.inference_service import InferenceService
from usfds_core.services.project_management.project_service import ProjectManagementService
from usfds_core.services.rule_engine.executor import RuleExecutor
from usfds_core.services.rule_engine.manager import RuleManager
from usfds_core.services.training.dispatchers.local_dispatcher import SynchronousRunDispatcher
from usfds_core.services.training.executor import TrainingRunExecutor
from usfds_core.services.training.notifiers.base_notifier import CallbackResultNotifier
from usfds_core.services.training.plugins.register import ModelPluginRegistrationService
from usfds_core.services.training.training_service import TrainingOrchestrationService

from usfds_infra.database import (
	SqliteDatasetArtifactRepository,
	SqliteDatasetRepository,
	SqliteDetectionJobRepository,
	SqliteInvestigationCaseRepository,
	SqliteModelRepository,
	SqliteModelVersionRepository,
	SqliteProjectRepository,
	SqliteRuleRepository,
	SqliteRuleVersionRepository,
	SqliteTrainingRunRepository,
	close_db,
	create_session_factory,
	create_sqlite_engine,
	init_db,
)
from usfds_infra.storage.local_storage import LocalFileStorage
from usfds_server.config import settings

# Global singletons managed during application lifecycle
_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_storage: LocalFileStorage | None = None


SYSTEM_USER_ID = UUID("00000000-0000-0000-0000-000000000000")
BUILTIN_RANDOM_FOREST_ID = UUID("00000000-0000-0000-0000-000000000001")
BUILTIN_XGBOOST_ID = UUID("00000000-0000-0000-0000-000000000002")


def seed_builtin_models(session_factory: sessionmaker[Session]) -> None:
    """Pre-seed system-provided built-in models into the Model Registry."""
    builtins = [
        Model(
            model_id=BUILTIN_RANDOM_FOREST_ID,
            model_name="random_forest",
            user_id=SYSTEM_USER_ID,
            display_name="Random Forest Classifier",
            description="Built-in Random Forest classifier with automated tabular preprocessing.",
            execution_type=ExecutionType.BUILTIN,
            default_hyperparameters={"n_estimators": 100, "max_depth": 10, "random_state": 42},
            hyperparameter_schema={
                "type": "object",
                "properties": {
                    "n_estimators": {"type": "integer", "default": 100, "minimum": 1},
                    "max_depth": {"type": "integer", "default": 10, "minimum": 1},
                    "random_state": {"type": "integer", "default": 42},
                },
            },
        ),
        Model(
            model_id=BUILTIN_XGBOOST_ID,
            model_name="xgboost",
            user_id=SYSTEM_USER_ID,
            display_name="XGBoost Classifier",
            description="Built-in XGBoost gradient boosting classifier with automated tabular preprocessing.",
            execution_type=ExecutionType.BUILTIN,
            default_hyperparameters={"n_estimators": 100, "max_depth": 6, "learning_rate": 0.1, "random_state": 42},
            hyperparameter_schema={
                "type": "object",
                "properties": {
                    "n_estimators": {"type": "integer", "default": 100, "minimum": 1},
                    "max_depth": {"type": "integer", "default": 6, "minimum": 1},
                    "learning_rate": {"type": "number", "default": 0.1, "minimum": 0.0001},
                    "random_state": {"type": "integer", "default": 42},
                },
            },
        ),
    ]

    with session_factory() as session:
        repo = SqliteModelRepository(session)
        for m in builtins:
            if repo.get_by_id(m.model_id) is None:
                repo.save(m)
        session.commit()


def setup_infrastructure() -> tuple[Engine, LocalFileStorage]:
    """Initialize database engine, run table schema creation, pre-seed built-in models, and initialize storage."""
    global _engine, _session_factory, _storage

    # 1. Setup SQLite Database with WAL mode
    _engine = create_sqlite_engine(db_path=settings.db_path, echo=settings.db_echo)
    _session_factory = create_session_factory(_engine)
    init_db(_engine)
    seed_builtin_models(_session_factory)

    # 2. Setup Local Storage
    _storage = LocalFileStorage(base_dir=settings.storage_dir)

    return _engine, _storage


def teardown_infrastructure() -> None:
    """Close and dispose of database connections."""
    global _engine
    if _engine is not None:
        close_db(_engine)
        _engine = None


def get_storage() -> LocalFileStorage:
    """FastAPI dependency to retrieve the active LocalFileStorage instance."""
    global _storage
    if _storage is None:
        _storage = LocalFileStorage(base_dir=settings.storage_dir)
    return _storage


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency to yield a database session per request."""
    global _session_factory
    if _session_factory is None:
        setup_infrastructure()

    assert _session_factory is not None
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_project_repo(session: Session = Depends(get_db)) -> SqliteProjectRepository:
    return SqliteProjectRepository(session)


def get_dataset_repo(session: Session = Depends(get_db)) -> SqliteDatasetRepository:
    return SqliteDatasetRepository(session)


def get_artifact_repo(session: Session = Depends(get_db)) -> SqliteDatasetArtifactRepository:
    return SqliteDatasetArtifactRepository(session)


def get_rule_repo(session: Session = Depends(get_db)) -> SqliteRuleRepository:
    return SqliteRuleRepository(session)


def get_rule_version_repo(session: Session = Depends(get_db)) -> SqliteRuleVersionRepository:
    return SqliteRuleVersionRepository(session)


def get_model_repo(session: Session = Depends(get_db)) -> SqliteModelRepository:
    return SqliteModelRepository(session)


def get_model_version_repo(session: Session = Depends(get_db)) -> SqliteModelVersionRepository:
    return SqliteModelVersionRepository(session)


def get_training_run_repo(session: Session = Depends(get_db)) -> SqliteTrainingRunRepository:
	return SqliteTrainingRunRepository(session)


def get_detection_job_repo(session: Session = Depends(get_db)) -> SqliteDetectionJobRepository:
	return SqliteDetectionJobRepository(session)


def get_investigation_case_repo(session: Session = Depends(get_db)) -> SqliteInvestigationCaseRepository:
	return SqliteInvestigationCaseRepository(session)


def get_project_management_service(
    project_repo: SqliteProjectRepository = Depends(get_project_repo),
    dataset_repo: SqliteDatasetRepository = Depends(get_dataset_repo),
    artifact_repo: SqliteDatasetArtifactRepository = Depends(get_artifact_repo),
    rule_repo: SqliteRuleRepository = Depends(get_rule_repo),
    storage: LocalFileStorage = Depends(get_storage),
) -> ProjectManagementService:
    return ProjectManagementService(
        project_repo=project_repo,
        dataset_repo=dataset_repo,
        artifact_repo=artifact_repo,
        rule_repo=rule_repo,
        file_storage=storage,
    )


def get_rule_manager(
    rule_repo: SqliteRuleRepository = Depends(get_rule_repo),
    version_repo: SqliteRuleVersionRepository = Depends(get_rule_version_repo),
    project_repo: SqliteProjectRepository = Depends(get_project_repo),
) -> RuleManager:
    return RuleManager(
        rule_repo=rule_repo,
        version_repo=version_repo,
        project_repo=project_repo,
    )


def get_rule_executor() -> RuleExecutor:
    return RuleExecutor()


def get_data_management_service(
    dataset_repo: SqliteDatasetRepository = Depends(get_dataset_repo),
    artifact_repo: SqliteDatasetArtifactRepository = Depends(get_artifact_repo),
    project_repo: SqliteProjectRepository = Depends(get_project_repo),
    project_service: ProjectManagementService = Depends(get_project_management_service),
    storage: LocalFileStorage = Depends(get_storage),
) -> DataManagementService:
    return DataManagementService(
        dataset_repo=dataset_repo,
        artifact_repo=artifact_repo,
        file_storage=storage,
        project_repo=project_repo,
        project_service=project_service,
    )


def get_training_service(
    model_repo: SqliteModelRepository = Depends(get_model_repo),
    model_version_repo: SqliteModelVersionRepository = Depends(get_model_version_repo),
    training_run_repo: SqliteTrainingRunRepository = Depends(get_training_run_repo),
    artifact_repo: SqliteDatasetArtifactRepository = Depends(get_artifact_repo),
    storage: LocalFileStorage = Depends(get_storage),
) -> TrainingOrchestrationService:
    executor: TrainingRunExecutor | None = None

    def dispatch_fn(payload: TrainingRunPayload) -> None:
        assert executor is not None
        executor.run(payload)

    dispatcher = SynchronousRunDispatcher(executor_func=dispatch_fn)
    plugin_registry = ModelPluginRegistrationService(
        model_repo=model_repo,
        file_storage=storage,
    )
    service = TrainingOrchestrationService(
        dispatcher=dispatcher,
        training_run_repo=training_run_repo,
        model_version_repo=model_version_repo,
        model_repo=model_repo,
        dataset_artifact_repo=artifact_repo,
        file_storage=storage,
        plugin_registry=plugin_registry,
    )
    executor = TrainingRunExecutor(
        file_storage=storage,
        notifier=CallbackResultNotifier(callback=service.handle_training_completion),
    )
    return service


def get_inference_service(
	project_repo: SqliteProjectRepository = Depends(get_project_repo),
	dataset_repo: SqliteDatasetRepository = Depends(get_dataset_repo),
	artifact_repo: SqliteDatasetArtifactRepository = Depends(get_artifact_repo),
	model_repo: SqliteModelRepository = Depends(get_model_repo),
	model_version_repo: SqliteModelVersionRepository = Depends(get_model_version_repo),
	training_run_repo: SqliteTrainingRunRepository = Depends(get_training_run_repo),
	detection_job_repo: SqliteDetectionJobRepository = Depends(get_detection_job_repo),
	investigation_repo: SqliteInvestigationCaseRepository = Depends(get_investigation_case_repo),
	rule_manager: RuleManager = Depends(get_rule_manager),
	storage: LocalFileStorage = Depends(get_storage),
) -> InferenceService:
	return InferenceService(
		file_storage=storage,
		detection_job_repo=detection_job_repo,
		project_repo=project_repo,
		dataset_repo=dataset_repo,
		artifact_repo=artifact_repo,
		model_repo=model_repo,
		model_version_repo=model_version_repo,
		training_run_repo=training_run_repo,
		rule_manager=rule_manager,
		investigation_repo=investigation_repo,
	)


__all__ = [
	"setup_infrastructure",
	"teardown_infrastructure",
	"get_storage",
	"get_db",
	"get_project_repo",
	"get_dataset_repo",
	"get_artifact_repo",
	"get_rule_repo",
	"get_rule_version_repo",
	"get_model_repo",
	"get_model_version_repo",
	"get_training_run_repo",
	"get_detection_job_repo",
	"get_investigation_case_repo",
	"get_project_management_service",
	"get_rule_manager",
	"get_rule_executor",
	"get_data_management_service",
	"get_training_service",
	"get_inference_service",
]
