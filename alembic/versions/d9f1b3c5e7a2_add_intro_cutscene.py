"""add the adventure's intro cut-scene

``intro_cutscene_id`` names a cut-scene of the adventure's library that is shown right after a
new session starts, before the first chapter's cut-scene. Existing adventures have none.

Revision ID: d9f1b3c5e7a2
Revises: c7e9a1b3d5f8
Create Date: 2026-11-23 19:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9f1b3c5e7a2"
down_revision: Union[str, Sequence[str], None] = "c7e9a1b3d5f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.add_column(sa.Column("intro_cutscene_id", sa.String(length=40), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.drop_column("intro_cutscene_id")
