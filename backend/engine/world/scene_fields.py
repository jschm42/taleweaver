"""The scene columns that make up a scene's content, shared by every place that copies scenes.

Session start, session copies, imports and template resets each build ``WorldScene`` rows.
Listing the fields once keeps them from silently dropping scripts or decorations.
"""

from copy import deepcopy
from typing import Any

from backend.engine.rules.fast_travel import normalize_unlock_mode
from backend.engine.world.sections import section_id_or_none

SCENE_SCRIPT_FIELDS = (
    "on_enter_scene_script",
    "on_enter_scene_text",
    "on_leave_scene_script",
    "on_leave_scene_text",
    "helpers_script",
)
# The scene's track of the adventure's audio library travels with the scene.
SCENE_AUDIO_FIELDS = ("audio_track_id",)
# Respawn mode: a fallen protagonist wakes up at the last revival point reached.
SCENE_RESPAWN_FIELDS = ("is_respawn_point",)
# World section (region) the scene belongs to (engine/world/sections.py).
SCENE_SECTION_FIELDS = ("section_id",)
# Fast travel point and how it is unlocked (engine/rules/fast_travel.py).
SCENE_TRAVEL_FIELDS = ("is_fast_travel_point", "fast_travel_unlock")
SCENE_CONTENT_FIELDS = (
    "id",
    "label",
    "description",
    "decorative_objects",
    "dynamic_zone",
    *SCENE_SCRIPT_FIELDS,
    *SCENE_AUDIO_FIELDS,
    *SCENE_RESPAWN_FIELDS,
    *SCENE_SECTION_FIELDS,
    *SCENE_TRAVEL_FIELDS,
)


def scene_content(scene: Any) -> dict[str, Any]:
    """Content columns of a ``WorldScene`` row, as keyword arguments for a copy."""
    content = {field: deepcopy(getattr(scene, field, None)) for field in SCENE_CONTENT_FIELDS}
    content["is_respawn_point"] = bool(content.get("is_respawn_point"))
    content["is_fast_travel_point"] = bool(content.get("is_fast_travel_point"))
    content["fast_travel_unlock"] = normalize_unlock_mode(content.get("fast_travel_unlock"))
    return content


def scene_content_from_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Content columns from a serialized scene (manifest or session export)."""
    content = {field: deepcopy(data.get(field)) for field in SCENE_CONTENT_FIELDS}
    content["label"] = data.get("label") or data.get("name") or data.get("id")
    content["description"] = data.get("description") or ""
    # Session exports written before the rename to audio.
    content["audio_track_id"] = data.get("audio_track_id") or data.get("music_track_id")
    content["is_respawn_point"] = data.get("is_respawn_point") is True
    content["section_id"] = section_id_or_none(data.get("section_id"))
    content["is_fast_travel_point"] = data.get("is_fast_travel_point") is True
    content["fast_travel_unlock"] = normalize_unlock_mode(data.get("fast_travel_unlock"))
    return content
