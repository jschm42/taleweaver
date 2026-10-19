"""add_scene_context_to_chat_messages

Stores the scene and sequence a chat message belongs to, so the client can group the
story into one page per scene/sequence instead of one page per player message.

Revision ID: c7d2e4f6a8b1
Revises: b4e8a1c9d205
Create Date: 2026-10-17 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7d2e4f6a8b1"
down_revision: Union[str, Sequence[str], None] = "b4e8a1c9d205"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_COLUMNS = ("scene_id", "sequence_id")


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "chat_messages" not in set(insp.get_table_names()):
        return
    existing = {c["name"] for c in insp.get_columns("chat_messages")}
    with op.batch_alter_table("chat_messages", schema=None) as batch_op:
        for column_name in _NEW_COLUMNS:
            if column_name not in existing:
                batch_op.add_column(sa.Column(column_name, sa.String(length=100), nullable=True))


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "chat_messages" not in set(insp.get_table_names()):
        return
    existing = {c["name"] for c in insp.get_columns("chat_messages")}
    with op.batch_alter_table("chat_messages", schema=None) as batch_op:
        for column_name in reversed(_NEW_COLUMNS):
            if column_name in existing:
                batch_op.drop_column(column_name)
