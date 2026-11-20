"""Respawn instead of game over: settings, revival HP and the session's revival record.

An adventure opts in with ``game_over_rules = {"on_zero_hp": "respawn", "respawn_hp_percent": 25}``.
Then a protagonist who falls to 0 HP is knocked out instead of dying: they wake up at the last
revival point they reached (else the start scene) with a share of their max HP. Deliberate
defeats (``tw.game.game_over()``, the defeat condition, a GM ``game_over``) stay final.

The session's revival record lives in ``entity_states["__respawn__"]`` (part of every checkpoint):
``{"point": <scene id or None>, "count": <respawns so far>}``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

RESPAWN_KEY = "__respawn__"
ON_ZERO_HP_KEY = "on_zero_hp"
HP_PERCENT_KEY = "respawn_hp_percent"
DEFEAT_MODES = ("game_over", "respawn")
DEFAULT_HP_PERCENT = 25


@dataclass(frozen=True)
class RespawnSettings:
    """How an adventure treats a protagonist at 0 HP."""

    enabled: bool = False
    hp_percent: int = DEFAULT_HP_PERCENT


def clamp_hp_percent(value: Any) -> int:
    """A revival HP share in percent (1-100); invalid values fall back to the default."""
    try:
        percent = int(round(float(str(value).strip().rstrip("%"))))
    except (TypeError, ValueError):
        return DEFAULT_HP_PERCENT
    return max(1, min(100, percent))


def normalize_game_over_rules(rules: Any) -> Optional[dict[str, Any]]:
    """The stored shape of ``game_over_rules``; None when it holds nothing."""
    if not isinstance(rules, dict) or not rules:
        return None
    result = dict(rules)
    mode = str(result.get(ON_ZERO_HP_KEY) or "game_over").strip().lower()
    result[ON_ZERO_HP_KEY] = mode if mode in DEFEAT_MODES else "game_over"
    if HP_PERCENT_KEY in result:
        result[HP_PERCENT_KEY] = clamp_hp_percent(result[HP_PERCENT_KEY])
    return result


def respawn_settings(rules: Any) -> RespawnSettings:
    """Reads the respawn settings from an adventure's ``game_over_rules``."""
    normalized = normalize_game_over_rules(rules)
    if not normalized or normalized[ON_ZERO_HP_KEY] != "respawn":
        return RespawnSettings()
    return RespawnSettings(
        True, clamp_hp_percent(normalized.get(HP_PERCENT_KEY, DEFAULT_HP_PERCENT))
    )


def revival_hp(max_hp: Any, percent: int) -> int:
    """HP after a respawn: the share of max HP, at least 1."""
    try:
        cap = int(max_hp or 0)
    except (TypeError, ValueError):
        cap = 0
    return max(1, round(max(cap, 1) * percent / 100))


def read_respawn(entity_states: Any) -> dict[str, Any]:
    """The session's revival record (``point`` may be None: then the start scene is used)."""
    raw = (entity_states or {}).get(RESPAWN_KEY) if isinstance(entity_states, dict) else None
    record = dict(raw) if isinstance(raw, dict) else {}
    point = record.get("point")
    count = record.get("count")
    return {
        "point": point if isinstance(point, str) and point else None,
        "count": count if isinstance(count, int) and count > 0 else 0,
    }


def store_respawn(entity_states: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    """Returns a copy of ``entity_states`` holding ``record`` as the revival record."""
    states = dict(entity_states or {})
    states[RESPAWN_KEY] = {"point": record.get("point"), "count": int(record.get("count") or 0)}
    return states


def apply_respawn_point(entity_states: dict[str, Any], scene_id: Optional[str]) -> None:
    """Replays ``tw.game.set_respawn_point`` in place; None = no change, "" = back to start."""
    if scene_id is None:
        return
    record = read_respawn(entity_states)
    record["point"] = scene_id.strip().upper() or None
    entity_states[RESPAWN_KEY] = store_respawn(entity_states, record)[RESPAWN_KEY]
