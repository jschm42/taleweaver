"""add intro_text to adventure_templates

Revision ID: f8a1d72d5f31
Revises: d44a4242b4e9
Create Date: 2026-05-05 19:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f8a1d72d5f31"
down_revision: Union[str, Sequence[str], None] = "d44a4242b4e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {row[1] for row in bind.exec_driver_sql("PRAGMA table_info(adventure_templates)").fetchall()}
    if "intro_text" not in cols:
        with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
            batch_op.add_column(sa.Column("intro_text", sa.String(length=5000), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    cols = {row[1] for row in bind.exec_driver_sql("PRAGMA table_info(adventure_templates)").fetchall()}
    if "intro_text" in cols:
        with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
            batch_op.drop_column("intro_text")
