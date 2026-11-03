"""add gm_time_control to adventure_templates

Revision ID: a7c3e9f1b2d4
Revises: f1c4a8d2e6b3
Create Date: 2026-11-01 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c3e9f1b2d4"
down_revision: Union[str, Sequence[str], None] = "f1c4a8d2e6b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Whether the GM may change the in-game time (extra_time_minutes / time overrides).
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("gm_time_control", sa.Boolean(), nullable=False, server_default=sa.text("1"))
        )


def downgrade() -> None:
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.drop_column("gm_time_control")
