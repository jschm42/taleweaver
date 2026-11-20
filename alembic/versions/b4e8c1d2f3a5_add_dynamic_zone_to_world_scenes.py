"""add dynamic_zone to world_scenes

Stores procedural generation metadata on pre-mapped WorldScene rows so authored
map scenes can be materialized dynamically upon first player entry.

Revision ID: b4e8c1d2f3a5
Revises: a9d4e7f1b2c8
Create Date: 2026-11-14 14:40:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4e8c1d2f3a5"
down_revision = "a9d4e7f1b2c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    existing = (
        {c["name"] for c in insp.get_columns("world_scenes")}
        if "world_scenes" in set(insp.get_table_names())
        else set()
    )
    if "dynamic_zone" not in existing:
        with op.batch_alter_table("world_scenes", schema=None) as batch_op:
            batch_op.add_column(sa.Column("dynamic_zone", sa.JSON(), nullable=True))


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    existing = (
        {c["name"] for c in insp.get_columns("world_scenes")}
        if "world_scenes" in set(insp.get_table_names())
        else set()
    )
    if "dynamic_zone" in existing:
        with op.batch_alter_table("world_scenes", schema=None) as batch_op:
            batch_op.drop_column("dynamic_zone")
