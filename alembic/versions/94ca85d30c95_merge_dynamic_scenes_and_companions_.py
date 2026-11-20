"""merge dynamic scenes and companions migrations

Revision ID: 94ca85d30c95
Revises: b4e8c1d2f3a5, d1a7c3e9b5f2
Create Date: 2026-11-14 16:11:57.433222
"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "94ca85d30c95"
down_revision: Union[str, Sequence[str], None] = ("b4e8c1d2f3a5", "d1a7c3e9b5f2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
