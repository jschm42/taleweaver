"""Reads the HP / Mana / Stamina effect of a consumable item.

Shared by the protagonist's ``/consume`` command and ``npc.consume()`` in scripts. A value comes
from a numeric field (``hp_change``, ``restore_mana``, ``effects.stamina``, ... on the item or its
``metadata_json``), else from the description ("restores 20 HP", "-5 stamina").
"""

from __future__ import annotations

import re
from typing import Any

RESOURCES = ("hp", "mana", "stamina")
RESOURCE_LABELS = {"hp": "HP", "mana": "Mana", "stamina": "Stamina"}

_RESOURCE_ALIASES = {
    "hp": r"(?:hp|health|lebenspunkte?)",
    "mana": r"(?:mana|magie|magiekraft)",
    "stamina": r"(?:stamina|ausdauer|energie)",
}
_POSITIVE_WORDS = (
    "stellt", "wieder her", "heilt", "regeneriert", "restores", "restore", "heals", "heal",
    "regains", "regain", "replenish", "replenishes", "recover", "recovers", "gain", "gains",
    "boost",
)  # fmt: skip
_NEGATIVE_WORDS = (
    "kostet", "verliert", "schaden", "schadet", "entzieht", "senkt", "reduziert", "damage",
    "damages", "lose", "loses", "losing", "drain", "drains", "reduces", "reduce", "consumes",
    "consume",
)  # fmt: skip
_RESOURCE_KEYS = {
    "hp": [
        "hp_change",
        "health_change",
        "heal",
        "heal_amount",
        "restore_hp",
        "restore_health",
        "hp_delta",
    ],
    "mana": ["mana_change", "restore_mana", "mana_restore", "mana_delta"],
    "stamina": ["stamina_change", "restore_stamina", "stamina_restore", "stamina_delta"],
}


def _signed_magnitude(raw: str, ctx: str) -> int:
    magnitude = abs(int(raw))
    if raw.startswith("-"):
        return -magnitude
    if raw.startswith("+"):
        return magnitude
    if any(word in ctx for word in _NEGATIVE_WORDS):
        return -magnitude
    if any(word in ctx for word in _POSITIVE_WORDS):
        return magnitude
    return 0


def _numeric_field(source: Any, keys: list[str], resource: str) -> int | None:
    if not isinstance(source, dict):
        return None
    for key in keys:
        val = source.get(key)
        if isinstance(val, (int, float)):
            return int(val)
    effects = source.get("effects")
    if isinstance(effects, dict) and isinstance(effects.get(resource), (int, float)):
        return int(effects[resource])
    return None


def description_delta(description: str, resource: str) -> int:
    """Signed sum of the amounts the description names for ``resource``."""
    resource_rx = _RESOURCE_ALIASES.get(resource)
    if not description or not resource_rx:
        return 0
    desc = description.lower()
    total = 0
    for match in re.finditer(rf"([+-]?\d+)\s*{resource_rx}", desc):
        ctx = desc[max(0, match.start() - 40) : min(len(desc), match.end() + 40)]
        total += _signed_magnitude(match.group(1), ctx)
    return total


def resource_delta(item: dict[str, Any], resource: str) -> int:
    """The item's effect on one resource; numeric fields win over the description."""
    keys = _RESOURCE_KEYS.get(resource, [])
    for source in (item, item.get("metadata_json")):
        value = _numeric_field(source, keys, resource)
        if value is not None:
            return value
    description = item.get("description")
    if isinstance(description, str):
        return description_delta(description, resource)
    return 0


def consumable_deltas(item: dict[str, Any]) -> dict[str, int]:
    """Non-zero effects of the item, e.g. ``{"hp": 20, "stamina": -5}``."""
    deltas = {resource: resource_delta(item, resource) for resource in RESOURCES}
    return {resource: delta for resource, delta in deltas.items() if delta}
