"""World object (item) persistence, item images and type-specific metadata."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Optional

from backend.core.config import settings
from backend.engine.image_prompt_context import build_object_image_prompt, clean_appearance
from backend.engine.manifest_apply.assets import find_duplicate_image_url, needs_image
from backend.engine.manifest_apply.avatar import StartingItems
from backend.engine.manifest_apply.context import ApplyContext, generator_module
from backend.engine.manifest_apply.visuals import (
    generate_image,
    pick_existing_image,
    placeholder_image,
    t2i_config,
    uses_advanced_model,
)
from backend.engine.switch_states import normalize_state_id, normalize_state_labels
from backend.models.world_entity import WorldEntity
from backend.utils.text_utils import slugify

# Item numbers: output key -> manifest keys checked in order.
STAT_KEYS: dict[str, tuple[str, ...]] = {
    "stat_modifier_strength": ("stat_modifier_strength", "strength"),
    "stat_modifier_dexterity": (
        "stat_modifier_dexterity",
        "stat_modifier_agility",
        "dexterity",
        "agility",
    ),
    "stat_modifier_intelligence": ("stat_modifier_intelligence", "intelligence"),
    "stat_modifier_wisdom": ("stat_modifier_wisdom", "wisdom"),
    "stat_modifier_charisma": ("stat_modifier_charisma", "charisma"),
    "stat_modifier_armor_class": ("stat_modifier_armor_class", "armor_class", "ac"),
}
EFFECT_KEYS: dict[str, tuple[str, ...]] = {
    "hp_change": (
        "hp_change",
        "health_change",
        "heal",
        "heal_amount",
        "restore_hp",
        "restore_health",
        "hp",
    ),
    "stamina_change": ("stamina_change", "restore_stamina", "stamina_restore", "stamina", "energy"),
    "mana_change": ("mana_change", "restore_mana", "mana_restore", "mana"),
}
_BASE_SCRIPT_FIELDS = (
    "on_pickup_script", "on_pickup_text", "on_drop_script", "on_drop_text",
    "on_equip_script", "on_equip_text", "on_unequip_script", "on_unequip_text",
    "on_interact_script", "on_interact_text",
)  # fmt: skip
_CONTAINER_SCRIPT_FIELDS = (
    "on_unlock_success_script", "on_unlock_success_text", "on_unlock_failure_script", "on_unlock_failure_text",
)  # fmt: skip
_CONSTRUCTABLE_FIELDS = (
    "result_item_ids", "kept_ingredients",
    "craft_guard_expression", "on_craft_success_script", "on_craft_success_text",
    "on_craft_failure_script", "on_craft_failure_text",
)  # fmt: skip
_TEXT_LOG_FORMATS = {"DOCUMENT", "SCROLL", "BOOK", "SIGN"}


@dataclass
class ObjectPlacement:
    """Where objects start: protagonist inventory/equipment, NPC inventories or a scene."""

    starting: StartingItems = field(default_factory=StartingItems)
    npc_item_ids: set[str] = field(default_factory=set)
    avatar: Any = None


def _dict_at(source: dict[str, Any], key: str) -> dict[str, Any]:
    value = source.get(key)
    return value if isinstance(value, dict) else {}


def first_number(sources: list[dict[str, Any]], keys: tuple[str, ...]) -> Optional[int]:
    for source in sources:
        for key in keys:
            value = source.get(key)
            if isinstance(value, (int, float)):
                return int(value)
    return None


def item_numbers(obj: dict[str, Any], source_item: dict[str, Any]) -> dict[str, Optional[int]]:
    """Stat modifiers and consumable effects, wherever the manifest put them."""
    metadata = _dict_at(obj, "metadata_json")
    stat_sources = [obj, source_item, metadata, _dict_at(metadata, "stat_modifiers")]
    effect_sources = [
        obj,
        source_item,
        metadata,
        _dict_at(metadata, "effects"),
        _dict_at(source_item, "effects"),
    ]
    numbers = {key: first_number(stat_sources, keys) for key, keys in STAT_KEYS.items()}
    numbers.update({key: first_number(effect_sources, keys) for key, keys in EFFECT_KEYS.items()})
    return numbers


def _merge_fields(obj: dict[str, Any], metadata: dict[str, Any], keys: tuple[str, ...]) -> None:
    for key in keys:
        metadata[key] = obj.get(key) or metadata.get(key) or None


def _weapon_metadata(obj: dict[str, Any], metadata: dict[str, Any]) -> None:
    metadata["damage_dice"] = obj.get("damage_dice") or "1d8"
    metadata["weapon_cost_type"] = obj.get("weapon_cost_type") or "stamina"
    cost = obj.get("weapon_cost_value")
    metadata["weapon_cost_value"] = cost if cost is not None else 20


def _readable_metadata(obj: dict[str, Any], metadata: dict[str, Any]) -> None:
    normalize = generator_module()._normalize_text_log_content
    metadata["text_log_content"] = normalize(
        obj.get("text_log_content") or metadata.get("text_log_content"),
        obj.get("description"),
        obj.get("name"),
    )
    text_format = (
        str(obj.get("text_log_format") or metadata.get("text_log_format") or "DOCUMENT")
        .strip()
        .upper()
    )
    metadata["text_log_format"] = text_format if text_format in _TEXT_LOG_FORMATS else "DOCUMENT"
    _merge_fields(obj, metadata, ("on_read_script", "on_read_text"))


def _container_metadata(obj: dict[str, Any], metadata: dict[str, Any]) -> None:
    code, item, rule = generator_module()._normalize_unlock_requirements(
        obj.get("code_to_unlock"), obj.get("item_to_unlock"), obj.get("rule_to_unlock")
    )
    expression = obj.get("unlock_expression") or metadata.get("unlock_expression") or None
    metadata.update(
        code_to_unlock=code,
        item_to_unlock=item,
        rule_to_unlock=rule,
        unlock_expression=expression,
        locked=bool(code or item or rule or expression),
    )
    _merge_fields(obj, metadata, _CONTAINER_SCRIPT_FIELDS)


def _constructable_metadata(obj: dict[str, Any], metadata: dict[str, Any]) -> None:
    _merge_fields(obj, metadata, _CONSTRUCTABLE_FIELDS)


def recipe_metadata(obj: dict[str, Any]) -> dict[str, Any]:
    """Results, kept ingredients, guard and hooks of a CONSTRUCTABLE recipe definition."""
    metadata = dict(_dict_at(obj, "metadata_json"))
    _constructable_metadata(obj, metadata)
    return metadata


def normalize_switch_states(raw_states: Any) -> list[str]:
    states: list[str] = []
    for state in raw_states or []:
        token = normalize_state_id(state)
        if token and token not in states:
            states.append(token)
    return states if len(states) >= 2 else ["OFF", "ON"]


def _list_or_empty(value: Any) -> list:
    return value if isinstance(value, list) else []


def _switch_metadata(obj: dict[str, Any], metadata: dict[str, Any]) -> None:
    states = normalize_switch_states(obj.get("switch_states"))
    initial = normalize_state_id(obj.get("switch_initial_state") or states[0])
    scripts = {
        key: str(obj.get(key) or metadata.get(key) or "").strip()
        for key in ("on_success_script", "on_failure_script")
    }
    metadata["switch"] = {
        "states": states,
        "state_labels": normalize_state_labels(states, obj.get("switch_state_labels")),
        "initial_state": initial if initial in states else states[0],
        "transitions": _list_or_empty(obj.get("switch_transitions")),
        "outcomes": _list_or_empty(obj.get("switch_outcomes")),
        **scripts,
    }
    metadata.update({key: value for key, value in scripts.items() if value})
    metadata.setdefault(
        "discovery_visibility",
        {"mentioned_in_scene": True, "listed_in_discoveries": False, "lootable": False},
    )


_TYPE_METADATA: dict[str, Callable[[dict[str, Any], dict[str, Any]], None]] = {
    "WEAPON": _weapon_metadata,
    "READABLE": _readable_metadata,
    "CONTAINER": _container_metadata,
    "CONSTRUCTABLE": _constructable_metadata,
    "SWITCH": _switch_metadata,
}


def object_metadata(obj: dict[str, Any], numbers: dict[str, Optional[int]]) -> dict[str, Any]:
    metadata = dict(obj.get("metadata_json") or {})
    _merge_fields(obj, metadata, _BASE_SCRIPT_FIELDS)
    for key in EFFECT_KEYS:
        if numbers[key] is not None:
            metadata[key] = numbers[key]
    handler = _TYPE_METADATA.get(str(obj.get("item_type") or "").upper())
    if handler:
        handler(obj, metadata)
    return metadata


def _item_slot(obj: dict[str, Any]) -> Optional[str]:
    from backend.engine.item_logic import get_item_slot

    slots = obj.get("wearable_slots")
    return slots[0] if slots else get_item_slot(obj["name"], obj.get("item_type", "PICKABLE"))


def resolved_item(
    obj: dict[str, Any], image_url: Optional[str], numbers: dict[str, Optional[int]]
) -> dict[str, Any]:
    """The item snapshot stored in NPC inventories."""
    return {
        "id": obj["id"],
        "name": obj["name"],
        "description": obj["description"],
        "image_url": image_url,
        "item_type": obj.get("item_type", "PICKABLE"),
        "slot": _item_slot(obj),
        "text_log_content": generator_module()._normalize_text_log_content(
            obj.get("text_log_content"), obj.get("description"), obj.get("name")
        ),
        "text_log_format": str(obj.get("text_log_format") or "").strip().upper() or None,
        **numbers,
    }


async def _generate_item_image(
    ctx: ApplyContext, obj: dict[str, Any], idx: int, total: int
) -> Optional[str]:
    from backend.engine.media_engine import MediaEngine

    prompt = build_object_image_prompt(obj["name"], obj["description"], obj.get("appearance"))
    user_config, api_keys = t2i_config(ctx)
    return await generate_image(
        ctx,
        status=f"Reifying Artifact {idx}/{total}: {obj['name']}...",
        prompt=prompt,
        factory=lambda: MediaEngine.generate_entity_image(
            prompt,
            ctx.template_id,
            obj["id"],
            "OBJECT",
            user_config,
            api_keys,
            style_instruction=ctx.style_instruction,
            use_advanced_model=uses_advanced_model(ctx, "asset_model_quality", "simple"),
        ),  # fmt: skip
        timeout=float(settings.VISUAL_TIMEOUT),
        failure_label=f"Object image generation for {ctx.template_id}/{obj['id']}",
    )


async def _object_image(
    ctx: ApplyContext,
    obj: dict[str, Any],
    processed: list[dict],
    cache: dict[str, str],
    position: tuple[int, int],
) -> Optional[str]:
    image_url = await pick_existing_image(
        ctx,
        kind="object",
        label=f"Item: {obj.get('name')}",
        source_asset_id=obj.get("source_asset_id"),
        before=[
            find_duplicate_image_url(obj, processed, cache),
            ctx.existing_images.get(obj["id"]),
        ],
        after=[obj.get("image_url")],
    )
    if not needs_image(image_url):
        return image_url
    # Recipes never appear in the world, so they get the placeholder instead of an image.
    if ctx.user and ctx.gen_items and not _is_recipe_def(obj):
        image_url = await _generate_item_image(ctx, obj, *position)
    if not needs_image(image_url):
        return image_url
    item_type = str(obj.get("item_type") or "PICKABLE").upper()
    safe_id = slugify(str(obj.get("id") or "")) or "entity"
    return await placeholder_image(ctx, safe_id, category=f"ITEM_{item_type}", subdir="entities")


def _is_recipe_def(obj: dict[str, Any]) -> bool:
    return str(obj.get("item_type") or "").upper() == "CONSTRUCTABLE"


def recipe_result_ids(objects: list[dict[str, Any]]) -> set[str]:
    """Ids of all items produced by a CONSTRUCTABLE recipe; they start hidden."""
    results: set[str] = set()
    for obj in objects:
        if not _is_recipe_def(obj):
            continue
        metadata = _dict_at(obj, "metadata_json")
        raw = obj.get("result_item_ids") or metadata.get("result_item_ids") or []
        results.update(str(r).strip() for r in raw if str(r or "").strip())
    return results


def starts_hidden(obj: dict[str, Any], result_ids: set[str]) -> bool:
    """Recipes and recipe results are always hidden; everything else follows ``is_hidden``."""
    if _is_recipe_def(obj) or str(obj.get("id") or "") in result_ids:
        return True
    return bool(obj.get("is_hidden", False))


def _give_to_avatar(placement: ObjectPlacement, item_id: str) -> None:
    avatar = placement.avatar
    if not avatar:
        return
    if item_id in placement.starting.inventory_ids:
        avatar.inventory = [*list(avatar.inventory), item_id]
    slot = placement.starting.equipped_ids.get(item_id)
    if slot:
        avatar.equipment = {**dict(avatar.equipment), slot: item_id}


def _object_entity(
    ctx: ApplyContext,
    obj: dict[str, Any],
    image_url: Optional[str],
    numbers: dict[str, Optional[int]],
    held: bool,
    default_scene_id: str,
    hidden: bool,
) -> WorldEntity:
    return WorldEntity(
        id=obj["id"],
        template_id=ctx.template_id,
        entity_type="OBJECT",
        name=obj["name"],
        description=obj["description"],
        appearance=clean_appearance(obj.get("appearance")),
        current_scene_id="INVENTORY"
        if held
        else (obj.get("start_scene_id") or obj.get("current_scene_id") or default_scene_id),
        spatial_position=obj.get("spatial_position"),
        image_url=image_url,
        item_type=obj.get("item_type", "PICKABLE"),
        wearable_slots=obj.get("wearable_slots"),
        is_hidden=hidden,
        reveal_rule=obj.get("reveal_rule") or None,
        unlock_rule=None,
        is_in_inventory=held,
        is_portable=obj.get("is_portable", obj.get("item_type") != "STATIC"),
        combination_ingredients=obj.get("combination_ingredients"),
        reveals_item_id=obj.get("reveals_item_id"),
        inventory=obj.get("inventory") or [],
        state_comment=obj.get("state_comment"),
        metadata_json=object_metadata(obj, numbers),
        **{key: numbers[key] for key in STAT_KEYS},
    )


async def persist_objects(
    ctx: ApplyContext,
    objects: list[dict[str, Any]],
    default_scene_id: str,
    placement: ObjectPlacement,
) -> dict[str, dict[str, Any]]:
    """Persists objects with images. Returns item id -> resolved item snapshot."""
    processed: list[dict] = []
    image_cache: dict[str, str] = {}
    resolved: dict[str, dict[str, Any]] = {}
    total = len(objects)
    result_ids = recipe_result_ids(objects)
    for idx, obj in enumerate(objects, start=1):
        if obj["id"] in ctx.seen_entity_ids:
            continue
        ctx.seen_entity_ids.add(obj["id"])
        numbers = item_numbers(obj, placement.starting.item_defs.get(obj["id"], {}))
        image_url = await _object_image(ctx, obj, processed, image_cache, (idx, total))
        resolved[obj["id"]] = resolved_item(obj, image_url, numbers)

        in_avatar = (
            obj["id"] in placement.starting.inventory_ids
            or obj["id"] in placement.starting.equipped_ids
        )
        if in_avatar:
            _give_to_avatar(placement, obj["id"])
        if image_url:
            image_cache[obj["id"]] = image_url
        processed.append(obj)
        held = in_avatar or obj["id"] in placement.npc_item_ids
        hidden = starts_hidden(obj, result_ids)
        ctx.db.add(_object_entity(ctx, obj, image_url, numbers, held, default_scene_id, hidden))
        await ctx.commit_and_refresh()
    return resolved
