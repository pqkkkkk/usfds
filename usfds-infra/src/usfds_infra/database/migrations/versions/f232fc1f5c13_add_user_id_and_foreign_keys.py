"""add user_id and foreign keys

Revision ID: f232fc1f5c13
Revises: 845d529c5502
Create Date: 2026-11-22 10:25:49.196976

"""
from typing import Dict, Sequence, Set, Union

from alembic import context, op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f232fc1f5c13'
down_revision: Union[str, Sequence[str], None] = '845d529c5502'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_USER_ID_TABLES = ('detection_jobs', 'model_versions', 'rules', 'training_runs')
_PROJECT_SCOPED_TABLES = ('datasets', 'detection_jobs', 'model_versions', 'models', 'rules', 'training_runs')


def upgrade() -> None:
	"""Upgrade schema."""
	offline = context.is_offline_mode()
	existing_cols: Dict[str, Set[str]] = {}
	existing_idxs: Dict[str, Set[str]] = {}
	existing_fks: Dict[str, Set[str]] = {}

	if not offline:
		inspector = sa.inspect(op.get_bind())
		for tbl in ('projects', *_PROJECT_SCOPED_TABLES):
			existing_cols[tbl] = {c['name'] for c in inspector.get_columns(tbl)}
			existing_idxs[tbl] = {i['name'] for i in inspector.get_indexes(tbl) if i.get('name')}
			existing_fks[tbl] = {fk['name'] for fk in inspector.get_foreign_keys(tbl) if fk.get('name')}

	# 1. Add user_id as nullable first on the 4 tables that did not have it, and make models.user_id nullable
	for tbl in _NEW_USER_ID_TABLES:
		if offline or 'user_id' not in existing_cols.get(tbl, set()):
			op.add_column(tbl, sa.Column('user_id', sa.String(length=36), nullable=True))

	with op.batch_alter_table('models', schema=None) as batch_op:
		batch_op.alter_column('user_id', existing_type=sa.String(length=36), nullable=True)

	# 2. Data cleanup & backfill (portable ANSI SQL for SQLite and PostgreSQL)
	op.execute(
		sa.text(
			"INSERT INTO users (user_id, username, email, full_name, password_hash, status, created_at, updated_at) "
			"SELECT DISTINCT p.user_id, 'legacy_' || p.user_id, NULL, 'Legacy Owner', '', 'DISABLED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP "
			"FROM projects p "
			"WHERE p.user_id IS NOT NULL "
			"AND NOT EXISTS (SELECT 1 FROM users u WHERE u.user_id = p.user_id)"
		)
	)
	op.execute(
		sa.text(
			"INSERT INTO users (user_id, username, email, full_name, password_hash, status, created_at, updated_at) "
			"SELECT DISTINCT d.user_id, 'legacy_' || d.user_id, NULL, 'Legacy Owner', '', 'DISABLED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP "
			"FROM datasets d "
			"WHERE d.user_id IS NOT NULL "
			"AND NOT EXISTS (SELECT 1 FROM users u WHERE u.user_id = d.user_id)"
		)
	)
	op.execute(
		sa.text(
			"UPDATE models SET user_id = NULL "
			"WHERE project_id IS NULL "
			"OR NOT EXISTS (SELECT 1 FROM users u WHERE u.user_id = models.user_id)"
		)
	)
	for tbl in _PROJECT_SCOPED_TABLES:
		op.execute(
			sa.text(
				f"DELETE FROM {tbl} "
				f"WHERE project_id IS NOT NULL "
				f"AND NOT EXISTS (SELECT 1 FROM projects p WHERE p.project_id = {tbl}.project_id)"
			)
		)

	for tbl in ('rules', 'detection_jobs', 'training_runs'):
		op.execute(
			sa.text(
				f"UPDATE {tbl} "
				f"SET user_id = COALESCE("
				f"(SELECT u.user_id FROM users u WHERE u.username = {tbl}.created_by LIMIT 1), "
				f"(SELECT p.user_id FROM projects p WHERE p.project_id = {tbl}.project_id LIMIT 1), "
				f"(SELECT u.user_id FROM users u ORDER BY u.created_at ASC LIMIT 1)"
				f") "
				f"WHERE user_id IS NULL"
			)
		)

	op.execute(
		sa.text(
			"UPDATE model_versions "
			"SET user_id = COALESCE("
			"(SELECT tr.user_id FROM training_runs tr WHERE tr.run_id = model_versions.run_id LIMIT 1), "
			"(SELECT u.user_id FROM users u WHERE u.username = model_versions.registered_by LIMIT 1), "
			"(SELECT p.user_id FROM projects p WHERE p.project_id = model_versions.project_id LIMIT 1), "
			"(SELECT u.user_id FROM users u ORDER BY u.created_at ASC LIMIT 1)"
			") "
			"WHERE user_id IS NULL"
		)
	)

	for tbl in _NEW_USER_ID_TABLES:
		op.execute(sa.text(f"DELETE FROM {tbl} WHERE user_id IS NULL"))

	# 3. Apply NOT NULL constraints, indexes, and named foreign keys via batch_alter_table
	with op.batch_alter_table('projects', schema=None) as batch_op:
		if offline or 'fk_projects_user_id_users' not in existing_fks.get('projects', set()):
			batch_op.create_foreign_key(
				'fk_projects_user_id_users', 'users', ['user_id'], ['user_id'], ondelete='RESTRICT'
			)

	with op.batch_alter_table('datasets', schema=None) as batch_op:
		if offline or 'ix_datasets_user_id' not in existing_idxs.get('datasets', set()):
			batch_op.create_index(batch_op.f('ix_datasets_user_id'), ['user_id'], unique=False)
		if offline or 'fk_datasets_project_id_projects' not in existing_fks.get('datasets', set()):
			batch_op.create_foreign_key(
				'fk_datasets_project_id_projects', 'projects', ['project_id'], ['project_id'], ondelete='CASCADE'
			)
		if offline or 'fk_datasets_user_id_users' not in existing_fks.get('datasets', set()):
			batch_op.create_foreign_key(
				'fk_datasets_user_id_users', 'users', ['user_id'], ['user_id'], ondelete='RESTRICT'
			)

	with op.batch_alter_table('models', schema=None) as batch_op:
		if offline or 'fk_models_user_id_users' not in existing_fks.get('models', set()):
			batch_op.create_foreign_key(
				'fk_models_user_id_users', 'users', ['user_id'], ['user_id'], ondelete='RESTRICT'
			)
		if offline or 'fk_models_project_id_projects' not in existing_fks.get('models', set()):
			batch_op.create_foreign_key(
				'fk_models_project_id_projects', 'projects', ['project_id'], ['project_id'], ondelete='CASCADE'
			)

	with op.batch_alter_table('model_versions', schema=None) as batch_op:
		batch_op.alter_column('user_id', existing_type=sa.String(length=36), nullable=False)
		if offline or 'ix_model_versions_user_id' not in existing_idxs.get('model_versions', set()):
			batch_op.create_index(batch_op.f('ix_model_versions_user_id'), ['user_id'], unique=False)
		if offline or 'fk_model_versions_user_id_users' not in existing_fks.get('model_versions', set()):
			batch_op.create_foreign_key(
				'fk_model_versions_user_id_users', 'users', ['user_id'], ['user_id'], ondelete='RESTRICT'
			)
		if offline or 'fk_model_versions_project_id_projects' not in existing_fks.get('model_versions', set()):
			batch_op.create_foreign_key(
				'fk_model_versions_project_id_projects', 'projects', ['project_id'], ['project_id'], ondelete='CASCADE'
			)

	with op.batch_alter_table('training_runs', schema=None) as batch_op:
		batch_op.alter_column('user_id', existing_type=sa.String(length=36), nullable=False)
		if offline or 'ix_training_runs_user_id' not in existing_idxs.get('training_runs', set()):
			batch_op.create_index(batch_op.f('ix_training_runs_user_id'), ['user_id'], unique=False)
		if offline or 'fk_training_runs_project_id_projects' not in existing_fks.get('training_runs', set()):
			batch_op.create_foreign_key(
				'fk_training_runs_project_id_projects', 'projects', ['project_id'], ['project_id'], ondelete='CASCADE'
			)
		if offline or 'fk_training_runs_user_id_users' not in existing_fks.get('training_runs', set()):
			batch_op.create_foreign_key(
				'fk_training_runs_user_id_users', 'users', ['user_id'], ['user_id'], ondelete='RESTRICT'
			)

	with op.batch_alter_table('rules', schema=None) as batch_op:
		batch_op.alter_column('user_id', existing_type=sa.String(length=36), nullable=False)
		if offline or 'ix_rules_user_id' not in existing_idxs.get('rules', set()):
			batch_op.create_index(batch_op.f('ix_rules_user_id'), ['user_id'], unique=False)
		if offline or 'fk_rules_user_id_users' not in existing_fks.get('rules', set()):
			batch_op.create_foreign_key(
				'fk_rules_user_id_users', 'users', ['user_id'], ['user_id'], ondelete='RESTRICT'
			)
		if offline or 'fk_rules_project_id_projects' not in existing_fks.get('rules', set()):
			batch_op.create_foreign_key(
				'fk_rules_project_id_projects', 'projects', ['project_id'], ['project_id'], ondelete='CASCADE'
			)

	with op.batch_alter_table('detection_jobs', schema=None) as batch_op:
		batch_op.alter_column('user_id', existing_type=sa.String(length=36), nullable=False)
		if offline or 'ix_detection_jobs_user_id' not in existing_idxs.get('detection_jobs', set()):
			batch_op.create_index(batch_op.f('ix_detection_jobs_user_id'), ['user_id'], unique=False)
		if offline or 'fk_detection_jobs_user_id_users' not in existing_fks.get('detection_jobs', set()):
			batch_op.create_foreign_key(
				'fk_detection_jobs_user_id_users', 'users', ['user_id'], ['user_id'], ondelete='RESTRICT'
			)
		if offline or 'fk_detection_jobs_project_id_projects' not in existing_fks.get('detection_jobs', set()):
			batch_op.create_foreign_key(
				'fk_detection_jobs_project_id_projects', 'projects', ['project_id'], ['project_id'], ondelete='CASCADE'
			)


