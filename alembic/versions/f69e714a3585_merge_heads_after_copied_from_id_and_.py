"""merge heads after copied_from_id and reveal_rule

Revision ID: f69e714a3585
Revises: 30b3bd896258, 373783a380c1
Create Date: 2026-05-20 15:12:11.166525
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision: str = 'f69e714a3585'
down_revision: Union[str, Sequence[str], None] = ('30b3bd896258', '373783a380c1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
