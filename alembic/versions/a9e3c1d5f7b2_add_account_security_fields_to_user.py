"""add account security fields to user

Revision ID: a9e3c1d5f7b2
Revises: c7d2e4f6a8b1
Create Date: 2026-10-18 12:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9e3c1d5f7b2"
down_revision = "c7d2e4f6a8b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("token_version", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("recovery_code_hashes", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("password_reset_token_hash", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("password_reset_expires_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_index(
            "ix_users_password_reset_token_hash", ["password_reset_token_hash"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index("ix_users_password_reset_token_hash")
        batch_op.drop_column("password_reset_expires_at")
        batch_op.drop_column("password_reset_token_hash")
        batch_op.drop_column("recovery_code_hashes")
        batch_op.drop_column("token_version")
