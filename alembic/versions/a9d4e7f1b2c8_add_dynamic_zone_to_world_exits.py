"""add dynamic_zone to world_exits

Stores procedural zone expansion metadata on WorldExit rows so template and
session exits can generate new scenes on first traversal.

Revision ID: a9d4e7f1b2c8
Revises: c8d2e4f6a1b3
Create Date: 2026-11-13 08:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9d4e7f1b2c8"
down_revision = "c8d2e4f6a1b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    existing = (
        {c["name"] for c in insp.get_columns("world_exits")}
        if "world_exits" in set(insp.get_table_names())
        else set()
    )
    if "dynamic_zone" not in existing:
        with op.batch_alter_table("world_exits", schema=None) as batch_op:
            batch_op.add_column(sa.Column("dynamic_zone", sa.JSON(), nullable=True))


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    existing = (
        {c["name"] for c in insp.get_columns("world_exits")}
        if "world_exits" in set(insp.get_table_names())
        else set()
    )
    if "dynamic_zone" in existing:
        with op.batch_alter_table("world_exits", schema=None) as batch_op:
            batch_op.drop_column("dynamic_zone")
