"""Consumable item usage during combat."""

from __future__ import annotations

import re
from typing import Any

from backend.engine.rule_engine import RESOURCE_CAP

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
_RESOURCE_LABELS = {"hp": "HP", "mana": "Mana", "stamina": "Stamina"}


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


class CombatConsumableMixin:
    """Finds and applies consumables from the protagonist's inventory."""

    @staticmethod
    def _description_delta(description: str, resource: str) -> int:
        resource_rx = _RESOURCE_ALIASES.get(resource)
        if not description or not resource_rx:
            return 0
        desc = description.lower()
        total = 0
        for match in re.finditer(rf"([+-]?\d+)\s*{resource_rx}", desc):
            ctx = desc[max(0, match.start() - 40) : min(len(desc), match.end() + 40)]
            total += _signed_magnitude(match.group(1), ctx)
        return total

    def _resource_delta_from_consumable(self, item: dict[str, Any], resource: str) -> int:
        keys = _RESOURCE_KEYS.get(resource, [])
        for source in (item, item.get("metadata_json")):
            value = _numeric_field(source, keys, resource)
            if value is not None:
                return value
        description = item.get("description")
        if isinstance(description, str):
            return self._description_delta(description, resource)
        return 0

    def _find_consumable(self, item_name: str) -> dict[str, Any] | None:
        for item in list(self.avatar.inventory or []):
            if (
                isinstance(item, dict)
                and item.get("name", "").lower() == item_name.lower()
                and item.get("item_type") == "CONSUMABLE"
            ):
                return item
        return None

    def _remove_consumable(self, item_name: str) -> None:
        new_inventory = []
        removed = False
        for inv_item in list(self.avatar.inventory or []):
            is_match = (
                isinstance(inv_item, dict)
                and inv_item.get("name", "").lower() == item_name.lower()
                and inv_item.get("item_type") == "CONSUMABLE"
            )
            if is_match and not removed:
                removed = True
                continue
            new_inventory.append(inv_item)
        self.avatar.inventory = new_inventory

    def _apply_consumable_deltas(self, item: dict[str, Any]) -> dict[str, int]:
        deltas: dict[str, int] = {}
        for resource in ("hp", "mana", "stamina"):
            delta = self._resource_delta_from_consumable(item, resource)
            if not delta:
                continue
            current = int(getattr(self.avatar, resource) or 0)
            cap = int(getattr(self.avatar, f"max_{resource}") or RESOURCE_CAP)
            new_value = max(0, min(cap, current + delta))
            setattr(self.avatar, resource, new_value)
            deltas[resource] = delta
        return deltas

    def _consume_item_now(self, item_name: str) -> str:
        item = self._find_consumable(item_name)
        if not item:
            return f"You do not have the consumable '{item_name}'."

        deltas = self._apply_consumable_deltas(item)
        self._remove_consumable(item_name)
        self._last_consumable_deltas = deltas

        gained = [f"+{v} {_RESOURCE_LABELS[k]}" for k, v in deltas.items() if v > 0]
        lost = [f"{v} {_RESOURCE_LABELS[k]}" for k, v in deltas.items() if v < 0]
        parts = [f"{self.avatar.name} uses {item.get('name', item_name)}."]
        if gained:
            parts.append(f"You gain: {', '.join(gained)}.")
        if lost:
            parts.append(f"You lose: {', '.join(lost)}.")
        return " ".join(parts)
