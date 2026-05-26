"""add session_checkpoints table

Revision ID: c2f8a4d9b611
Revises: f69e714a3585
Create Date: 2026-05-26 12:15:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2f8a4d9b611'
down_revision: Union[str, Sequence[str], None] = 'f69e714a3585'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'session_checkpoints',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('message_index', sa.Integer(), nullable=False),
        sa.Column('state_snapshot', sa.JSON(), nullable=False),
        sa.Column('trigger_reason', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['game_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_session_checkpoints')),
    )
    op.create_index(op.f('ix_session_checkpoints_session_id'), 'session_checkpoints', ['session_id'], unique=False)
    op.create_index('ix_session_checkpoints_session_id_created_at', 'session_checkpoints', ['session_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_session_checkpoints_session_id_created_at', table_name='session_checkpoints')
    op.drop_index(op.f('ix_session_checkpoints_session_id'), table_name='session_checkpoints')
    op.drop_table('session_checkpoints')
