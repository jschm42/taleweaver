"""add narrator voice catalog to users and narrator voice to adventure templates

Revision ID: e5b9d3f7a2c4
Revises: a7c3e9f5b2d1
Create Date: 2026-10-31 11:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5b9d3f7a2c4"
down_revision: Union[str, Sequence[str], None] = "a7c3e9f5b2d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("narrator_voice_catalog", sa.JSON(), nullable=True))
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.add_column(sa.Column("narrator_voice", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.drop_column("narrator_voice")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("narrator_voice_catalog")
