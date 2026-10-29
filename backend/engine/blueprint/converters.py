"""Converters that turn raw blueprint values into manifest field values.

Every converter raises ``ValueError`` with a user-facing message on bad input.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from backend.engine.interaction.switch_states import (
    STATE_ID_MAX,
    STATE_LABEL_MAX,
    is_valid_state_id,
)

_TRUE_WORDS = {"yes", "true", "on", "1", "y"}
_FALSE_WORDS = {"no", "false", "off", "0", "n"}
STAT_ALIASES = {
    "str": "strength",
    "strength": "strength",
    "dex": "dexterity",
    "dexterity": "dexterity",
    "int": "intelligence",
    "intelligence": "intelligence",
    "wis": "wisdom",
    "wisdom": "wisdom",
    "cha": "charisma",
    "charisma": "charisma",
    "ac": "armor_class",
    "armor_class": "armor_class",
}


def normalize_id(raw: str) -> str:
    """Turn ``@Old Man`` / ``old-man`` / ``##OLD_MAN##`` into ``OLD_MAN``."""
    clean = raw.replace("##", "").strip().strip("\"'").lstrip("@")
    clean = re.sub(r"[^A-Za-z0-9]+", "_", clean).strip("_")
    return clean.upper()


def text(raw: str) -> str:
    return raw.strip()


def integer(raw: str) -> int:
    try:
        return int(raw.strip().lstrip("+"))
    except ValueError as exc:
        raise ValueError(f"expected a whole number, got '{raw.strip()}'") from exc


def boolean(raw: str) -> bool:
    word = raw.strip().lower()
    if word in _TRUE_WORDS:
        return True
    if word in _FALSE_WORDS:
        return False
    raise ValueError(f"expected yes/no, got '{raw.strip()}'")


def ident(raw: str) -> str:
    return normalize_id(raw)


def ident_list(raw: str) -> list[str]:
    return [normalize_id(part) for part in re.split(r"[,+]", raw) if normalize_id(part)]


def switch_states(raw: str) -> dict[str, Any]:
    """``OFF=Dark, HALF-OPEN, ON=Lights on`` -> state IDs plus labels (only when given)."""
    states: list[str] = []
    labels: dict[str, str] = {}
    for part in text_list(raw):
        state_raw, _, label = part.partition("=")
        state = state_raw.strip().upper().replace(" ", "_")
        if not is_valid_state_id(state):
            raise ValueError(
                f"state ID '{state_raw.strip()}' must be 1-{STATE_ID_MAX} characters "
                "(letters, digits, '_' or '-')"
            )
        if len(label.strip()) > STATE_LABEL_MAX:
            raise ValueError(
                f"label of state '{state}' is longer than {STATE_LABEL_MAX} characters"
            )
        states.append(state)
        if label.strip():
            labels[state] = label.strip()
    result: dict[str, Any] = {"switch_states": states}
    if labels:
        result["switch_state_labels"] = labels
    return result


