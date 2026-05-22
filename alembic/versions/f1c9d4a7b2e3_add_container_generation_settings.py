"""add container generation settings

Revision ID: f1c9d4a7b2e3
Revises: e41b8d7c9aa1
Create Date: 2026-05-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f1c9d4a7b2e3"
down_revision = "e41b8d7c9aa1"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [column["name"] for column in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _has_column("adventure_templates", "container_generation_enabled"):
        op.add_column(
            "adventure_templates",
            sa.Column("container_generation_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        )

    if not _has_column("adventure_templates", "max_containers"):
        op.add_column(
            "adventure_templates",
            sa.Column("max_containers", sa.Integer(), nullable=False, server_default="8"),
        )

    op.execute("UPDATE adventure_templates SET max_containers = 8 WHERE max_containers IS NULL")


def downgrade() -> None:
    if _has_column("adventure_templates", "max_containers"):
        op.drop_column("adventure_templates", "max_containers")

    if _has_column("adventure_templates", "container_generation_enabled"):
        op.drop_column("adventure_templates", "container_generation_enabled")
