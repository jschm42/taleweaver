"""add music_url to world_scenes

Optional background music file per scene (``/data/`` URL or path, e.g. MP3, OGG, WAV).

Revision ID: e8c1d3f5b7a9
Revises: c9e5a1b3d7f4
Create Date: 2026-11-07 12:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8c1d3f5b7a9"
down_revision = "c9e5a1b3d7f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("world_scenes", sa.Column("music_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("world_scenes", "music_url")