def text_list(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def choice(*allowed: str, aliases: dict[str, str] | None = None) -> Callable[[str], str]:
    lookup = {value.lower(): value for value in allowed}
    lookup.update({key.lower(): value for key, value in (aliases or {}).items()})

    def convert(raw: str) -> str:
        key = raw.strip().lower().replace(" ", "_")
        if key not in lookup:
            raise ValueError(f"expected one of {', '.join(allowed)}, got '{raw.strip()}'")
        return lookup[key]

    return convert


def stat_bonus(raw: str) -> dict[str, int]:
    """``str+2, ac-1`` -> ``{"stat_modifier_strength": 2, "stat_modifier_armor_class": -1}``."""
    result: dict[str, int] = {}
    for part in text_list(raw):
        match = re.fullmatch(r"([a-z_]+)\s*([+-]\s*\d+)", part.lower())
        if not match or match.group(1) not in STAT_ALIASES:
            raise ValueError(f"expected bonuses like 'str+2, ac+1', got '{part}'")
        stat = STAT_ALIASES[match.group(1)]
        result[f"stat_modifier_{stat}"] = int(match.group(2).replace(" ", ""))
    return result


def _resource_cost(raw: str) -> tuple[str, int]:
    match = re.fullmatch(r"(mana|stamina)\s+(\d+)", raw.strip().lower())
    if not match:
        raise ValueError(f"expected a cost like 'mana 10' or 'stamina 3', got '{raw.strip()}'")
    return match.group(1), int(match.group(2))


def weapon_cost(raw: str) -> dict[str, Any]:
    kind, amount = _resource_cost(raw)
    return {"weapon_cost_type": kind, "weapon_cost_value": amount}


_EFFECT_RX = re.compile(r"(target|self)\s+([a-z_]+)\s+([+-]?\s*\d+(?:d\d+(?:[+-]\d+)?)?)")
_EFFECT_STATS = {"hp", "mana", "stamina", "mp", "sta"}
_EFFECT_STAT_ALIASES = {"mp": "mana", "sta": "stamina"}


def _effect_stat(raw: str) -> str:
    key = raw.strip().lower()
    stat = _EFFECT_STAT_ALIASES.get(key) or STAT_ALIASES.get(key) or key
    if stat not in {*_EFFECT_STATS, *STAT_ALIASES.values()}:
        raise ValueError(f"unknown stat '{raw.strip()}'")
    return stat


def weapon_effects(raw: str) -> list[dict[str, str]]:
    """``target stamina -1d4, self hp +2`` -> weapon on-hit effects."""
    effects = []
    for part in (p.strip() for p in raw.split(",")):
        match = _EFFECT_RX.fullmatch(part.lower())
        if not match:
            raise ValueError(
                f"expected effects like 'target stamina -1d4, self hp +2', got '{part}'"
            )
        target, stat, amount = match.groups()
        effects.append(
            {"target": target, "stat": _effect_stat(stat), "amount": amount.replace(" ", "")}
        )
    return effects


def ability_cost(raw: str) -> dict[str, Any]:
    kind, amount = _resource_cost(raw)
    return {"cost_type": kind, "cost": amount}


def ability_damage(raw: str) -> dict[str, Any]:
    value = raw.strip()
    return {"damage_value": value, "damage_type": "ROLLED" if "d" in value.lower() else "FIXED"}


_AREA_SCOPES = {"single": "SINGLE", "splash": "SPLASH", "all": "ALL_ENEMIES"}
MAX_SPLASH_RADIUS = 2


def ability_area(raw: str) -> dict[str, Any]:
    """``single`` / ``splash`` / ``splash 2`` / ``all`` -> target_scope (+ splash_radius)."""
    parts = raw.strip().lower().split()
    scope = _AREA_SCOPES.get(parts[0]) if parts else None
    if not scope or len(parts) > 2:
        raise ValueError(f"expected single, splash [1-2] or all, got '{raw.strip()}'")
    result: dict[str, Any] = {"target_scope": scope}
    if len(parts) == 1:
        return result
    radius = integer(parts[1])
    if scope != "SPLASH" or not 1 <= radius <= MAX_SPLASH_RADIUS:
        raise ValueError(
            f"only splash takes a radius of 1-{MAX_SPLASH_RADIUS}, got '{raw.strip()}'"
        )
    result["splash_radius"] = radius
    return result


def movement(raw: str) -> dict[str, Any]:
    moves = boolean(raw)
    return {"moveable": moves, "movement_type": "MOVABLE" if moves else "STATIONARY"}


def one_way(raw: str) -> bool:
    return not boolean(raw)


_GATE_KEYS = {
    "item": "item",
    "code": "code",
    "rule": "rule",
    "guard": "expression",
}
_MESSAGE_KEYS = {"fail": "fail_message", "success": "success_message"}


def switch_transition(raw: str) -> dict[str, Any]:
    """``OFF -> ON | item: FUSE | guard: tw.flags.get('X') | fail: It sparks.``"""
    head, *options = [part.strip() for part in raw.split("|")]
    match = re.fullmatch(r"([^->]*)->\s*(.+)", head)
    if not match:
        raise ValueError(f"expected 'FROM -> TO', got '{head}'")
    from_state = match.group(1).strip().upper()
    transition: dict[str, Any] = {
        "from": "" if from_state in ("", "*", "ANY") else from_state,
        "to": match.group(2).strip().upper(),
        "fail_message": "",
    }
    gates: dict[str, str] = {}
    for option in options:
        key, _, value = option.partition(":")
        key = key.strip().lower()
        if key in _GATE_KEYS:
            gates[_GATE_KEYS[key]] = normalize_id(value) if key == "item" else value.strip()
        elif key in _MESSAGE_KEYS:
            transition[_MESSAGE_KEYS[key]] = value.strip()
        else:
            raise ValueError(f"unknown transition option '{key}'")
    if gates:
        transition["gates"] = {"item": "", "code": "", "rule": "", "expression": "", **gates}
    return transition


_EFFECT_TYPES = {"flag": "story_flag", "unlock_container": "unlock_container"}


def switch_outcome(raw: str) -> dict[str, Any]:
    """``ON -> flag: POWER_ON; unlock_container: FUSE_BOX``."""
    state, arrow, rest = raw.partition("->")
    if not arrow or not state.strip():
        raise ValueError(f"expected 'STATE -> flag: KEY', got '{raw.strip()}'")
    effects: list[dict[str, str]] = []
    for part in [p.strip() for p in rest.split(";") if p.strip()]:
        key, _, value = part.partition(":")
        effect_type = _EFFECT_TYPES.get(key.strip().lower())
        if not effect_type:
            raise ValueError(
                f"unknown outcome effect '{key.strip()}' (use flag or unlock_container; "
                "unlock exits with a script calling tw.exits.unlock)"
            )
        slot = "key" if effect_type == "story_flag" else "target_id"
        effects.append({"type": effect_type, "target_id": "", "key": "", slot: value.strip()})
    return {"on_state": state.strip().upper(), "effects": effects}
