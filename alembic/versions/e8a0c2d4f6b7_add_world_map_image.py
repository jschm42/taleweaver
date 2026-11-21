"""add the world map image of an adventure

Revision ID: e8a0c2d4f6b7
Revises: d6f8b0c2e4a5
Create Date: 2026-11-21 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8a0c2d4f6b7"
down_revision: Union[str, Sequence[str], None] = "d6f8b0c2e4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Background image of the world map (engine/world/section_map_image.py); NULL = none.
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.add_column(sa.Column("world_map_image_url", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.drop_column("world_map_image_url")
