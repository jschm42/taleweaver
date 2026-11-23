"""every adventure has a region: add the default region and assign every scene

An adventure without a built region gets the default region (id MAIN, named after the
adventure, in the middle of the world map). An adventure that has built regions but also
scenes without one gets an extra built region "Other places" for them. The template's scenes
without a region, the session copies of those scenes and the session snapshots are updated,
so running sessions know the region their scenes belong to. Scenes created at runtime
(dynamic zones, ids starting with DYN_) keep no region.

Downgrade keeps the regions: they are valid data for the older code as well.

Revision ID: b5d7f9a1c3e6
Revises: a3c5e7f9b1d4
Create Date: 2026-11-23 15:00:00.000000

"""

import json
from typing import Any, Optional, Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5d7f9a1c3e6"
down_revision: Union[str, Sequence[str], None] = "a3c5e7f9b1d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SNAPSHOT_KEY = "__manifest_snapshot__"
_PLAYER_KEYS = ("id", "label", "description", "map_x", "map_y", "order_index")


def _load(raw: Any) -> Any:
    if isinstance(raw, (str, bytes)):
        try:
            return json.loads(raw)
        except ValueError:
            return None
    return raw


def _is_built(section: Any) -> bool:
    return isinstance(section, dict) and str(section.get("status") or "built") == "built"


def _new_section(sections: list[Any], title: Optional[str]) -> dict[str, Any]:
    taken = {str(s.get("id")) for s in sections if isinstance(s, dict)}
    section_id, number = "MAIN", 1
    while section_id in taken:
        number += 1
        section_id = f"MAIN_{number}"
    has_built = any(_is_built(s) for s in sections)
    label = "Other places" if has_built else (str(title or "").strip()[:100] or "Main region")
    return {
        "id": section_id,
        "label": label,
        "description": "",
        "map_x": 50.0,
        "map_y": 50.0,
        "order_index": len(sections),
        "status": "built",
        "brief": "",
        "summary": "",
        "planned_links": [],
        "generation_error": "",
        "generation_notes": [],
        "generation_settings": None,
        "generated": None,
    }


def _player_section(section: dict[str, Any]) -> dict[str, Any]:
    return {key: section[key] for key in _PLAYER_KEYS}


def _update_manifest(manifest: Any, sections: list[Any], section_id: str) -> Any:
    if not isinstance(manifest, dict):
        return manifest
    manifest["sections"] = sections
    for scene in manifest.get("scenes") or []:
        if isinstance(scene, dict) and not scene.get("section_id"):
            scene["section_id"] = section_id
    return manifest


def _update_snapshot(states: Any, section: dict[str, Any]) -> Any:
    """Adds the region to a session's adventure snapshot (player fields only)."""
    snapshot = states.get(_SNAPSHOT_KEY) if isinstance(states, dict) else None
    if not isinstance(snapshot, dict):
        return None
    adventure = snapshot.setdefault("adventure", {})
    known = (
        adventure.get("world_sections") if isinstance(adventure.get("world_sections"), list) else []
    )
    if any(isinstance(s, dict) and s.get("id") == section["id"] for s in known):
        return None
    adventure["world_sections"] = [*known, _player_section(section)]
    manifest = snapshot.get("original_manifest")
    if isinstance(manifest, dict):
        manifest["sections"] = adventure["world_sections"]
    return states


def _migrate_sessions(conn: Any, template_id: str, section: dict[str, Any]) -> None:
    rows = conn.execute(
        sa.text("SELECT session_id, entity_states FROM session_states WHERE template_id = :t"),
        {"t": template_id},
    ).fetchall()
    for session_id, raw_states in rows:
        conn.execute(
            sa.text(
                "UPDATE world_scenes SET section_id = :s WHERE session_id = :id "
                "AND (section_id IS NULL OR section_id = '') AND substr(id, 1, 4) != 'DYN_'"
            ),
            {"s": section["id"], "id": session_id},
        )
        states = _update_snapshot(_load(raw_states), section)
        if states is not None:
            conn.execute(
                sa.text("UPDATE session_states SET entity_states = :e WHERE session_id = :id"),
                {"e": json.dumps(states), "id": session_id},
            )


def _migrate_template(
    conn: Any, template_id: str, title: Any, raw_sections: Any, raw_manifest: Any
) -> None:
    sections = [s for s in (_load(raw_sections) or []) if isinstance(s, dict)]
    unassigned = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM world_scenes WHERE template_id = :t AND session_id IS NULL "
            "AND (section_id IS NULL OR section_id = '') AND substr(id, 1, 4) != 'DYN_'"
        ),
        {"t": template_id},
    ).scalar()
    if any(_is_built(s) for s in sections) and not unassigned:
        return
    section = _new_section(sections, title)
    sections = [*sections, section]
    conn.execute(
        sa.text(
            "UPDATE world_scenes SET section_id = :s WHERE template_id = :t AND session_id IS NULL "
            "AND (section_id IS NULL OR section_id = '') AND substr(id, 1, 4) != 'DYN_'"
        ),
        {"s": section["id"], "t": template_id},
    )
    manifest = _update_manifest(_load(raw_manifest), sections, section["id"])
    conn.execute(
        sa.text(
            "UPDATE adventure_templates SET world_sections = :w, original_manifest = :m WHERE id = :t"
        ),
        {
            "w": json.dumps(sections),
            "m": json.dumps(manifest) if manifest is not None else None,
            "t": template_id,
        },
    )
    _migrate_sessions(conn, template_id, section)


def upgrade() -> None:
    conn = op.get_bind()
    templates = conn.execute(
        sa.text("SELECT id, title, world_sections, original_manifest FROM adventure_templates")
    ).fetchall()
    for template_id, title, raw_sections, raw_manifest in templates:
        _migrate_template(conn, template_id, title, raw_sections, raw_manifest)


def downgrade() -> None:
    # The regions stay: an adventure with regions is valid for the older code too.
    pass
