"""add validation_runs table

Revision ID: 7e6a4b2c9031
Revises: 764a99e41994
Create Date: 2026-06-30 12:00:00.000000
"""

from typing import Optional, Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "7e6a4b2c9031"
down_revision: Union[str, Sequence[str], None] = "764a99e41994"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "validation_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("include_ai", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("structural_findings", sa.JSON(), nullable=False),
        sa.Column("ai_findings", sa.JSON(), nullable=False),
        sa.Column("ai_skipped_reason", sa.String(length=64), nullable=True),
        sa.Column("structural_finding_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai_finding_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cached_suggestions", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["template_id"], ["adventure_templates.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_validation_runs_user_template",
        "validation_runs",
        ["user_id", "template_id", "run_at"],
        unique=False,
    )
    op.create_index(
        "ix_validation_runs_template",
        "validation_runs",
        ["template_id"],
        unique=False,
    )
    op.create_index(
        "ix_validation_runs_user",
        "validation_runs",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_validation_runs_user", table_name="validation_runs")
    op.drop_index("ix_validation_runs_template", table_name="validation_runs")
    op.drop_index("ix_validation_runs_user_template", table_name="validation_runs")
    op.drop_table("validation_runs")
