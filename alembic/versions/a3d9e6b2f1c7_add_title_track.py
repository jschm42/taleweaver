"""add the adventure's optional title song

``adventure_templates.title_track_id`` points at a track of ``music_tracks``; it is played while
the adventure's library tile is hovered.

Revision ID: a3d9e6b2f1c7
Revises: f7a1c4e8d2b6
Create Date: 2026-11-08 14:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3d9e6b2f1c7"
down_revision = "f7a1c4e8d2b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.add_column(sa.Column("title_track_id", sa.String(length=50), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.drop_column("title_track_id")
