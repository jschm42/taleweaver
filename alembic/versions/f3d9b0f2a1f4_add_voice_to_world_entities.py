"""Add voice column to world_entities

Revision ID: f3d9b0f2a1f4
Revises: dab2beb3a37f
Create Date: 2026-05-08 18:25:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3d9b0f2a1f4'
down_revision: Union[str, Sequence[str], None] = '886aaf16818a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('world_entities', schema=None) as batch_op:
        batch_op.add_column(sa.Column('voice', sa.String(length=50), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('world_entities', schema=None) as batch_op:
        batch_op.drop_column('voice')
