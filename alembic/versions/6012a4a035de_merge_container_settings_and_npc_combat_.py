"""merge container settings and npc combat heads

Revision ID: 6012a4a035de
Revises: b7a4d83c6e21, f1c9d4a7b2e3
Create Date: 2026-05-21 08:36:33.857785
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision: str = '6012a4a035de'
down_revision: Union[str, Sequence[str], None] = ('b7a4d83c6e21', 'f1c9d4a7b2e3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
