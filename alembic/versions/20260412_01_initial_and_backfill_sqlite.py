"""Initial schema with SQLite-safe backfill

Revision ID: 20260412_01
Revises:
Create Date: 2026-04-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260412_01"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _has_column(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def _has_unique_index(bind, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(bind)
    return index_name in {idx["name"] for idx in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, "users"):
        op.create_table(
            "users",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("username", sa.String(length=50), nullable=False),
            sa.Column("encrypted_api_keys", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    if not _has_unique_index(bind, "users", "uq_users_username"):
        op.create_index("uq_users_username", "users", ["username"], unique=True)

    if not _has_table(bind, "adventures"):
        op.create_table(
            "adventures",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("strict_rules", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("heartbeat_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("heartbeat_interval", sa.Integer(), nullable=False, server_default=sa.text("10")),
            sa.Column("game_over_rules", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    else:
        if not _has_column(bind, "adventures", "strict_rules"):
            op.add_column(
                "adventures",
                sa.Column("strict_rules", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            )
        if not _has_column(bind, "adventures", "heartbeat_enabled"):
            op.add_column(
                "adventures",
                sa.Column("heartbeat_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            )
        if not _has_column(bind, "adventures", "heartbeat_interval"):
            op.add_column(
                "adventures",
                sa.Column("heartbeat_interval", sa.Integer(), nullable=False, server_default=sa.text("10")),
            )
        if not _has_column(bind, "adventures", "game_over_rules"):
            op.add_column("adventures", sa.Column("game_over_rules", sa.JSON(), nullable=True))

    if not _has_table(bind, "avatars"):
        op.create_table(
            "avatars",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("hp", sa.Integer(), nullable=False, server_default=sa.text("200")),
            sa.Column("stamina", sa.Integer(), nullable=False, server_default=sa.text("200")),
            sa.Column("mana", sa.Integer(), nullable=False, server_default=sa.text("200")),
            sa.Column("stats", sa.JSON(), nullable=False),
            sa.Column("inventory", sa.JSON(), nullable=False),
            sa.Column("equipment", sa.JSON(), nullable=False),
            sa.Column("status_effects", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    if not _has_table(bind, "game_states"):
        op.create_table(
            "game_states",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("avatar_id", sa.String(length=36), sa.ForeignKey("avatars.id"), nullable=False),
            sa.Column("adventure_id", sa.String(length=36), sa.ForeignKey("adventures.id"), nullable=False),
            sa.Column("scene_id", sa.String(length=255), nullable=False),
            sa.Column("in_game_time", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("is_paused", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    elif not _has_column(bind, "game_states", "is_paused"):
        op.add_column(
            "game_states",
            sa.Column("is_paused", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )

    if not _has_table(bind, "chat_messages"):
        op.create_table(
            "chat_messages",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("game_state_id", sa.String(length=36), sa.ForeignKey("game_states.id"), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()

    if _has_table(bind, "chat_messages"):
        op.drop_table("chat_messages")
    if _has_table(bind, "game_states"):
        op.drop_table("game_states")
    if _has_table(bind, "avatars"):
        op.drop_table("avatars")
    if _has_table(bind, "adventures"):
        op.drop_table("adventures")
    if _has_table(bind, "users"):
        op.drop_table("users")
