"""add lock columns to world_exits

Revision ID: a3f7c1e9d204
Revises: 8a1fbc92d4ee
Create Date: 2026-05-31 22:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a3f7c1e9d204"
down_revision = "8a1fbc92d4ee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("world_exits")}

    if "code_to_unlock" not in existing_columns:
        op.add_column(
            "world_exits",
            sa.Column("code_to_unlock", sa.String(length=50), nullable=True),
        )

    if "item_to_unlock" not in existing_columns:
        op.add_column(
            "world_exits",
            sa.Column("item_to_unlock", sa.String(length=50), nullable=True),
        )

    if "rule_to_unlock" not in existing_columns:
        op.add_column(
            "world_exits",
            sa.Column("rule_to_unlock", sa.String(length=500), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("world_exits")}

    if "rule_to_unlock" in existing_columns:
        op.drop_column("world_exits", "rule_to_unlock")

    if "item_to_unlock" in existing_columns:
        op.drop_column("world_exits", "item_to_unlock")

    if "code_to_unlock" in existing_columns:
        op.drop_column("world_exits", "code_to_unlock")
