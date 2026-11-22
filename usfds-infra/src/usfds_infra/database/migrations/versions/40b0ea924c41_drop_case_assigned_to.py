"""drop_case_assigned_to

Revision ID: 40b0ea924c41
Revises: f232fc1f5c13
Create Date: 2026-11-22 15:07:38.561104

"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '40b0ea924c41'
down_revision: Union[str, Sequence[str], None] = 'f232fc1f5c13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
	"""Upgrade schema."""
	offline = context.is_offline_mode()
	should_drop = offline or any(
		c['name'] == 'assigned_to' for c in sa.inspect(op.get_bind()).get_columns('fraud_cases')
	)
	if should_drop:
		with op.batch_alter_table('fraud_cases', schema=None) as batch_op:
			batch_op.drop_column('assigned_to')


def downgrade() -> None:
	"""Downgrade schema."""
	offline = context.is_offline_mode()
	should_add = offline or not any(
		c['name'] == 'assigned_to' for c in sa.inspect(op.get_bind()).get_columns('fraud_cases')
	)
	if should_add:
		with op.batch_alter_table('fraud_cases', schema=None) as batch_op:
			batch_op.add_column(sa.Column('assigned_to', sa.String(length=100), nullable=True))
