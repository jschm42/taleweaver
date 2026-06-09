"""add decorative_objects to world_scenes

Revision ID: a1b2c3d4e5f6
Revises: e011bfa7b3fd
Create Date: 2026-06-09 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'e011bfa7b3fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [column["name"] for column in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _has_column("world_scenes", "decorative_objects"):
        op.add_column(
            "world_scenes",
            sa.Column("decorative_objects", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    if _has_column("world_scenes", "decorative_objects"):
        op.drop_column("world_scenes", "decorative_objects")
