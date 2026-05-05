"""merge heads

Revision ID: d44a4242b4e9
Revises: b3477fb2839a, e5624ad2bd9f
Create Date: 2026-05-05 08:34:20.594460
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision: str = 'd44a4242b4e9'
down_revision: Union[str, Sequence[str], None] = ('b3477fb2839a', 'e5624ad2bd9f')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
