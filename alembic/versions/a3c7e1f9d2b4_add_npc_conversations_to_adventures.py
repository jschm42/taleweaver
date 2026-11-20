"""add npc_conversations to adventure_templates

Revision ID: a3c7e1f9d2b4
Revises: cfa8f8fd4b9e
Create Date: 2026-11-19 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3c7e1f9d2b4"
down_revision: Union[str, Sequence[str], None] = "cfa8f8fd4b9e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NPC conversations: chatter level and gossip switch; NULL keeps both off.
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.add_column(sa.Column("npc_conversations", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.drop_column("npc_conversations")
