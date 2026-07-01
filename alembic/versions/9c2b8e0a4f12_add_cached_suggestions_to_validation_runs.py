"""add cached_suggestions column to validation_runs

Revision ID: 9c2b8e0a4f12
Revises: 7e6a4b2c9031
Create Date: 2026-06-30 16:30:00.000000

The ``cached_suggestions`` column was already included in the
``validation_runs`` table definition added by revision ``7e6a4b2c9031``,
so this revision is a no-op kept only to preserve the migration chain.
"""

from typing import Optional, Sequence, Union


revision: str = "9c2b8e0a4f12"
down_revision: Union[str, Sequence[str], None] = "7e6a4b2c9031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
