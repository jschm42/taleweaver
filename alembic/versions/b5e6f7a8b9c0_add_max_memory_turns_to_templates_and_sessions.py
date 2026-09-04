"""add max_memory_turns to adventure_templates and session_states

Revision ID: b5e6f7a8b9c0
Revises: b4d5e6f7a8b9
Create Date: 2026-09-04 08:40:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5e6f7a8b9c0'
down_revision: Union[str, Sequence[str], None] = 'b4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [column["name"] for column in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _has_column("adventure_templates", "max_memory_turns"):
        op.add_column(
            "adventure_templates",
            sa.Column("max_memory_turns", sa.Integer(), nullable=False, server_default="30"),
        )
    if not _has_column("session_states", "max_memory_turns"):
        op.add_column(
            "session_states",
            sa.Column("max_memory_turns", sa.Integer(), nullable=False, server_default="30"),
        )


def downgrade() -> None:
    if _has_column("adventure_templates", "max_memory_turns"):
        op.drop_column("adventure_templates", "max_memory_turns")
    if _has_column("session_states", "max_memory_turns"):
        op.drop_column("session_states", "max_memory_turns")
