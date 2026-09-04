"""add compressed_history and enable_history_compression to session_states

Revision ID: c6f7a8b9c0d1
Revises: b5e6f7a8b9c0
Create Date: 2026-09-04 11:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c6f7a8b9c0d1'
down_revision: Union[str, Sequence[str], None] = 'b5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [column["name"] for column in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _has_column("session_states", "compressed_history"):
        op.add_column(
            "session_states",
            sa.Column("compressed_history", sa.JSON(), nullable=True),
        )
    if not _has_column("session_states", "enable_history_compression"):
        op.add_column(
            "session_states",
            sa.Column("enable_history_compression", sa.Boolean(), nullable=False, server_default="1"),
        )


def downgrade() -> None:
    if _has_column("session_states", "compressed_history"):
        op.drop_column("session_states", "compressed_history")
    if _has_column("session_states", "enable_history_compression"):
        op.drop_column("session_states", "enable_history_compression")
