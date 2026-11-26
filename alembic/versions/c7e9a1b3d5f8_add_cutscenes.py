"""add the cut-scene library of an adventure

Cut-scenes are slide shows (image + text, optional audio track) shown over the play view at a
chapter start or by ``tw.cutscene.play``. Existing adventures start without cut-scenes.

Revision ID: c7e9a1b3d5f8
Revises: b5d7f9a1c3e6
Create Date: 2026-11-23 15:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7e9a1b3d5f8"
down_revision: Union[str, Sequence[str], None] = "b5d7f9a1c3e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.add_column(sa.Column("cutscenes", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.drop_column("cutscenes")
