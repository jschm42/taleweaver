"""add music generation settings

``server_settings.music_settings`` holds the experimental ComfyUI music workflow and its
limits (see backend/core/music_settings.py).

Revision ID: d4a7e2c9b1f3
Revises: c9e5a1b3d7f4
Create Date: 2026-11-07 12:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4a7e2c9b1f3"
down_revision = "c9e5a1b3d7f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("server_settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("music_settings", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("server_settings", schema=None) as batch_op:
        batch_op.drop_column("music_settings")
