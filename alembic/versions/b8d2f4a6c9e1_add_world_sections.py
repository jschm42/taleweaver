"""add world sections (adventure regions)

Revision ID: b8d2f4a6c9e1
Revises: a3c7e1f9d2b4
Create Date: 2026-11-20 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8d2f4a6c9e1"
down_revision: Union[str, Sequence[str], None] = "a3c7e1f9d2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # World sections (regions) of an adventure: a JSON list like audio_tracks
    # (engine/world/sections.py). NULL = the adventure has no sections.
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.add_column(sa.Column("world_sections", sa.JSON(), nullable=True))
    # The section a scene belongs to; NULL = no section.
    with op.batch_alter_table("world_scenes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("section_id", sa.String(length=50), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("world_scenes", schema=None) as batch_op:
        batch_op.drop_column("section_id")
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.drop_column("world_sections")
