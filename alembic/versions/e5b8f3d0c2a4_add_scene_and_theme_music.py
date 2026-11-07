"""add scene and main theme music

Scenes get ``music_prompt`` / ``music_url`` (a rendered loop), adventures a main theme
(``music_prompt`` / ``music_url``) and the author switch ``music_enabled``.

Revision ID: e5b8f3d0c2a4
Revises: d4a7e2c9b1f3
Create Date: 2026-11-07 18:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5b8f3d0c2a4"
down_revision = "d4a7e2c9b1f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("world_scenes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("music_prompt", sa.String(length=1000), nullable=True))
        batch_op.add_column(sa.Column("music_url", sa.String(length=255), nullable=True))
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.add_column(sa.Column("music_prompt", sa.String(length=1000), nullable=True))
        batch_op.add_column(sa.Column("music_url", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column("music_enabled", sa.Boolean(), nullable=False, server_default="1")
        )


def downgrade() -> None:
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.drop_column("music_enabled")
        batch_op.drop_column("music_url")
        batch_op.drop_column("music_prompt")
    with op.batch_alter_table("world_scenes", schema=None) as batch_op:
        batch_op.drop_column("music_url")
        batch_op.drop_column("music_prompt")
