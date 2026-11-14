"""baseline schema (schema as of commit 323eb43, 26-11-14)

Revision ID: 0001_baseline
Revises: 
Create Date: 2026-11-14 10:10:03.158186

"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_baseline'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Idempotent baseline: databases created before Alembic (by `Base.metadata.create_all`) keep their
    # existing tables and data; only missing tables are created. Fresh databases get everything.
    # Offline (--sql) mode has no live connection to inspect: render the full schema.
    existing_tables = set() if context.is_offline_mode() else set(sa.inspect(op.get_bind()).get_table_names())

    if 'audit_logs' not in existing_tables:
        op.create_table('audit_logs',
        sa.Column('log_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=True),
        sa.Column('entity_type', sa.String(length=40), nullable=False),
        sa.Column('entity_id', sa.String(length=255), nullable=False),
        sa.Column('action', sa.String(length=40), nullable=False),
        sa.Column('actor', sa.String(length=100), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('log_id')
        )
        with op.batch_alter_table('audit_logs', schema=None) as batch_op:
            batch_op.create_index('idx_audit_entity', ['project_id', 'entity_type', 'entity_id', 'created_at'], unique=False)
            batch_op.create_index('idx_audit_project', ['project_id', 'created_at'], unique=False)

    if 'datasets' not in existing_tables:
        op.create_table('datasets',
        sa.Column('dataset_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('dataset_name', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('contains_pii', sa.Boolean(), nullable=False),
        sa.Column('data_classification', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('dataset_id'),
        sa.UniqueConstraint('project_id', 'dataset_name', name='uq_project_dataset_name')
        )
        with op.batch_alter_table('datasets', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_datasets_project_id'), ['project_id'], unique=False)

    if 'detection_jobs' not in existing_tables:
        op.create_table('detection_jobs',
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('deployment_id', sa.String(length=36), nullable=True),
        sa.Column('target_artifact_id', sa.String(length=36), nullable=True),
        sa.Column('model_version_id', sa.String(length=36), nullable=True),
        sa.Column('job_name', sa.String(length=255), nullable=True),
        sa.Column('input_path', sa.String(length=500), nullable=False),
        sa.Column('output_path', sa.String(length=500), nullable=True),
        sa.Column('score_threshold', sa.Float(), nullable=False),
        sa.Column('use_rules', sa.Boolean(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('total_records', sa.Integer(), nullable=True),
        sa.Column('fraud_records', sa.Integer(), nullable=True),
        sa.Column('fraud_rate', sa.Float(), nullable=True),
        sa.Column('summary_metrics', sa.JSON(), nullable=True),
        sa.Column('execution_time_seconds', sa.Float(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('job_id')
        )
        with op.batch_alter_table('detection_jobs', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_detection_jobs_deployment_id'), ['deployment_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_detection_jobs_model_version_id'), ['model_version_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_detection_jobs_project_id'), ['project_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_detection_jobs_status'), ['status'], unique=False)
            batch_op.create_index(batch_op.f('ix_detection_jobs_target_artifact_id'), ['target_artifact_id'], unique=False)

    if 'fraud_cases' not in existing_tables:
        op.create_table('fraud_cases',
        sa.Column('case_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('case_code', sa.String(length=64), nullable=False),
        sa.Column('event_id', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('tx_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('final_action', sa.String(length=20), nullable=False),
        sa.Column('dataset_artifact_id', sa.String(length=36), nullable=True),
        sa.Column('detection_job_id', sa.String(length=36), nullable=True),
        sa.Column('model_version_id', sa.String(length=36), nullable=True),
        sa.Column('model_score', sa.Float(), nullable=True),
        sa.Column('triggered_rules', sa.JSON(), nullable=False),
        sa.Column('triggered_rule_codes', sa.JSON(), nullable=False),
        sa.Column('feature_contributions', sa.JSON(), nullable=False),
        sa.Column('attributes', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('priority', sa.String(length=20), nullable=False),
        sa.Column('priority_score', sa.Float(), nullable=False),
        sa.Column('assigned_to', sa.String(length=100), nullable=True),
        sa.Column('resolution_reason', sa.String(length=50), nullable=True),
        sa.Column('resolution_summary', sa.Text(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', sa.String(length=100), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("final_action IN ('REVIEW', 'REJECT')"),
        sa.CheckConstraint("status IN ('OPEN','IN_PROGRESS','PENDING_CUSTOMER','RESOLVED_FRAUD','RESOLVED_LEGITIMATE')"),
        sa.CheckConstraint('amount >= 0'),
        sa.CheckConstraint('model_score IS NULL OR (model_score >= 0 AND model_score <= 1)'),
        sa.PrimaryKeyConstraint('case_id'),
        sa.UniqueConstraint('project_id', 'case_code', name='uq_case_project_code'),
        sa.UniqueConstraint('project_id', 'event_id', name='uq_case_project_event')
        )
        with op.batch_alter_table('fraud_cases', schema=None) as batch_op:
            batch_op.create_index('idx_case_queue', ['project_id', 'status', 'priority_score'], unique=False)
            batch_op.create_index('idx_case_user', ['project_id', 'user_id'], unique=False)

    if 'models' not in existing_tables:
        op.create_table('models',
        sa.Column('model_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=True),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('execution_type', sa.String(length=50), nullable=False),
        sa.Column('entrypoint_uri', sa.String(length=500), nullable=True),
        sa.Column('hyperparameter_schema', sa.JSON(), nullable=True),
        sa.Column('default_hyperparameters', sa.JSON(), nullable=True),
        sa.Column('risk_level', sa.String(length=50), nullable=True),
        sa.Column('github_repo', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('model_id')
        )
        with op.batch_alter_table('models', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_models_model_name'), ['model_name'], unique=False)
            batch_op.create_index(batch_op.f('ix_models_project_id'), ['project_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_models_user_id'), ['user_id'], unique=False)

    if 'projects' not in existing_tables:
        op.create_table('projects',
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('project_name', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('base_dataset_id', sa.String(length=36), nullable=True),
        sa.Column('raw_schema', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('project_id'),
        sa.UniqueConstraint('user_id', 'project_name', name='uq_user_project_name')
        )
        with op.batch_alter_table('projects', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_projects_status'), ['status'], unique=False)
            batch_op.create_index(batch_op.f('ix_projects_user_id'), ['user_id'], unique=False)

    if 'rules' not in existing_tables:
        op.create_table('rules',
        sa.Column('rule_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('rule_code', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('current_version_id', sa.String(length=36), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('rule_id'),
        sa.UniqueConstraint('project_id', 'rule_code', name='uq_project_rule_code')
        )
        with op.batch_alter_table('rules', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_rules_project_id'), ['project_id'], unique=False)

    if 'dataset_artifacts' not in existing_tables:
        op.create_table('dataset_artifacts',
        sa.Column('artifact_id', sa.String(length=36), nullable=False),
        sa.Column('dataset_id', sa.String(length=36), nullable=False),
        sa.Column('parent_artifact_id', sa.String(length=36), nullable=True),
        sa.Column('pipeline_stage', sa.String(length=50), nullable=False),
        sa.Column('change_type', sa.String(length=100), nullable=True),
        sa.Column('storage_path', sa.String(length=500), nullable=False),
        sa.Column('output_paths', sa.JSON(), nullable=False),
        sa.Column('checksum_sha256', sa.String(length=64), nullable=True),
        sa.Column('schema_snapshot', sa.JSON(), nullable=True),
        sa.Column('row_count', sa.Integer(), nullable=True),
        sa.Column('column_count', sa.Integer(), nullable=True),
        sa.Column('validation_status', sa.String(length=50), nullable=True),
        sa.Column('validation_report', sa.JSON(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['dataset_id'], ['datasets.dataset_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_artifact_id'], ['dataset_artifacts.artifact_id'], ),
        sa.PrimaryKeyConstraint('artifact_id')
        )
        with op.batch_alter_table('dataset_artifacts', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_dataset_artifacts_dataset_id'), ['dataset_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_dataset_artifacts_parent_artifact_id'), ['parent_artifact_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_dataset_artifacts_pipeline_stage'), ['pipeline_stage'], unique=False)

    if 'entity_blacklist' not in existing_tables:
        op.create_table('entity_blacklist',
        sa.Column('blacklist_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('entity_type', sa.String(length=30), nullable=False),
        sa.Column('entity_value', sa.String(length=255), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('source_case_id', sa.String(length=36), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('removed_by', sa.String(length=100), nullable=True),
        sa.Column('removed_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('ACTIVE','REMOVED')"),
        sa.ForeignKeyConstraint(['source_case_id'], ['fraud_cases.case_id'], ),
        sa.PrimaryKeyConstraint('blacklist_id')
        )
        with op.batch_alter_table('entity_blacklist', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_entity_blacklist_project_id'), ['project_id'], unique=False)
            batch_op.create_index('uq_active_blacklist', ['project_id', 'entity_type', 'entity_value'], unique=True, sqlite_where=sa.text("status = 'ACTIVE'"), postgresql_where=sa.text("status = 'ACTIVE'"))

    if 'model_versions' not in existing_tables:
        op.create_table('model_versions',
        sa.Column('version_id', sa.String(length=36), nullable=False),
        sa.Column('model_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=True),
        sa.Column('run_id', sa.String(length=36), nullable=True),
        sa.Column('semver', sa.String(length=50), nullable=False),
        sa.Column('artifact_uri', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('artifact_size_mb', sa.Float(), nullable=True),
        sa.Column('checksum_sha256', sa.String(length=64), nullable=True),
        sa.Column('framework', sa.String(length=100), nullable=True),
        sa.Column('decision_threshold', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('registered_by', sa.String(length=100), nullable=True),
        sa.Column('registered_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['model_id'], ['models.model_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('version_id')
        )
        with op.batch_alter_table('model_versions', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_model_versions_model_id'), ['model_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_model_versions_project_id'), ['project_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_model_versions_run_id'), ['run_id'], unique=False)

    if 'rule_versions' not in existing_tables:
        op.create_table('rule_versions',
        sa.Column('rule_version_id', sa.String(length=36), nullable=False),
        sa.Column('rule_id', sa.String(length=36), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('condition', sa.JSON(), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['rule_id'], ['rules.rule_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('rule_version_id'),
        sa.UniqueConstraint('rule_id', 'version_number', name='uq_rule_version_number')
        )
        with op.batch_alter_table('rule_versions', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_rule_versions_rule_id'), ['rule_id'], unique=False)

    if 'training_runs' not in existing_tables:
        op.create_table('training_runs',
        sa.Column('run_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=True),
        sa.Column('model_id', sa.String(length=36), nullable=True),
        sa.Column('version_id', sa.String(length=36), nullable=True),
        sa.Column('run_name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('accuracy', sa.Float(), nullable=True),
        sa.Column('precision_score', sa.Float(), nullable=True),
        sa.Column('recall_score', sa.Float(), nullable=True),
        sa.Column('f1_score', sa.Float(), nullable=True),
        sa.Column('loss', sa.Float(), nullable=True),
        sa.Column('default_threshold', sa.Float(), nullable=False),
        sa.Column('recommended_threshold', sa.Float(), nullable=True),
        sa.Column('hyperparameters', sa.JSON(), nullable=True),
        sa.Column('custom_metrics', sa.JSON(), nullable=True),
        sa.Column('compute_target', sa.String(length=100), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('logs_path', sa.String(length=500), nullable=True),
        sa.Column('metrics_path', sa.String(length=500), nullable=True),
        sa.Column('eval_predictions_path', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['model_id'], ['models.model_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('run_id')
        )
        with op.batch_alter_table('training_runs', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_training_runs_model_id'), ['model_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_training_runs_project_id'), ['project_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_training_runs_status'), ['status'], unique=False)
            batch_op.create_index(batch_op.f('ix_training_runs_version_id'), ['version_id'], unique=False)

    if 'run_datasets' not in existing_tables:
        op.create_table('run_datasets',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.String(length=36), nullable=False),
        sa.Column('dataset_artifact_id', sa.String(length=36), nullable=False),
        sa.Column('dataset_role', sa.String(length=50), nullable=False),
        sa.Column('sample_count', sa.Integer(), nullable=True),
        sa.Column('usage_percentage', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['training_runs.run_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('run_datasets', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_run_datasets_dataset_artifact_id'), ['dataset_artifact_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_run_datasets_run_id'), ['run_id'], unique=False)

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('run_datasets', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_run_datasets_run_id'))
        batch_op.drop_index(batch_op.f('ix_run_datasets_dataset_artifact_id'))

    op.drop_table('run_datasets')
    with op.batch_alter_table('training_runs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_training_runs_version_id'))
        batch_op.drop_index(batch_op.f('ix_training_runs_status'))
        batch_op.drop_index(batch_op.f('ix_training_runs_project_id'))
        batch_op.drop_index(batch_op.f('ix_training_runs_model_id'))

    op.drop_table('training_runs')
    with op.batch_alter_table('rule_versions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_rule_versions_rule_id'))

    op.drop_table('rule_versions')
    with op.batch_alter_table('model_versions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_model_versions_run_id'))
        batch_op.drop_index(batch_op.f('ix_model_versions_project_id'))
        batch_op.drop_index(batch_op.f('ix_model_versions_model_id'))

    op.drop_table('model_versions')
    with op.batch_alter_table('entity_blacklist', schema=None) as batch_op:
        batch_op.drop_index('uq_active_blacklist', sqlite_where=sa.text("status = 'ACTIVE'"), postgresql_where=sa.text("status = 'ACTIVE'"))
        batch_op.drop_index(batch_op.f('ix_entity_blacklist_project_id'))

    op.drop_table('entity_blacklist')
    with op.batch_alter_table('dataset_artifacts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_dataset_artifacts_pipeline_stage'))
        batch_op.drop_index(batch_op.f('ix_dataset_artifacts_parent_artifact_id'))
        batch_op.drop_index(batch_op.f('ix_dataset_artifacts_dataset_id'))

    op.drop_table('dataset_artifacts')
    with op.batch_alter_table('rules', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_rules_project_id'))

    op.drop_table('rules')
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_projects_user_id'))
        batch_op.drop_index(batch_op.f('ix_projects_status'))

    op.drop_table('projects')
    with op.batch_alter_table('models', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_models_user_id'))
        batch_op.drop_index(batch_op.f('ix_models_project_id'))
        batch_op.drop_index(batch_op.f('ix_models_model_name'))

    op.drop_table('models')
    with op.batch_alter_table('fraud_cases', schema=None) as batch_op:
        batch_op.drop_index('idx_case_user')
        batch_op.drop_index('idx_case_queue')

    op.drop_table('fraud_cases')
    with op.batch_alter_table('detection_jobs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_detection_jobs_target_artifact_id'))
        batch_op.drop_index(batch_op.f('ix_detection_jobs_status'))
        batch_op.drop_index(batch_op.f('ix_detection_jobs_project_id'))
        batch_op.drop_index(batch_op.f('ix_detection_jobs_model_version_id'))
        batch_op.drop_index(batch_op.f('ix_detection_jobs_deployment_id'))

    op.drop_table('detection_jobs')
    with op.batch_alter_table('datasets', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_datasets_project_id'))

    op.drop_table('datasets')
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.drop_index('idx_audit_project')
        batch_op.drop_index('idx_audit_entity')

    op.drop_table('audit_logs')
    # ### end Alembic commands ###
