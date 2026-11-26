"""drop the campaign outline of world sections

The adventure's plot is the only story guide for regions: "Plan regions" and region
generation read it directly, so the stored campaign outline is gone.

Revision ID: a3c5e7f9b1d4
Revises: f1b3d5e7a9c2
Create Date: 2026-11-23 11:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3c5e7f9b1d4"
down_revision: Union[str, Sequence[str], None] = "f1b3d5e7a9c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.drop_column("world_outline")


def downgrade() -> None:
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.add_column(sa.Column("world_outline", sa.JSON(), nullable=True))
