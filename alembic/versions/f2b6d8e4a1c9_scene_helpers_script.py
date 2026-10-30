"""add helpers_script to world_scenes

Revision ID: f2b6d8e4a1c9
Revises: e5a7c9b1d3f2
Create Date: 2026-10-30 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2b6d8e4a1c9"
down_revision: Union[str, Sequence[str], None] = "e5a7c9b1d3f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Scene helper functions/constants, loaded into every script run like init_script.
    with op.batch_alter_table("world_scenes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("helpers_script", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("world_scenes", schema=None) as batch_op:
        batch_op.drop_column("helpers_script")
