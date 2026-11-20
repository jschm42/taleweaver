"""merge dynamic scenes and respawn migrations

Revision ID: cfa8f8fd4b9e
Revises: 94ca85d30c95, e4b8f2a6c1d9
Create Date: 2026-11-16 19:52:48.586876
"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "cfa8f8fd4b9e"
down_revision: Union[str, Sequence[str], None] = ("94ca85d30c95", "e4b8f2a6c1d9")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