def downgrade() -> None:
	"""Downgrade schema."""
	with op.batch_alter_table('detection_jobs', schema=None) as batch_op:
		batch_op.drop_constraint('fk_detection_jobs_project_id_projects', type_='foreignkey')
		batch_op.drop_constraint('fk_detection_jobs_user_id_users', type_='foreignkey')
		batch_op.drop_index(batch_op.f('ix_detection_jobs_user_id'))
		batch_op.drop_column('user_id')

	with op.batch_alter_table('rules', schema=None) as batch_op:
		batch_op.drop_constraint('fk_rules_project_id_projects', type_='foreignkey')
		batch_op.drop_constraint('fk_rules_user_id_users', type_='foreignkey')
		batch_op.drop_index(batch_op.f('ix_rules_user_id'))
		batch_op.drop_column('user_id')

	with op.batch_alter_table('training_runs', schema=None) as batch_op:
		batch_op.drop_constraint('fk_training_runs_user_id_users', type_='foreignkey')
		batch_op.drop_constraint('fk_training_runs_project_id_projects', type_='foreignkey')
		batch_op.drop_index(batch_op.f('ix_training_runs_user_id'))
		batch_op.drop_column('user_id')

	with op.batch_alter_table('model_versions', schema=None) as batch_op:
		batch_op.drop_constraint('fk_model_versions_project_id_projects', type_='foreignkey')
		batch_op.drop_constraint('fk_model_versions_user_id_users', type_='foreignkey')
		batch_op.drop_index(batch_op.f('ix_model_versions_user_id'))
		batch_op.drop_column('user_id')

	with op.batch_alter_table('models', schema=None) as batch_op:
		batch_op.drop_constraint('fk_models_project_id_projects', type_='foreignkey')
		batch_op.drop_constraint('fk_models_user_id_users', type_='foreignkey')
		batch_op.alter_column('user_id', existing_type=sa.String(length=36), nullable=False)

	with op.batch_alter_table('datasets', schema=None) as batch_op:
		batch_op.drop_constraint('fk_datasets_user_id_users', type_='foreignkey')
		batch_op.drop_constraint('fk_datasets_project_id_projects', type_='foreignkey')
		batch_op.drop_index(batch_op.f('ix_datasets_user_id'))

	with op.batch_alter_table('projects', schema=None) as batch_op:
		batch_op.drop_constraint('fk_projects_user_id_users', type_='foreignkey')
