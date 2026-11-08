"""rename the music feature to audio

Tracks of the library may also be spoken text, so the columns are named after audio:
``music_tracks`` -> ``audio_tracks``, ``music_enabled`` -> ``audio_enabled`` (adventure
templates), ``music_track_id`` -> ``audio_track_id`` (scenes) and ``music_settings`` ->
``audio_settings`` (server settings). Files already stored in ``music/`` folders keep their
URLs; new files go to ``audio/`` folders.

Revision ID: b5e1f8c3a9d2
Revises: a3d9e6b2f1c7
Create Date: 2026-11-08 18:00:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5e1f8c3a9d2"
down_revision = "a3d9e6b2f1c7"
branch_labels = None
depends_on = None

_RENAMES = (
    ("adventure_templates", "music_tracks", "audio_tracks"),
    ("adventure_templates", "music_enabled", "audio_enabled"),
    ("world_scenes", "music_track_id", "audio_track_id"),
    ("server_settings", "music_settings", "audio_settings"),
)


def upgrade() -> None:
    for table, old, new in _RENAMES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column(old, new_column_name=new)


def downgrade() -> None:
    for table, old, new in reversed(_RENAMES):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column(new, new_column_name=old)
