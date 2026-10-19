"""add_leave_scene_and_exit_unlock_triggers

Revision ID: 88de02e25626
Revises: 70c211b399de
Create Date: 2026-10-13 20:02:34.192117
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision: str = '88de02e25626'
down_revision: Union[str, Sequence[str], None] = '70c211b399de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    table_names = set(insp.get_table_names())

    if "world_scenes" in table_names:
        scene_cols = {c["name"] for c in insp.get_columns("world_scenes")}
        with op.batch_alter_table("world_scenes", schema=None) as batch_op:
            if "on_leave_scene_script" not in scene_cols:
                batch_op.add_column(
                    sa.Column("on_leave_scene_script", sa.String(length=5000), nullable=True)
                )
            if "on_leave_scene_text" not in scene_cols:
                batch_op.add_column(
                    sa.Column("on_leave_scene_text", sa.String(length=5000), nullable=True)
                )

    if "world_exits" in table_names:
        exit_cols = {c["name"] for c in insp.get_columns("world_exits")}
        with op.batch_alter_table("world_exits", schema=None) as batch_op:
            if "unlock_expression" not in exit_cols:
                batch_op.add_column(
                    sa.Column("unlock_expression", sa.String(length=500), nullable=True)
                )
            if "on_unlock_success_script" not in exit_cols:
                batch_op.add_column(
                    sa.Column("on_unlock_success_script", sa.String(length=5000), nullable=True)
                )
            if "on_unlock_success_text" not in exit_cols:
                batch_op.add_column(
                    sa.Column("on_unlock_success_text", sa.String(length=5000), nullable=True)
                )
            if "on_unlock_failure_script" not in exit_cols:
                batch_op.add_column(
                    sa.Column("on_unlock_failure_script", sa.String(length=5000), nullable=True)
                )
            if "on_unlock_failure_text" not in exit_cols:
                batch_op.add_column(
                    sa.Column("on_unlock_failure_text", sa.String(length=5000), nullable=True)
                )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    table_names = set(insp.get_table_names())

    if "world_scenes" in table_names:
        scene_cols = {c["name"] for c in insp.get_columns("world_scenes")}
        with op.batch_alter_table("world_scenes", schema=None) as batch_op:
            if "on_leave_scene_text" in scene_cols:
                batch_op.drop_column("on_leave_scene_text")
            if "on_leave_scene_script" in scene_cols:
                batch_op.drop_column("on_leave_scene_script")

    if "world_exits" in table_names:
        exit_cols = {c["name"] for c in insp.get_columns("world_exits")}
        with op.batch_alter_table("world_exits", schema=None) as batch_op:
            if "on_unlock_failure_text" in exit_cols:
                batch_op.drop_column("on_unlock_failure_text")
            if "on_unlock_failure_script" in exit_cols:
                batch_op.drop_column("on_unlock_failure_script")
            if "on_unlock_success_text" in exit_cols:
                batch_op.drop_column("on_unlock_success_text")
            if "on_unlock_success_script" in exit_cols:
                batch_op.drop_column("on_unlock_success_script")
            if "unlock_expression" in exit_cols:
                batch_op.drop_column("unlock_expression")
