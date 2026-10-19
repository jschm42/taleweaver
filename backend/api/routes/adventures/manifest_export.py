"""Pure transforms applied when exporting a template's original manifest."""

from typing import Any, Optional

from backend.models.adventure_template import AdventureTemplate

_LEGACY_EQUIPMENT_SLOTS = (
    "Head",
    "Neck",
    "Chest",
    "Back",
    "Hands",
    "Waist",
    "Legs",
    "Feet",
    "MainHand",
    "OffHand",
    "Fingers",
    "Trinket",
)


def backfill_manifest_metadata(manifest: dict[str, Any], adventure: AdventureTemplate) -> None:
    """Fill top-level metadata that older manifests may lack (existing keys win)."""
    defaults = {
        "version": adventure.version or "1.0",
        "id": adventure.id,
        "title": adventure.title,
        "time_per_turn": adventure.time_per_turn,
        "generate_npc_images": adventure.generate_npc_images or False,
        "generate_item_images": adventure.generate_item_images or False,
        "automatic_cover_generation": False,
        "cover_source_adventure_id": adventure.cover_source_adventure_id,
        "cover_source_adventure_name": adventure.cover_source_adventure_name,
        "cover_similarity_percent": adventure.cover_similarity_percent,
        "allow_reuse_source_assets": adventure.allow_reuse_source_assets,
    }
    for key, value in defaults.items():
        manifest.setdefault(key, value)


def _register_object(objects: list[dict[str, Any]], obj_dict: Any) -> None:
    if not obj_dict or not obj_dict.get("id"):
        return
    obj_copy = dict(obj_dict)
    obj_copy.setdefault("entity_type", "OBJECT")
    if not any(o.get("id") == obj_copy["id"] for o in objects):
        objects.append(obj_copy)


def _as_item_ref(item: Any, objects: list[dict[str, Any]]) -> Any:
    """Inline item dicts become ID references (and are registered as objects)."""
    if not isinstance(item, dict):
        return item
    _register_object(objects, item)
    return item.get("id")


def _collect_equipment_refs(
    protagonist: dict[str, Any], objects: list[dict[str, Any]]
) -> dict[str, Any]:
    equipment = {
        slot: _as_item_ref(item, objects)
        for slot, item in (protagonist.get("starting_equipment") or {}).items()
    }
    # Legacy manifests stored equipped items as root-level protagonist slots.
    for slot in _LEGACY_EQUIPMENT_SLOTS:
        if slot in protagonist:
            equipment[slot] = _as_item_ref(protagonist.pop(slot), objects)
    return equipment


def _scene_item_ids(objects: list[dict[str, Any]]) -> set[Any]:
    ids = set()
    for obj in objects:
        scene_id = obj.get("current_scene_id") or obj.get("start_scene_id")
        if scene_id and scene_id != "INVENTORY":
            ids.add(obj.get("id"))
    return ids


def _dedupe_inventory(inventory: list[Any], in_scene: set[Any]) -> list[Any]:
    result: list[Any] = []
    for item_id in inventory:
        if item_id and item_id not in in_scene and item_id not in result:
            result.append(item_id)
    return result


def _dedupe_equipment(
    equipment: dict[str, Any], in_scene: set[Any], inventory: list[Any]
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for slot, item_id in equipment.items():
        taken = item_id in in_scene or item_id in inventory or item_id in result.values()
        if item_id and not taken:
            result[slot] = item_id
    return result


def normalize_protagonist_items(manifest: dict[str, Any]) -> None:
    """Turn inline protagonist items into ID references.

    Priority deduplication: an item placed in a scene beats inventory, which
    beats equipment.
    """
    protagonist = manifest.get("protagonist")
    if not isinstance(protagonist, dict):
        return
    objects = manifest.setdefault("objects", [])

    inventory = [_as_item_ref(item, objects) for item in protagonist.get("starting_inventory", [])]
    equipment = _collect_equipment_refs(protagonist, objects)

    in_scene = _scene_item_ids(objects)
    final_inventory = _dedupe_inventory(inventory, in_scene)
    final_equipment = _dedupe_equipment(equipment, in_scene, final_inventory)

    protagonist["starting_inventory"] = final_inventory
    if final_equipment:
        protagonist["starting_equipment"] = final_equipment
    else:
        protagonist.pop("starting_equipment", None)


def _with_start_scenes(
    items: Optional[list[dict[str, Any]]],
    entity_scene_map: dict[str, Any],
    valid_scene_ids: set[Any],
) -> Optional[list[dict[str, Any]]]:
    if not items:
        return items
    normalized: list[dict[str, Any]] = []
    for item in items:
        item_copy = dict(item)
        scene_id = entity_scene_map.get(item_copy.get("id"))
        if not item_copy.get("start_scene_id") and scene_id in valid_scene_ids:
            item_copy["start_scene_id"] = scene_id
        normalized.append(item_copy)
    return normalized


def backfill_item_start_scenes(manifest: dict[str, Any], entity_scene_map: dict[str, Any]) -> None:
    """Fill missing start_scene_id from world entities, only for scenes in the manifest."""
    valid_scene_ids = {
        s.get("id") for s in manifest.get("scenes", []) if isinstance(s, dict) and s.get("id")
    }
    for key in ("items", "objects"):
        updated = _with_start_scenes(manifest.get(key), entity_scene_map, valid_scene_ids)
        if updated is not None:
            manifest[key] = updated
        else:
            manifest.pop(key, None)


def serialize_exit(world_exit: Any) -> dict[str, Any]:
    exit_type = str(world_exit.exit_type or "one_way").strip().lower()
    return {
        "id": world_exit.id,
        "from_scene_id": world_exit.from_scene_id,
        "to_scene_id": world_exit.to_scene_id,
        "label": world_exit.label,
        "exit_type": exit_type,
        "is_bidirectional": str(world_exit.exit_type or "").strip().lower() == "bidirectional",
        "is_locked": world_exit.is_locked,
        "lock_description": world_exit.lock_description,
        "code_to_unlock": world_exit.code_to_unlock,
        "item_to_unlock": world_exit.item_to_unlock,
        "rule_to_unlock": world_exit.rule_to_unlock,
    }
