"""add voice to avatars

Revision ID: b4d6f8a0c2e3
Revises: a9c3e5f7b1d2
Create Date: 2026-10-26 20:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4d6f8a0c2e3"
down_revision: Union[str, Sequence[str], None] = "a9c3e5f7b1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("avatars", schema=None) as batch_op:
        batch_op.add_column(sa.Column("voice", sa.String(length=50), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("avatars", schema=None) as batch_op:
        batch_op.drop_column("voice")
