"""add travel time on exits and fast travel points

Revision ID: c4e6a8b0d2f3
Revises: b8d2f4a6c9e1
Create Date: 2026-11-20 18:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e6a8b0d2f3"
down_revision: Union[str, Sequence[str], None] = "b8d2f4a6c9e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Travel time of a way (docs/specs/world_sections.md, phase 2); NULL = no travel time.
    with op.batch_alter_table("world_exits", schema=None) as batch_op:
        batch_op.add_column(sa.Column("travel_minutes", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("travel_label", sa.String(length=100), nullable=True))
    # Fast travel points and how they are unlocked.
    with op.batch_alter_table("world_scenes", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_fast_travel_point", sa.Boolean(), nullable=False, server_default=sa.text("0")
            )
        )
        batch_op.add_column(
            sa.Column(
                "fast_travel_unlock", sa.String(length=20), nullable=False, server_default="visit"
            )
        )
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "fast_travel_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.drop_column("fast_travel_enabled")
    with op.batch_alter_table("world_scenes", schema=None) as batch_op:
        batch_op.drop_column("fast_travel_unlock")
        batch_op.drop_column("is_fast_travel_point")
    with op.batch_alter_table("world_exits", schema=None) as batch_op:
        batch_op.drop_column("travel_label")
        batch_op.drop_column("travel_minutes")
