"""add email and is_active to users

Self-registration stores an optional e-mail address and creates accounts inactive until an
administrator activates them. Existing users stay active.

Revision ID: e8c9d1a2b3f4
Revises: b5e1f8c3a9d2
Create Date: 2026-11-08 20:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8c9d1a2b3f4"
down_revision = "b5e1f8c3a9d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("email", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1"))
        )
        batch_op.create_index("ix_users_email", ["email"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index("ix_users_email")
        batch_op.drop_column("is_active")
        batch_op.drop_column("email")
