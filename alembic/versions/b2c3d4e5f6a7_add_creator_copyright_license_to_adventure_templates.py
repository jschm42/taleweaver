"""add creator copyright license to adventure_templates

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-12 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [column["name"] for column in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _has_column("adventure_templates", "creator"):
        op.add_column(
            "adventure_templates",
            sa.Column("creator", sa.String(length=100), nullable=True),
        )
    if not _has_column("adventure_templates", "copyright"):
        op.add_column(
            "adventure_templates",
            sa.Column("copyright", sa.String(length=100), nullable=True),
        )
    if not _has_column("adventure_templates", "license"):
        op.add_column(
            "adventure_templates",
            sa.Column("license", sa.String(length=100), nullable=True),
        )


def downgrade() -> None:
    if _has_column("adventure_templates", "license"):
        op.drop_column("adventure_templates", "license")
    if _has_column("adventure_templates", "copyright"):
        op.drop_column("adventure_templates", "copyright")
    if _has_column("adventure_templates", "creator"):
        op.drop_column("adventure_templates", "creator")
