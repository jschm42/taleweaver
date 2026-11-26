"""add mcp_settings to server_settings and mcp_tokens table

Revision ID: a9c3e7f1b2d4
Revises: e1a2b3c4d5e6
Create Date: 2026-11-26 10:50:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9c3e7f1b2d4"
down_revision = "e1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "server_settings" in tables:
        existing = {c["name"] for c in insp.get_columns("server_settings")}
        if "mcp_settings" not in existing:
            with op.batch_alter_table("server_settings", schema=None) as batch_op:
                batch_op.add_column(sa.Column("mcp_settings", sa.JSON(), nullable=True))

    if "mcp_tokens" not in tables:
        op.create_table(
            "mcp_tokens",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("token_prefix", sa.String(length=16), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("allowed_features", sa.JSON(), nullable=True),
            sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash"),
        )
        op.create_index("ix_mcp_tokens_token_hash", "mcp_tokens", ["token_hash"], unique=True)
        op.create_index("ix_mcp_tokens_user_id", "mcp_tokens", ["user_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "mcp_tokens" in tables:
        op.drop_index("ix_mcp_tokens_user_id", table_name="mcp_tokens")
        op.drop_index("ix_mcp_tokens_token_hash", table_name="mcp_tokens")
        op.drop_table("mcp_tokens")

    if "server_settings" in tables:
        existing = {c["name"] for c in insp.get_columns("server_settings")}
        if "mcp_settings" in existing:
            with op.batch_alter_table("server_settings", schema=None) as batch_op:
                batch_op.drop_column("mcp_settings")
