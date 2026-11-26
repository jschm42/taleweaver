"""add win and game-over cut-scenes

``win_cutscene_id`` and ``game_over_cutscene_id`` name optional cut-scenes of the adventure's
library that are shown when the adventure is won or lost, before the ending card. Existing
adventures have none.

Revision ID: e1a2b3c4d5e6
Revises: d9f1b3c5e7a2
Create Date: 2026-11-25 11:38:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "d9f1b3c5e7a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.add_column(sa.Column("win_cutscene_id", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("game_over_cutscene_id", sa.String(length=40), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.drop_column("game_over_cutscene_id")
        batch_op.drop_column("win_cutscene_id")
