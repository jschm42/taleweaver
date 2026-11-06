"""move server-wide settings from the users table into server_settings

API keys, model / image / TTS settings, the catalogs, the narrator voices and the shared game
settings were stored per user (copied to every row). They now live once in the single-row
table ``server_settings``. The values are taken from the oldest admin (the former source of
the copies), the per-user columns are dropped, and ``users.game_settings`` keeps only the
player-owned keys.

Revision ID: b8d4f0a2c6e1
Revises: e5b2d7f1a9c3
Create Date: 2026-11-06 14:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8d4f0a2c6e1"
down_revision = "e5b2d7f1a9c3"
branch_labels = None
depends_on = None

MOVED_FIELDS = (
    "encrypted_api_keys",
    "llm_settings",
    "t2i_settings",
    "tts_settings",
    "image_styles_catalog",
    "tone_catalog",
    "narrator_voice_catalog",
)
# Mirrors backend.core.tts_preferences.USER_SCOPED_GAME_SETTING_KEYS at this revision.
USER_SCOPED_GAME_SETTING_KEYS = ("tts_preferences",)
SERVER_SETTINGS_ID = 1


def _users_table(with_moved: bool) -> sa.Table:
    columns = [
        sa.column("id", sa.String),
        sa.column("role", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("game_settings", sa.JSON),
    ]
    if with_moved:
        columns += [sa.column(field, sa.JSON) for field in MOVED_FIELDS]
    return sa.table("users", *columns)


server_settings = sa.table(
    "server_settings",
    sa.column("id", sa.Integer),
    sa.column("created_at", sa.DateTime),
    sa.column("updated_at", sa.DateTime),
    sa.column("game_settings", sa.JSON),
    *(sa.column(field, sa.JSON) for field in MOVED_FIELDS),
)


def _split_game_settings(game_settings) -> tuple[dict, dict]:
    """(shared, personal) parts of a game_settings dict."""
    raw = game_settings if isinstance(game_settings, dict) else {}
    shared = {k: v for k, v in raw.items() if k not in USER_SCOPED_GAME_SETTING_KEYS}
    personal = {k: v for k, v in raw.items() if k in USER_SCOPED_GAME_SETTING_KEYS}
    return shared, personal


def _source_user(conn: sa.engine.Connection, users: sa.Table):
    query = (
        sa.select(users)
        .where(users.c.role == "admin")
        .order_by(users.c.created_at, users.c.id)
        .limit(1)
    )
    return conn.execute(query).mappings().first()


def _create_server_settings_table() -> None:
    op.create_table(
        "server_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        *(sa.Column(field, sa.JSON(), nullable=True) for field in MOVED_FIELDS),
        sa.Column("game_settings", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def upgrade() -> None:
    _create_server_settings_table()
    conn = op.get_bind()
    users = _users_table(with_moved=True)

    source = _source_user(conn, users)
    values = {field: (source[field] if source else None) for field in MOVED_FIELDS}
    values["game_settings"] = _split_game_settings(source["game_settings"] if source else None)[0]
    now = sa.func.current_timestamp()
    conn.execute(
        sa.insert(server_settings).values(
            id=SERVER_SETTINGS_ID, created_at=now, updated_at=now, **values
        )
    )

    for user_id, game_settings in conn.execute(sa.select(users.c.id, users.c.game_settings)):
        personal = _split_game_settings(game_settings)[1]
        conn.execute(
            sa.update(users).where(users.c.id == user_id).values(game_settings=personal or None)
        )

    with op.batch_alter_table("users", schema=None) as batch_op:
        for field in MOVED_FIELDS:
            batch_op.drop_column(field)


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        for field in MOVED_FIELDS:
            batch_op.add_column(sa.Column(field, sa.JSON(), nullable=True))

    conn = op.get_bind()
    users = _users_table(with_moved=True)
    row = conn.execute(sa.select(server_settings)).mappings().first()
    if row is not None:
        shared = _split_game_settings(row["game_settings"])[0]
        for user_id, game_settings in conn.execute(sa.select(users.c.id, users.c.game_settings)):
            values = {field: row[field] for field in MOVED_FIELDS}
            values["game_settings"] = {**shared, **_split_game_settings(game_settings)[1]}
            conn.execute(sa.update(users).where(users.c.id == user_id).values(**values))

    op.drop_table("server_settings")
