"""add max_time_per_turn to adventure_templates

Revision ID: b4d5e6f7a8b9
Revises: a3f1b27d5e89
Create Date: 2026-09-02 14:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'a3f1b27d5e89'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [column["name"] for column in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _has_column("adventure_templates", "max_time_per_turn"):
        op.add_column(
            "adventure_templates",
            sa.Column("max_time_per_turn", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    if _has_column("adventure_templates", "max_time_per_turn"):
        op.drop_column("adventure_templates", "max_time_per_turn")
