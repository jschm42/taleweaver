"""add cached_suggestions column to validation_runs

Revision ID: 9c2b8e0a4f12
Revises: 7e6a4b2c9031
Create Date: 2026-06-30 16:30:00.000000
"""

from typing import Optional, Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "9c2b8e0a4f12"
down_revision: Union[str, Sequence[str], None] = "7e6a4b2c9031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "validation_runs",
        sa.Column(
            "cached_suggestions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("validation_runs", "cached_suggestions")
