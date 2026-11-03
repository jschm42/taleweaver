"""add is_revealed to world_exits

Revision ID: c4e7a1b9d2f6
Revises: b8d4f0a2c3e5
Create Date: 2026-11-01 22:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e7a1b9d2f6"
down_revision: Union[str, Sequence[str], None] = "b8d4f0a2c3e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A revealed exit shows its target scene (name and image) before the player visits it.
    with op.batch_alter_table("world_exits", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_revealed", sa.Boolean(), nullable=False, server_default=sa.text("0"))
        )


def downgrade() -> None:
    with op.batch_alter_table("world_exits", schema=None) as batch_op:
        batch_op.drop_column("is_revealed")
