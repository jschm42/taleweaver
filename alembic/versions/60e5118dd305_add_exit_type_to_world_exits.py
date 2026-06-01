"""add_exit_type_to_world_exits

Revision ID: 60e5118dd305
Revises: a3f7c1e9d204
Create Date: 2026-06-01 10:23:41.424403
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '60e5118dd305'
down_revision: Union[str, Sequence[str], None] = 'a3f7c1e9d204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. Drop indexes if they exist
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("session_checkpoints")}
    with op.batch_alter_table('session_checkpoints', schema=None) as batch_op:
        if 'ix_session_checkpoints_session_id' in existing_indexes:
            batch_op.drop_index(batch_op.f('ix_session_checkpoints_session_id'))
        if 'ix_session_checkpoints_session_id_created_at' in existing_indexes:
            batch_op.drop_index(batch_op.f('ix_session_checkpoints_session_id_created_at'))

    # 2. Add exit_type column to world_exits if it doesn't exist
    existing_columns = {col["name"] for col in inspector.get_columns("world_exits")}
    if "exit_type" not in existing_columns:
        with op.batch_alter_table('world_exits', schema=None) as batch_op:
            batch_op.add_column(sa.Column('exit_type', sa.String(length=20), nullable=False, server_default='one_way'))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. Drop exit_type column if it exists
    existing_columns = {col["name"] for col in inspector.get_columns("world_exits")}
    if "exit_type" in existing_columns:
        with op.batch_alter_table('world_exits', schema=None) as batch_op:
            batch_op.drop_column('exit_type')

    # 2. Re-create indexes if they don't exist
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("session_checkpoints")}
    with op.batch_alter_table('session_checkpoints', schema=None) as batch_op:
        if 'ix_session_checkpoints_session_id_created_at' not in existing_indexes:
            batch_op.create_index(batch_op.f('ix_session_checkpoints_session_id_created_at'), ['session_id', 'created_at'], unique=False)
        if 'ix_session_checkpoints_session_id' not in existing_indexes:
            batch_op.create_index(batch_op.f('ix_session_checkpoints_session_id'), ['session_id'], unique=False)
