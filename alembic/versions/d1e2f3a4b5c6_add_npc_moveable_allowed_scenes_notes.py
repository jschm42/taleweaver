"""add moveable, allowed_scenes, and notes to world_entities

Revision ID: d1e2f3a4b5c6
Revises: c6f7a8b9c0d1
Create Date: 2026-09-08 07:40:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, Sequence[str], None] = 'c6f7a8b9c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [column["name"] for column in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _has_column("world_entities", "moveable"):
        op.add_column(
            "world_entities",
            sa.Column("moveable", sa.Boolean(), nullable=False, server_default="0"),
        )
    if not _has_column("world_entities", "allowed_scenes"):
        op.add_column(
            "world_entities",
            sa.Column("allowed_scenes", sa.JSON(), nullable=True),
        )
    if not _has_column("world_entities", "notes"):
        op.add_column(
            "world_entities",
            sa.Column("notes", sa.String(length=1000), nullable=True),
        )


def downgrade() -> None:
    if _has_column("world_entities", "notes"):
        op.drop_column("world_entities", "notes")
    if _has_column("world_entities", "allowed_scenes"):
        op.drop_column("world_entities", "allowed_scenes")
    if _has_column("world_entities", "moveable"):
        op.drop_column("world_entities", "moveable")
