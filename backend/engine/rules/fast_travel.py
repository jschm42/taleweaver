"""Fast travel points: scenes the player can travel to from anywhere once unlocked.

An author marks scenes with ``WorldScene.is_fast_travel_point``. ``fast_travel_unlock`` says how
a point becomes a destination: ``visit`` (default, on first entry) or ``script`` (only
``tw.game.unlock_fast_travel``). The session record lives in ``entity_states["__travel__"]``
so it is part of every checkpoint::

    {"unlocked": ["HARBOR_SQUARE", ...], "disabled": False, "reason": ""}

Scripts change it with ``tw.game`` calls that record ordered ``ScriptChangeset.travel_ops``;
every changeset applier replays them with :func:`apply_travel_ops`.
Spec: docs/specs/world_sections.md (6.3).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

TRAVEL_KEY = "__travel__"
UNLOCK_MODES = ("visit", "script")
DEFAULT_UNLOCK_MODE = "visit"
MAX_REASON_LENGTH = 200
MAX_UNLOCKED_POINTS = 500


def normalize_unlock_mode(raw: Any) -> str:
    mode = str(raw or "").strip().lower()
    return mode if mode in UNLOCK_MODES else DEFAULT_UNLOCK_MODE


def _scene_id(raw: Any) -> str:
    return str(raw or "").strip().upper()


def read_travel(entity_states: Any) -> dict[str, Any]:
    """A normalized, independent copy of the session's fast travel record."""
    raw = entity_states.get(TRAVEL_KEY) if isinstance(entity_states, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    unlocked = [_scene_id(s) for s in raw.get("unlocked") or [] if _scene_id(s)]
    return {
        "unlocked": list(dict.fromkeys(unlocked))[:MAX_UNLOCKED_POINTS],
        "disabled": raw.get("disabled") is True,
        "reason": str(raw.get("reason") or "")[:MAX_REASON_LENGTH],
    }


def store_travel(entity_states: dict[str, Any], record: dict[str, Any]) -> None:
    entity_states[TRAVEL_KEY] = deepcopy(record)


def unlock_point(record: dict[str, Any], scene_id: Any) -> bool:
    """Adds a point; returns True when it was new."""
    point = _scene_id(scene_id)
    if not point or point in record["unlocked"]:
        return False
    record["unlocked"].append(point)
    return True


def lock_point(record: dict[str, Any], scene_id: Any) -> bool:
    point = _scene_id(scene_id)
    if point not in record["unlocked"]:
        return False
    record["unlocked"].remove(point)
    return True


def unlock_on_visit(entity_states: dict[str, Any], scene: Any) -> bool:
    """Unlocks ``scene`` when it is a fast travel point with the unlock mode ``visit``."""
    if scene is None or not getattr(scene, "is_fast_travel_point", False):
        return False
    if normalize_unlock_mode(getattr(scene, "fast_travel_unlock", None)) != "visit":
        return False
    record = read_travel(entity_states)
    if not unlock_point(record, getattr(scene, "id", None)):
        return False
    store_travel(entity_states, record)
    return True


def _set_enabled(record: dict[str, Any], op: dict[str, Any]) -> bool:
    record["disabled"] = op.get("enabled") is False
    record["reason"] = str(op.get("reason") or "")[:MAX_REASON_LENGTH] if record["disabled"] else ""
    return True


_OPS = {
    "unlock": lambda record, op: unlock_point(record, op.get("scene_id")),
    "lock": lambda record, op: lock_point(record, op.get("scene_id")),
    "enable": _set_enabled,
}


def apply_travel_ops(entity_states: dict[str, Any], ops: Optional[list[Any]]) -> bool:
    """Replays ``tw.game`` fast travel operations in order; returns True when any applied."""
    if not ops:
        return False
    record = read_travel(entity_states)
    changed = False
    for op in ops:
        handler = _OPS.get(op.get("op")) if isinstance(op, dict) else None
        changed = bool(handler and handler(record, op)) or changed
    store_travel(entity_states, record)
    return changed


def block_reason(adventure: Any, sequence: Optional[dict[str, Any]], record: dict[str, Any]) -> str:
    """Why fast travel is off as a whole right now, or "" when it is allowed."""
    if getattr(adventure, "fast_travel_enabled", True) is False:
        return "Fast travel is not available in this adventure."
    if isinstance(sequence, dict) and sequence.get("fast_travel_allowed") is False:
        return "Fast travel is not possible in this chapter."
    if record.get("disabled"):
        return record.get("reason") or "Fast travel is not possible right now."
    return ""
