"""add the campaign outline of world sections

Revision ID: d6f8b0c2e4a5
Revises: c4e6a8b0d2f3
Create Date: 2026-11-21 09:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d6f8b0c2e4a5"
down_revision: Union[str, Sequence[str], None] = "c4e6a8b0d2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Campaign outline that region generation reads (engine/world/section_outline.py).
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.add_column(sa.Column("world_outline", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.drop_column("world_outline")
