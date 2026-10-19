"""add_on_exit_used_triggers_to_world_exits

Revision ID: a2c4e6f8b0d2
Revises: 88de02e25626
Create Date: 2026-10-14 09:07:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2c4e6f8b0d2"
down_revision: Union[str, Sequence[str], None] = "88de02e25626"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    table_names = set(insp.get_table_names())

    if "world_exits" in table_names:
        exit_cols = {c["name"] for c in insp.get_columns("world_exits")}
        with op.batch_alter_table("world_exits", schema=None) as batch_op:
            if "on_exit_used_script" not in exit_cols:
                batch_op.add_column(
                    sa.Column("on_exit_used_script", sa.String(length=5000), nullable=True)
                )
            if "on_exit_used_text" not in exit_cols:
                batch_op.add_column(
                    sa.Column("on_exit_used_text", sa.String(length=5000), nullable=True)
                )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    table_names = set(insp.get_table_names())

    if "world_exits" in table_names:
        exit_cols = {c["name"] for c in insp.get_columns("world_exits")}
        with op.batch_alter_table("world_exits", schema=None) as batch_op:
            if "on_exit_used_text" in exit_cols:
                batch_op.drop_column("on_exit_used_text")
            if "on_exit_used_script" in exit_cols:
                batch_op.drop_column("on_exit_used_script")
