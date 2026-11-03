"""raise original_prompt limit to 50000 characters

Revision ID: e5b2d7f1a9c3
Revises: c4e7a1b9d2f6
Create Date: 2026-11-02 12:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5b2d7f1a9c3"
down_revision = "c4e7a1b9d2f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.alter_column(
            "original_prompt",
            existing_type=sa.String(length=20000),
            type_=sa.String(length=50000),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.alter_column(
            "original_prompt",
            existing_type=sa.String(length=50000),
            type_=sa.String(length=20000),
            existing_nullable=True,
        )
