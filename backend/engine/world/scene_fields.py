"""The scene columns that make up a scene's content, shared by every place that copies scenes.

Session start, session copies, imports and template resets each build ``WorldScene`` rows.
Listing the fields once keeps them from silently dropping scripts or decorations.
"""

from copy import deepcopy
from typing import Any

SCENE_SCRIPT_FIELDS = (
    "on_enter_scene_script",
    "on_enter_scene_text",
    "on_leave_scene_script",
    "on_leave_scene_text",
    "helpers_script",
)
SCENE_CONTENT_FIELDS = ("id", "label", "description", "decorative_objects", *SCENE_SCRIPT_FIELDS)


def scene_content(scene: Any) -> dict[str, Any]:
    """Content columns of a ``WorldScene`` row, as keyword arguments for a copy."""
    return {field: deepcopy(getattr(scene, field, None)) for field in SCENE_CONTENT_FIELDS}


def scene_content_from_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Content columns from a serialized scene (manifest or session export)."""
    content = {field: deepcopy(data.get(field)) for field in SCENE_CONTENT_FIELDS}
    content["label"] = data.get("label") or data.get("name") or data.get("id")
    content["description"] = data.get("description") or ""
    return content
