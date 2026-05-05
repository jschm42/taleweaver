"""add_is_walkthrough_revealed_to_session_state

Revision ID: 1259581a66a4
Revises: aa67131aff30
Create Date: 2026-05-04 22:11:03.501139
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1259581a66a4'
down_revision: Union[str, Sequence[str], None] = 'aa67131aff30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('session_states', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_walkthrough_revealed', sa.Boolean(), nullable=False, server_default=sa.text('0')))


def downgrade() -> None:
    with op.batch_alter_table('session_states', schema=None) as batch_op:
        batch_op.drop_column('is_walkthrough_revealed')
