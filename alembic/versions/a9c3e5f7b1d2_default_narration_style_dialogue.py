"""default narration_style to dialogue for new sessions

Revision ID: a9c3e5f7b1d2
Revises: f2b6d8a4c1e9
Create Date: 2026-10-26 18:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9c3e5f7b1d2"
down_revision: Union[str, Sequence[str], None] = "f2b6d8a4c1e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _set_server_default(value: str) -> None:
    # Existing sessions keep their stored style; only new rows get the new default.
    with op.batch_alter_table("session_states", schema=None) as batch_op:
        batch_op.alter_column(
            "narration_style",
            existing_type=sa.String(length=16),
            existing_nullable=False,
            server_default=value,
        )


def upgrade() -> None:
    _set_server_default("dialogue")


def downgrade() -> None:
    _set_server_default("balanced")
