"""default narration_style to balanced for new sessions

Revision ID: c7e2a4f9d1b3
Revises: b4d6f8a0c2e3
Create Date: 2026-10-28 22:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7e2a4f9d1b3"
down_revision: Union[str, Sequence[str], None] = "b4d6f8a0c2e3"
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
    _set_server_default("balanced")


def downgrade() -> None:
    _set_server_default("dialogue")
