"""add_win_loss_guard_expressions

Revision ID: b4e8a1c9d205
Revises: a2c4e6f8b0d2
Create Date: 2026-10-14 12:40:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4e8a1c9d205"
down_revision: Union[str, Sequence[str], None] = "a2c4e6f8b0d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    table_names = set(insp.get_table_names())

    if "adventure_templates" in table_names:
        adv_cols = {c["name"] for c in insp.get_columns("adventure_templates")}
        with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
            if "completed_guard_expression" not in adv_cols:
                batch_op.add_column(
                    sa.Column("completed_guard_expression", sa.String(length=2000), nullable=True)
                )
            if "gameover_guard_expression" not in adv_cols:
                batch_op.add_column(
                    sa.Column("gameover_guard_expression", sa.String(length=2000), nullable=True)
                )

    if "session_states" in table_names:
        state_cols = {c["name"] for c in insp.get_columns("session_states")}
        with op.batch_alter_table("session_states", schema=None) as batch_op:
            if "completed_guard_expression" not in state_cols:
                batch_op.add_column(
                    sa.Column("completed_guard_expression", sa.String(length=2000), nullable=True)
                )
            if "gameover_guard_expression" not in state_cols:
                batch_op.add_column(
                    sa.Column("gameover_guard_expression", sa.String(length=2000), nullable=True)
                )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    table_names = set(insp.get_table_names())

    if "adventure_templates" in table_names:
        adv_cols = {c["name"] for c in insp.get_columns("adventure_templates")}
        with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
            if "gameover_guard_expression" in adv_cols:
                batch_op.drop_column("gameover_guard_expression")
            if "completed_guard_expression" in adv_cols:
                batch_op.drop_column("completed_guard_expression")

    if "session_states" in table_names:
        state_cols = {c["name"] for c in insp.get_columns("session_states")}
        with op.batch_alter_table("session_states", schema=None) as batch_op:
            if "gameover_guard_expression" in state_cols:
                batch_op.drop_column("gameover_guard_expression")
            if "completed_guard_expression" in state_cols:
                batch_op.drop_column("completed_guard_expression")
