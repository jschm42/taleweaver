"""add unlock_rule to world_entities

Revision ID: e41b8d7c9aa1
Revises: 9c1b7e2d4a11
Create Date: 2026-05-21 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e41b8d7c9aa1"
down_revision = "9c1b7e2d4a11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("world_entities")}

    if "unlock_rule" not in existing_columns:
        op.add_column(
            "world_entities",
            sa.Column("unlock_rule", sa.String(length=500), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("world_entities")}

    if "unlock_rule" in existing_columns:
        op.drop_column("world_entities", "unlock_rule")
