"""make world_maps.template_id nullable

Revision ID: a9d4c1b2e7f0
Revises: 606a7e7cff6c
Create Date: 2026-05-12 15:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a9d4c1b2e7f0"
down_revision: Union[str, Sequence[str], None] = "606a7e7cff6c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("world_maps", schema=None) as batch_op:
        batch_op.alter_column(
            "template_id",
            existing_type=sa.String(length=36),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("world_maps", schema=None) as batch_op:
        batch_op.alter_column(
            "template_id",
            existing_type=sa.String(length=36),
            nullable=False,
        )
