"""add training run compute tracking

Revision ID: f56bffce222f
Revises: 15b917605e94
Create Date: 2026-11-25 15:18:52.192357

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f56bffce222f'
down_revision: Union[str, Sequence[str], None] = '15b917605e94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    from alembic import context

    existing_cols: set[str] = set()
    if not context.is_offline_mode():
        inspector = sa.inspect(op.get_bind())
        if "training_runs" in inspector.get_table_names():
            existing_cols = {c["name"] for c in inspector.get_columns("training_runs")}

    with op.batch_alter_table('training_runs', schema=None) as batch_op:
        if 'external_job_id' not in existing_cols:
            batch_op.add_column(sa.Column('external_job_id', sa.String(length=255), nullable=True))
        if 'compute_metadata' not in existing_cols:
            batch_op.add_column(sa.Column('compute_metadata', sa.JSON(), nullable=True))
        batch_op.create_index(
            batch_op.f('ix_training_runs_external_job_id'),
            ['external_job_id'],
            unique=False,
            if_not_exists=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('training_runs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_training_runs_external_job_id'))
        batch_op.drop_column('compute_metadata')
        batch_op.drop_column('external_job_id')
