"""music track library per adventure

Replaces per-scene music (``world_scenes.music_prompt`` / ``music_url``) and the main theme
(``adventure_templates.music_prompt`` / ``music_url``) with a library of tracks
(``adventure_templates.music_tracks``, JSON) that scenes select via
``world_scenes.music_track_id``. Existing scene music and main themes become library tracks;
template scenes keep pointing at theirs.

Revision ID: f7a1c4e8d2b6
Revises: e5b8f3d0c2a4
Create Date: 2026-11-08 10:00:00.000000
"""

import json
import secrets

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7a1c4e8d2b6"
down_revision = "e5b8f3d0c2a4"
branch_labels = None
depends_on = None


def _track(name: str, prompt, url) -> dict:
    return {
        "id": secrets.token_hex(6),
        "name": name[:100],
        "prompt": (prompt or "")[:1000],
        "url": url,
        "source": "generated" if url else "planned",
        "reference_scene_id": None,
        "created_at": None,
    }


def _move_music_into_libraries(bind) -> None:
    libraries: dict[str, list[dict]] = {}
    templates = bind.execute(
        sa.text("SELECT id, music_prompt, music_url FROM adventure_templates")
    ).fetchall()
    for template_id, prompt, url in templates:
        if prompt or url:
            libraries.setdefault(template_id, []).append(_track("Main theme", prompt, url))
    scenes = bind.execute(
        sa.text(
            "SELECT pk, template_id, label, music_prompt, music_url FROM world_scenes "
            "WHERE session_id IS NULL AND template_id IS NOT NULL "
            "AND (music_prompt IS NOT NULL OR music_url IS NOT NULL)"
        )
    ).fetchall()
    for pk, template_id, label, prompt, url in scenes:
        track = _track(f"{label or 'Scene'} music", prompt, url)
        libraries.setdefault(template_id, []).append(track)
        bind.execute(
            sa.text("UPDATE world_scenes SET music_track_id = :tid WHERE pk = :pk"),
            {"tid": track["id"], "pk": pk},
        )
    for template_id, tracks in libraries.items():
        bind.execute(
            sa.text("UPDATE adventure_templates SET music_tracks = :tracks WHERE id = :id"),
            {"tracks": json.dumps(tracks), "id": template_id},
        )


def upgrade() -> None:
    with op.batch_alter_table("world_scenes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("music_track_id", sa.String(length=50), nullable=True))
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.add_column(sa.Column("music_tracks", sa.JSON(), nullable=True))

    _move_music_into_libraries(op.get_bind())

    with op.batch_alter_table("world_scenes", schema=None) as batch_op:
        batch_op.drop_column("music_url")
        batch_op.drop_column("music_prompt")
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.drop_column("music_url")
        batch_op.drop_column("music_prompt")


def downgrade() -> None:
    # Library tracks are not mapped back; scenes lose their music assignment.
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.add_column(sa.Column("music_prompt", sa.String(length=1000), nullable=True))
        batch_op.add_column(sa.Column("music_url", sa.String(length=255), nullable=True))
        batch_op.drop_column("music_tracks")
    with op.batch_alter_table("world_scenes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("music_prompt", sa.String(length=1000), nullable=True))
        batch_op.add_column(sa.Column("music_url", sa.String(length=255), nullable=True))
        batch_op.drop_column("music_track_id")
