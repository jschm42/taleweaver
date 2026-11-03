"""Helpers for handing existing world items between script proxies (e.g. NPC -> protagonist).

Items never appear out of thin air: a transfer only succeeds when the giver actually holds
the item, and the protagonist receives the item's world entity data, not an invented stub.
"""

from __future__ import annotations

from typing import Any, Optional

# Entity fields copied into the protagonist's inventory entry (JSON-safe, session-agnostic).
_INVENTORY_ENTRY_KEYS = ("id", "name", "description", "item_type", "image_url", "metadata_json")


def ref_id(entry: Any) -> str:
    """Upper-cased item ID of an inventory entry (a dict with ``id`` or a bare ID string)."""
    raw = entry.get("id") if isinstance(entry, dict) else entry
    return str(raw or "").strip().upper()


def take_from_inventory(inventory: list[Any], item_id: str) -> tuple[Optional[Any], list[Any]]:
    """Splits the first entry matching ``item_id`` off ``inventory``: (taken, remaining)."""
    target = str(item_id).strip().upper()
    for index, entry in enumerate(inventory):
        if ref_id(entry) == target:
            return entry, [*inventory[:index], *inventory[index + 1 :]]
    return None, list(inventory)


def inventory_entry(inventory_ref: Any, entity_data: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Builds the protagonist's inventory entry, preferring the item's world entity data."""
    ref = dict(inventory_ref) if isinstance(inventory_ref, dict) else {"id": str(inventory_ref)}
    source = {**ref, **(entity_data or {})}
    entry = {key: source[key] for key in _INVENTORY_ENTRY_KEYS if source.get(key) is not None}
    entry.setdefault("name", str(entry["id"]).replace("_", " ").title())
    return entry
