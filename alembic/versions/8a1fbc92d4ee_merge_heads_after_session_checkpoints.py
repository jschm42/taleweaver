"""merge heads after session checkpoints

Revision ID: 8a1fbc92d4ee
Revises: c2f8a4d9b611, e3c88ba0e84a
Create Date: 2026-05-26 13:05:00.000000
"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = '8a1fbc92d4ee'
down_revision: Union[str, Sequence[str], None] = ('c2f8a4d9b611', 'e3c88ba0e84a')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
