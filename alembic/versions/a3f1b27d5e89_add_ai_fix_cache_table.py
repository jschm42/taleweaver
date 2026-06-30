"""add ai_fix_cache table

Revision ID: a3f1b27d5e89
Revises: 9c2b8e0a4f12
Create Date: 2026-06-30 17:00:00.000000
"""

from typing import Optional, Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a3f1b27d5e89"
down_revision: Union[str, Sequence[str], None] = "9c2b8e0a4f12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_fix_cache",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("finding_signature", sa.String(length=512), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["template_id"], ["adventure_templates.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "template_id", "user_id", "finding_signature",
            name="uq_ai_fix_cache_user_template_finding",
        ),
    )
    op.create_index(
        "ix_ai_fix_cache_user_template_finding",
        "ai_fix_cache",
        ["user_id", "template_id", "finding_signature"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ai_fix_cache_user_template_finding", table_name="ai_fix_cache")
    op.drop_table("ai_fix_cache")
