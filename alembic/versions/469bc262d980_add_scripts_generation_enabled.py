"""add_scripts_generation_enabled

Revision ID: 469bc262d980
Revises: d1e2f3a4b5c6
Create Date: 2026-09-22 12:32:28.288922
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '469bc262d980'
down_revision: Union[str, Sequence[str], None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [column["name"] for column in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _has_column("adventure_templates", "scripts_generation_enabled"):
        op.add_column(
            "adventure_templates",
            sa.Column("scripts_generation_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )


def downgrade() -> None:
    if _has_column("adventure_templates", "scripts_generation_enabled"):
        op.drop_column("adventure_templates", "scripts_generation_enabled")
