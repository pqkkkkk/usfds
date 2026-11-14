from typing import Generator
from uuid import UUID
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker
from usfds_core.domain.entities.enums import ExecutionType
from usfds_core.domain.entities.model import Model
from usfds_core.storage.base_storage import IFileStorage

from usfds_infra.database import (
	SqliteModelRepository,
	close_db,
	create_session_factory,
	create_postgres_engine,
	create_sqlite_engine,
	init_db,
)
from usfds_infra.job_queue import BullMQJobQueue
from usfds_infra.storage.local_storage import LocalFileStorage
from usfds_infra.storage.s3_storage import S3FileStorage
from usfds_server.config import settings

# Global singletons managed during application lifecycle
_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_storage: IFileStorage | None = None
_job_queue: BullMQJobQueue | None = None


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


def _build_storage() -> IFileStorage:
    """Create the configured file storage backend ('local' or 's3')."""
    if settings.storage_backend == "s3":
        return S3FileStorage(
            bucket=settings.s3_bucket,
            endpoint_url=settings.s3_endpoint_url,
            public_endpoint_url=settings.s3_public_endpoint_url,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            region=settings.s3_region,
        )
    return LocalFileStorage(base_dir=settings.storage_dir)


def get_job_queue() -> BullMQJobQueue:
    """Producer for the BullMQ queue (requires PostgreSQL via USFDS_DB_URL)."""
    global _job_queue
    if _job_queue is None:
        if not settings.db_url:
            raise RuntimeError("USFDS_DISPATCH_BACKEND=queue requires USFDS_DB_URL (PostgreSQL).")
        _job_queue = BullMQJobQueue(settings.db_url, schema=settings.bullmq_schema)
    return _job_queue


def setup_infrastructure() -> tuple[Engine, IFileStorage]:
    """Initialize database engine, run table schema creation, pre-seed built-in models, and initialize storage."""
    global _engine, _session_factory, _storage

    # 1. Setup database: PostgreSQL when USFDS_DB_URL is set, otherwise SQLite with WAL mode
    if settings.db_url:
        _engine = create_postgres_engine(db_url=settings.db_url, echo=settings.db_echo)
    else:
        _engine = create_sqlite_engine(db_path=settings.db_path, echo=settings.db_echo)
    _session_factory = create_session_factory(_engine)
    init_db(_engine)
    seed_builtin_models(_session_factory)

    # 2. Setup file storage (local filesystem or S3-compatible)
    _storage = _build_storage()

    return _engine, _storage


def teardown_infrastructure() -> None:
    """Close and dispose of database connections and forget every lifecycle singleton.

    Resetting all globals (not only the engine) prevents a restarted app, e.g. a new TestClient,
    from reusing a session factory bound to a disposed engine or storage rooted at a stale directory.
    """
    global _engine, _session_factory, _storage, _job_queue
    if _engine is not None:
        close_db(_engine)
        _engine = None
    _session_factory = None
    _storage = None
    _job_queue = None


def get_storage() -> IFileStorage:
    """FastAPI dependency to retrieve the active file storage instance."""
    global _storage
    if _storage is None:
        _storage = _build_storage()
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


# --- Providers (append-only hot spot) ---------------------------------------------------------------------
# Repository getters: usfds_server/providers/repos.py. Service providers: usfds_server/providers/<domain>.py.
# Imported at the bottom on purpose: providers import get_db / get_storage / get_job_queue from this module.
from usfds_server.providers.repos import (  # noqa: E402
	get_artifact_repo,
	get_case_repo,
	get_dataset_repo,
	get_detection_job_repo,
	get_model_repo,
	get_model_version_repo,
	get_project_repo,
	get_rule_repo,
	get_rule_version_repo,
	get_training_run_repo,
)
from usfds_server.providers.project import get_project_management_service  # noqa: E402
from usfds_server.providers.data import get_data_management_service  # noqa: E402
from usfds_server.providers.rule import get_rule_executor, get_rule_manager  # noqa: E402
from usfds_server.providers.training import get_training_service  # noqa: E402
from usfds_server.providers.detection import get_inference_service  # noqa: E402
from usfds_server.providers.insight import get_insight_report_service  # noqa: E402

__all__ = [
	"setup_infrastructure",
	"teardown_infrastructure",
	"get_storage",
	"get_job_queue",
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
    "get_case_repo",
	"get_project_management_service",
	"get_rule_manager",
	"get_rule_executor",
	"get_data_management_service",
	"get_training_service",
	"get_inference_service",
	"get_insight_report_service",
]
