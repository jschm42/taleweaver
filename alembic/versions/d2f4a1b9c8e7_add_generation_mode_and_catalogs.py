"""Add adventure generation mode fields and user catalogs.

Revision ID: d2f4a1b9c8e7
Revises: c1a2b3d4e5f6
Create Date: 2026-04-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2f4a1b9c8e7"
down_revision: Union[str, Sequence[str], None] = "c1a2b3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table_name: str) -> bool:
    row = conn.execute(
        sa.text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": table_name},
    ).fetchone()
    return row is not None


def _columns(conn, table_name: str) -> set[str]:
    rows = conn.execute(sa.text(f"PRAGMA table_info('{table_name}')")).fetchall()
    return {r[1] for r in rows}


def upgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "adventures"):
        adventure_cols = _columns(conn, "adventures")
        with op.batch_alter_table("adventures", schema=None) as batch_op:
            if "rule_enforcement_mode" not in adventure_cols:
                batch_op.add_column(sa.Column("rule_enforcement_mode", sa.String(length=16), nullable=False, server_default=sa.text("'strict'")))
            if "pacing_minutes" not in adventure_cols:
                batch_op.add_column(sa.Column("pacing_minutes", sa.Integer(), nullable=False, server_default=sa.text("5")))
            if "clock_enabled" not in adventure_cols:
                batch_op.add_column(sa.Column("clock_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")))
            if "selected_image_styles" not in adventure_cols:
                batch_op.add_column(sa.Column("selected_image_styles", sa.JSON(), nullable=True))
            if "selected_tone" not in adventure_cols:
                batch_op.add_column(sa.Column("selected_tone", sa.String(length=100), nullable=True))

    if _table_exists(conn, "users"):
        user_cols = _columns(conn, "users")
        with op.batch_alter_table("users", schema=None) as batch_op:
            if "image_styles_catalog" not in user_cols:
                batch_op.add_column(sa.Column("image_styles_catalog", sa.JSON(), nullable=True))
            if "tone_catalog" not in user_cols:
                batch_op.add_column(sa.Column("tone_catalog", sa.JSON(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "users"):
        user_cols = _columns(conn, "users")
        with op.batch_alter_table("users", schema=None) as batch_op:
            if "tone_catalog" in user_cols:
                batch_op.drop_column("tone_catalog")
            if "image_styles_catalog" in user_cols:
                batch_op.drop_column("image_styles_catalog")

    if _table_exists(conn, "adventures"):
        adventure_cols = _columns(conn, "adventures")
        with op.batch_alter_table("adventures", schema=None) as batch_op:
            if "selected_tone" in adventure_cols:
                batch_op.drop_column("selected_tone")
            if "selected_image_styles" in adventure_cols:
                batch_op.drop_column("selected_image_styles")
            if "clock_enabled" in adventure_cols:
                batch_op.drop_column("clock_enabled")
            if "pacing_minutes" in adventure_cols:
                batch_op.drop_column("pacing_minutes")
            if "rule_enforcement_mode" in adventure_cols:
                batch_op.drop_column("rule_enforcement_mode")
