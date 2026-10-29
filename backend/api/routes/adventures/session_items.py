"""Repairs avatar inventory/equipment items from the template's item entities.

Legacy imports stored items as bare IDs or as dicts missing stat/effect fields; these
helpers expand and backfill them from the matching ``WorldEntity`` rows.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any, Optional

from backend.engine.rules.item_logic import get_item_slot, normalize_equipment_keys
from backend.models.avatar import Avatar
from backend.models.world_entity import WorldEntity

_TEXT_LOG_FORMATS = {"DOCUMENT", "SCROLL", "BOOK", "SIGN"}
_TEXT_LOG_MAX_LENGTH = 1000

# Item field -> candidate sources, tried in order (entity, metadata and its "effects").
_NumericSource = Callable[[WorldEntity, dict[str, Any], dict[str, Any]], tuple[Any, ...]]
_NUMERIC_FIELDS: dict[str, _NumericSource] = {
    "stat_modifier_strength": lambda e, m, _: (
        e.stat_modifier_strength,
        m.get("stat_modifier_strength"),
    ),
    "stat_modifier_dexterity": lambda e, m, _: (
        e.stat_modifier_dexterity,
        m.get("stat_modifier_dexterity"),
        m.get("stat_modifier_agility"),
    ),
    "stat_modifier_intelligence": lambda e, m, _: (
        e.stat_modifier_intelligence,
        m.get("stat_modifier_intelligence"),
    ),
    "stat_modifier_wisdom": lambda e, m, _: (e.stat_modifier_wisdom, m.get("stat_modifier_wisdom")),
    "stat_modifier_charisma": lambda e, m, _: (
        e.stat_modifier_charisma,
        m.get("stat_modifier_charisma"),
    ),
    "stat_modifier_armor_class": lambda e, m, _: (
        e.stat_modifier_armor_class,
        m.get("stat_modifier_armor_class"),
    ),
    "hp_change": lambda _, m, fx: (
        m.get("hp_change"),
        m.get("health_change"),
        fx.get("hp"),
        fx.get("health"),
    ),
    "stamina_change": lambda _, m, fx: (
        m.get("stamina_change"),
        fx.get("stamina"),
        fx.get("energy"),
    ),
    "mana_change": lambda _, m, fx: (m.get("mana_change"), fx.get("mana")),
}


def _to_int_or_none(value: Any) -> Optional[int]:
    if isinstance(value, (int, float)):
        return int(value)
    return None


def _first_int(candidates: tuple[Any, ...]) -> Optional[int]:
    return next((v for v in map(_to_int_or_none, candidates) if v is not None), None)


def _effects(metadata: dict[str, Any]) -> dict[str, Any]:
    effects = metadata.get("effects")
    return effects if isinstance(effects, dict) else {}


def _numeric_values(entity: WorldEntity, metadata: dict[str, Any]) -> dict[str, Optional[int]]:
    effects = _effects(metadata)
    return {
        field: _first_int(sources(entity, metadata, effects))
        for field, sources in _NUMERIC_FIELDS.items()
    }


def _text_log(metadata: dict[str, Any]) -> tuple[str, str]:
    content = str(metadata.get("text_log_content") or "").strip()[:_TEXT_LOG_MAX_LENGTH]
    log_format = str(metadata.get("text_log_format") or "DOCUMENT").strip().upper()
    return content, log_format if log_format in _TEXT_LOG_FORMATS else "DOCUMENT"


def _merged_metadata(item: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    """Item metadata keeps its own values; missing keys come from the entity."""
    existing = item.get("metadata_json")
    if not isinstance(existing, dict):
        return dict(metadata)
    merged = dict(existing)
    for key, value in metadata.items():
        merged.setdefault(key, value)
    return merged


def backfill_item_from_entity(item: dict, entity: WorldEntity) -> dict:
    merged = dict(item)
    metadata = entity.metadata_json or {}
    item_type = str(entity.item_type or merged.get("item_type") or "").upper()

    # Preserve metadata for item-specific frontend behavior (e.g. READABLE text logs, container locks).
    merged["metadata_json"] = _merged_metadata(merged, metadata)
    for field, value in _numeric_values(entity, metadata).items():
        if merged.get(field) is None and value is not None:
            merged[field] = value

    if item_type == "READABLE":
        content, log_format = _text_log(metadata)
        merged["text_log_content"] = merged.get("text_log_content") or content
        merged["text_log_format"] = merged.get("text_log_format") or log_format
    return merged


def _item_slot(entity: WorldEntity) -> Any:
    slots = entity.wearable_slots
    if isinstance(slots, list) and slots:
        return slots[0]
    if isinstance(slots, str):
        return slots
    return get_item_slot(entity.name, entity.item_type or "PICKABLE")


def reconstruct_item_dict_from_entity(entity: WorldEntity) -> dict:
    metadata = entity.metadata_json or {}
    item_type = entity.item_type or "PICKABLE"
    is_readable = str(item_type).upper() == "READABLE"
    text_log_content, text_log_format = _text_log(metadata)
    return {
        "id": entity.id,
        "name": entity.name,
        "description": entity.description,
        "image_url": entity.image_url,
        "item_type": item_type,
        "slot": _item_slot(entity),
        "metadata_json": dict(metadata),
        "text_log_content": text_log_content if is_readable else "",
        "text_log_format": text_log_format if is_readable else "",
        **_numeric_values(entity, metadata),
    }


def _backfilled(item: Any, entities_by_id: dict[str, WorldEntity]) -> Any:
    if isinstance(item, str) and item in entities_by_id:
        return reconstruct_item_dict_from_entity(entities_by_id[item])
    if isinstance(item, dict) and item.get("id") in entities_by_id:
        return backfill_item_from_entity(item, entities_by_id[item["id"]])
    return item


def backfill_avatar_items_from_template_entities(
    avatar: Avatar, entities_by_id: dict[str, WorldEntity]
) -> None:
    avatar.inventory = [_backfilled(item, entities_by_id) for item in (avatar.inventory or [])]
    avatar.equipment = {
        slot: _backfilled(item, entities_by_id)
        for slot, item in normalize_equipment_keys(avatar.equipment).items()
    }


def iter_avatar_items(avatar: Avatar) -> Iterator[tuple[str, dict]]:
    for index, item in enumerate(avatar.inventory or []):
        if isinstance(item, dict):
            yield (f"inventory[{index}]", item)

    for slot, item in (avatar.equipment or {}).items():
        if isinstance(item, dict):
            yield (f"equipment.{slot}", item)
