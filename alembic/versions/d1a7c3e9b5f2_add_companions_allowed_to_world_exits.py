"""add companions_allowed to world_exits

Revision ID: d1a7c3e9b5f2
Revises: c8d2e4f6a1b3
Create Date: 2026-11-12 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1a7c3e9b5f2"
down_revision: Union[str, Sequence[str], None] = "c8d2e4f6a1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A solo passage: the active companion stays behind when the player uses the exit.
    with op.batch_alter_table("world_exits", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "companions_allowed", sa.Boolean(), nullable=False, server_default=sa.text("1")
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("world_exits", schema=None) as batch_op:
        batch_op.drop_column("companions_allowed")
