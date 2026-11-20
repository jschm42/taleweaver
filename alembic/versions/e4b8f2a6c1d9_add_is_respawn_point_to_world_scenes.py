"""add is_respawn_point to world_scenes

Revision ID: e4b8f2a6c1d9
Revises: d1a7c3e9b5f2
Create Date: 2026-11-13 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4b8f2a6c1d9"
down_revision: Union[str, Sequence[str], None] = "d1a7c3e9b5f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Revival point: in respawn mode a fallen protagonist wakes up at the last one reached.
    with op.batch_alter_table("world_scenes", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_respawn_point", sa.Boolean(), nullable=False, server_default=sa.text("0"))
        )


def downgrade() -> None:
    with op.batch_alter_table("world_scenes", schema=None) as batch_op:
        batch_op.drop_column("is_respawn_point")
