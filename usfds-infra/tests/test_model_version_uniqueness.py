"""ModelVersion DB uniqueness and concurrency-safe allocation tests (ISS-010)."""
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from usfds_core.domain.entities.model import Model, ModelVersion, TrainingRun
from usfds_core.domain.entities.system import Project, User
from usfds_core.domain.schemas.training_payload import TrainingRunResult
from usfds_core.services.training.dispatchers.local_dispatcher import SynchronousRunDispatcher
from usfds_core.services.training.training_service import TrainingOrchestrationService
from usfds_core.storage.in_memory_storage import InMemoryFileStorage
from usfds_infra.database import (
	SqliteDatasetArtifactRepository,
	SqliteModelRepository,
	SqliteModelVersionRepository,
	SqliteProjectRepository,
	SqliteTrainingRunRepository,
	SqlUserRepository,
)


def _seed_user(session, user_id):
	SqlUserRepository(session).save(
		User(
			user_id=user_id,
			username=f"u_{user_id.hex[:8]}",
			email=f"{user_id.hex[:8]}@usfds.local",
			full_name="Test User",
			password_hash="h",
		)
	)


def test_model_version_unique_constraint_prevents_duplicates(session_factory):
	"""ISS-010: DB unique constraint (model_id, semver) rejects duplicate versions."""
	model_id = uuid4()
	user_id = uuid4()

	with session_factory() as session:
		_seed_user(session, user_id)
		SqliteModelRepository(session).save(
			Model(model_id=model_id, user_id=user_id, model_name="rf_unique_test")
		)
		SqliteModelVersionRepository(session).save(
			ModelVersion(model_id=model_id, user_id=user_id, semver="v1", artifact_uri="models/v1.joblib")
		)
		session.commit()

	with session_factory() as session:
		with pytest.raises(IntegrityError):
			from usfds_infra.database.models import ModelVersionModel

			session.add(
				ModelVersionModel(
					version_id=str(uuid4()),
					model_id=str(model_id),
					user_id=str(user_id),
					semver="v1",
					artifact_uri="models/v1_dup.joblib",
				)
			)
			session.flush()


def test_concurrent_completion_retries_and_allocates_distinct_versions(session_factory):
	"""ISS-010: Two concurrent completions reading the same latest version retry and get v1, v2."""
	model_id = uuid4()
	user_id = uuid4()
	run1_id = uuid4()
	run2_id = uuid4()

	with session_factory() as session:
		_seed_user(session, user_id)
		SqliteModelRepository(session).save(
			Model(model_id=model_id, user_id=user_id, model_name="rf_concurrent_test")
		)
		run_repo = SqliteTrainingRunRepository(session)
		run_repo.save(TrainingRun(run_id=run1_id, user_id=user_id, model_id=model_id, run_name="run_1"))
		run_repo.save(TrainingRun(run_id=run2_id, user_id=user_id, model_id=model_id, run_name="run_2"))
		session.commit()

	with session_factory() as session1, session_factory() as session2:
		ver_repo1 = SqliteModelVersionRepository(session1)
		ver_repo2 = SqliteModelVersionRepository(session2)

		# Simulate both workers reading latest=None before either saves, then racing on save.
		original_get_latest_2 = ver_repo2.get_latest_version
		calls = {"count": 0}

		def stale_first_read(mid, *args, **kwargs):
			calls["count"] += 1
			if calls["count"] == 1:
				return None
			return original_get_latest_2(mid, *args, **kwargs)

		ver_repo2.get_latest_version = stale_first_read

		service1 = TrainingOrchestrationService(
			dispatcher=SynchronousRunDispatcher(executor_func=lambda p: None),
			training_run_repo=SqliteTrainingRunRepository(session1),
			model_version_repo=ver_repo1,
			model_repo=SqliteModelRepository(session1),
			dataset_artifact_repo=SqliteDatasetArtifactRepository(session1),
			file_storage=InMemoryFileStorage(),
		)
		service2 = TrainingOrchestrationService(
			dispatcher=SynchronousRunDispatcher(executor_func=lambda p: None),
			training_run_repo=SqliteTrainingRunRepository(session2),
			model_version_repo=ver_repo2,
			model_repo=SqliteModelRepository(session2),
			dataset_artifact_repo=SqliteDatasetArtifactRepository(session2),
			file_storage=InMemoryFileStorage(),
		)

		completed1 = service1.handle_training_completion(
			TrainingRunResult(
				run_id=run1_id,
				is_success=True,
				artifact_uri="models/run1.joblib",
				metrics={"accuracy": 0.9},
			)
		)
		session1.commit()

		completed2 = service2.handle_training_completion(
			TrainingRunResult(
				run_id=run2_id,
				is_success=True,
				artifact_uri="models/run2.joblib",
				metrics={"accuracy": 0.91},
			)
		)
		session2.commit()

		with session_factory() as verify_session:
			versions = SqliteModelVersionRepository(verify_session).list_by_model(model_id)
			semvers = sorted(v.semver for v in versions)
			assert semvers == ["v1", "v2"]
			assert completed1.version_id != completed2.version_id


def test_same_model_semver_allowed_across_projects_but_unique_within_project_and_null(session_factory):
	"""ISS-010: (project_id, model_id, semver) allows v1 per project, rejects duplicates within same project or NULL project."""
	from usfds_infra.database.models import ModelVersionModel

	model_id = uuid4()
	user_id = uuid4()
	project_a = uuid4()
	project_b = uuid4()

	with session_factory() as session:
		_seed_user(session, user_id)
		proj_repo = SqliteProjectRepository(session)
		proj_repo.save(Project(project_id=project_a, user_id=user_id, project_name="Proj A"))
		proj_repo.save(Project(project_id=project_b, user_id=user_id, project_name="Proj B"))
		SqliteModelRepository(session).save(
			Model(model_id=model_id, project_id=None, user_id=None, model_name="rf_project_scope")
		)
		repo = SqliteModelVersionRepository(session)
		repo.save(
			ModelVersion(
				model_id=model_id,
				project_id=project_a,
				user_id=user_id,
				semver="v1",
				artifact_uri="models/a_v1.joblib",
			)
		)
		repo.save(
			ModelVersion(
				model_id=model_id,
				project_id=project_b,
				user_id=user_id,
				semver="v1",
				artifact_uri="models/b_v1.joblib",
			)
		)
		repo.save(
			ModelVersion(
				model_id=model_id,
				project_id=None,
				user_id=user_id,
				semver="v1",
				artifact_uri="models/null_v1.joblib",
			)
		)
		session.commit()

	with session_factory() as session:
		with pytest.raises(IntegrityError):
			session.add(
				ModelVersionModel(
					version_id=str(uuid4()),
					model_id=str(model_id),
					project_id=str(project_a),
					user_id=str(user_id),
					semver="v1",
					artifact_uri="models/a_v1_dup.joblib",
				)
			)
			session.flush()
		session.rollback()

		with pytest.raises(IntegrityError):
			session.add(
				ModelVersionModel(
					version_id=str(uuid4()),
					model_id=str(model_id),
					project_id=None,
					user_id=str(user_id),
					semver="v1",
					artifact_uri="models/null_v1_dup.joblib",
				)
			)
			session.flush()
