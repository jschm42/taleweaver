"""add allow_dynamic_items setting

Revision ID: b3477fb2839a
Revises: 1259581a66a4
Create Date: 2026-05-05 00:37:10.039584
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision: str = 'b3477fb2839a'
down_revision: Union[str, Sequence[str], None] = '1259581a66a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('adventure_templates', sa.Column('allow_dynamic_items', sa.Boolean(), nullable=False, server_default='1'))
    op.add_column('session_states', sa.Column('allow_dynamic_items', sa.Boolean(), nullable=False, server_default='1'))


def downgrade() -> None:
    op.drop_column('session_states', 'allow_dynamic_items')
    op.drop_column('adventure_templates', 'allow_dynamic_items')
