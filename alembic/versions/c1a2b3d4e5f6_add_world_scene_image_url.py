"""Add image_url to world_scenes

Revision ID: c1a2b3d4e5f6
Revises: aaf98fb37ad2
Create Date: 2026-04-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a2b3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'aaf98fb37ad2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def upgrade() -> None:
    conn = op.get_bind()
    # If table doesn't exist, skip — other migrations will create it
    exists = conn.execute(sa.text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='world_scenes'"))
    if exists.fetchone() is None:
        return

    cols = [r[1] for r in conn.execute(sa.text("PRAGMA table_info('world_scenes')")).fetchall()]
    if 'image_url' not in cols:
        with op.batch_alter_table('world_scenes', schema=None) as batch_op:
            batch_op.add_column(sa.Column('image_url', sa.String(length=255), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    cols = [r[1] for r in conn.execute(sa.text("PRAGMA table_info('world_scenes')")).fetchall()]
    if 'image_url' in cols:
        with op.batch_alter_table('world_scenes', schema=None) as batch_op:
            batch_op.drop_column('image_url')
