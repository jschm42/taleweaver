"""add is_raw flag to chat_messages

Revision ID: e5a7c9b1d3f2
Revises: c7e2a4f9d1b3
Create Date: 2026-10-29 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5a7c9b1d3f2"
down_revision: Union[str, Sequence[str], None] = "c7e2a4f9d1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Raw messages (tw.story.narrate_raw) are shown verbatim, without dialogue parsing.
    with op.batch_alter_table("chat_messages", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_raw", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("chat_messages", schema=None) as batch_op:
        batch_op.drop_column("is_raw")
