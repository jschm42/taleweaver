"""Consumable item usage during combat."""

from __future__ import annotations

from typing import Any

from backend.engine.rules.consumable_effects import (
    RESOURCE_LABELS,
    RESOURCES,
    description_delta,
    resource_delta,
)
from backend.engine.rules.rule_engine import RESOURCE_CAP


class CombatConsumableMixin:
    """Finds and applies consumables from the protagonist's inventory."""

    @staticmethod
    def _description_delta(description: str, resource: str) -> int:
        return description_delta(description, resource)

    def _resource_delta_from_consumable(self, item: dict[str, Any], resource: str) -> int:
        return resource_delta(item, resource)

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
        for resource in RESOURCES:
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

        gained = [f"+{v} {RESOURCE_LABELS[k]}" for k, v in deltas.items() if v > 0]
        lost = [f"{v} {RESOURCE_LABELS[k]}" for k, v in deltas.items() if v < 0]
        parts = [f"{self.avatar.name} uses {item.get('name', item_name)}."]
        if gained:
            parts.append(f"You gain: {', '.join(gained)}.")
        if lost:
            parts.append(f"You lose: {', '.join(lost)}.")
        return " ".join(parts)
