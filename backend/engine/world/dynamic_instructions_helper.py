"""Helpers for dynamic exit generation instructions, blueprint blocks, and cluster consistency."""

from __future__ import annotations

import json
import random
import re
from typing import Any, Optional

from backend.engine.blueprint.parser import has_blueprint_tags, parse_blueprint
from backend.engine.blueprint.prompt import blueprint_payload
from backend.engine.world.dynamic_scene_schemas import (
    DynamicGeneratedNpc,
    DynamicGeneratedObject,
    DynamicGeneratedScenePayload,
)

_WEARABLE_SLOT_FALLBACKS: tuple[str, ...] = ("Head", "Neck", "Chest", "Hands", "Ring", "Feet")
_WEARABLE_STAT_ATTRS: tuple[str, ...] = (
    "stat_modifier_strength",
    "stat_modifier_dexterity",
    "stat_modifier_intelligence",
    "stat_modifier_wisdom",
    "stat_modifier_charisma",
    "stat_modifier_armor_class",
)

_ALL_DYNAMIC_ITEM_TYPES: list[str] = [
    "STANDARD",
    "CONSUMABLE",
    "WEARABLE",
    "WEAPON",
    "READABLE",
    "CONTAINER",
    "SWITCH",
]
_DICE_PATTERN = re.compile(r"^\d+d\d*(?:[+-]\d+)?$", re.IGNORECASE)
_DYNAMIC_ITEM_TYPE_MAP: dict[str, str] = {
    "STANDARD": "STANDARD",
    "CONSUMABLE": "CONSUMABLE",
    "WEARABLE": "WEARABLE",
    "WEAPON": "WEAPON",
    "CONTAINER": "CONTAINER",
    "READABLE": "READABLE",
    "SWITCH": "SWITCH",
    "CONTAINER_SWITCH": "CONTAINER",
    "CONSTRUCTABLE": "STANDARD",
    "STATIC": "STANDARD",
    "PICKABLE": "STANDARD",
    "TOOL": "STANDARD",
    "KEY": "STANDARD",
}


def is_valid_damage_dice(value: object) -> bool:
    """Return True for valid dice notation such as ``1d6``, ``1d+2``, or ``2d8-1``."""
    return bool(_DICE_PATTERN.fullmatch(str(value or "").strip()))


def ensure_object_item_stats(obj: DynamicGeneratedObject) -> None:
    """Guarantee gear/consumable objects carry usable stats while leaving trinkets as flavor."""
    if obj.item_type == "CONSUMABLE":
        if obj.hp_change == 0 and obj.stamina_change == 0 and obj.mana_change == 0:
            obj.hp_change = 15
        return
    if obj.item_type == "WEARABLE":
        if not obj.wearable_slots:
            obj.wearable_slots = [random.choice(_WEARABLE_SLOT_FALLBACKS)]
        if not any(getattr(obj, attr, 0) != 0 for attr in _WEARABLE_STAT_ATTRS):
            setattr(obj, random.choice(_WEARABLE_STAT_ATTRS), 1)
        return
    if obj.item_type == "WEAPON" and not is_valid_damage_dice(obj.damage_dice):
        obj.damage_dice = "1d6"


def _norm_key(raw: object) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", str(raw or "").strip().upper()).strip("_")


def _extract_prose_kv(prose_lines: list[str]) -> dict[str, str]:
    extracted: dict[str, str] = {}
    for line in prose_lines:
        if ":" not in line:
            continue
        raw_k, raw_v = line.split(":", 1)
        key = re.sub(r"[\s\-]+", "_", raw_k.strip().lower())
        val = raw_v.strip()
        if key and val:
            extracted[key] = val
    return extracted


def _add_name_and_id_keys(target: set[str], items: list[dict[str, Any]]) -> None:
    for item in items:
        id_key = _norm_key(item.get("id") or item.get("scene_id"))
        name_key = _norm_key(item.get("name"))
        if id_key:
            target.add(id_key)
        if name_key:
            target.add(name_key)


def _collect_cluster_entity_keys(
    cluster_context: Optional[list[dict[str, Any]]],
) -> tuple[set[str], set[str]]:
    scene_keys: set[str] = set()
    entity_keys: set[str] = set()
    _add_name_and_id_keys(scene_keys, list(cluster_context or []))
    for scene in cluster_context or []:
        _add_name_and_id_keys(entity_keys, list(scene.get("npcs") or []))
        _add_name_and_id_keys(entity_keys, list(scene.get("objects") or []))
    return scene_keys, entity_keys


def adjust_plan_for_instructions(plan: dict[str, Any], zone: dict[str, Any]) -> dict[str, Any]:
    """Ensure rolled scene plan does not strip containers, weapons, or NPCs required by instructions."""
    instructions = str(zone.get("instructions") or "").strip()
    if not instructions:
        return plan

    updated = dict(plan)
    updated["allow_items"] = True
    updated["allow_container"] = True
    updated["allow_switch"] = True
    updated["allowed_item_types"] = list(_ALL_DYNAMIC_ITEM_TYPES)
    max_npcs = max(0, int(zone.get("max_npcs", 2)))

    if has_blueprint_tags(instructions):
        bp = parse_blueprint(instructions)
        item_blocks = bp.of_kind("item")
        npc_blocks = bp.of_kind("npc")
        updated["target_objects"] = max(
            int(updated.get("target_objects") or 0),
            min(5, max(2, len(item_blocks))),
        )
        if npc_blocks and max_npcs > 0:
            updated["target_npcs"] = max(
                int(updated.get("target_npcs") or 0),
                min(max_npcs, len(npc_blocks)),
            )
        return updated

    updated["target_objects"] = max(int(updated.get("target_objects") or 0), 3)
    lowered = instructions.lower()
    npc_cues = ("npc", "guard", "merchant", "keeper", "smith", "bandit", "enemy", "wolf")
    if max_npcs > 0 and any(cue in lowered for cue in npc_cues):
        updated["target_npcs"] = max(1, int(updated.get("target_npcs") or 0))
    return updated


def _format_cluster_scene_line(scene: dict[str, Any]) -> list[str]:
    name = str(scene.get("name") or scene.get("scene_id") or "Unknown")
    depth = scene.get("depth", 1)
    desc = str(scene.get("description") or "")[:180].strip()
    lines = [f"- Scene '{name}' (depth {depth}): {desc}"]

    npcs = scene.get("npcs") or []
    if npcs:
        npc_bits = [f"{n.get('name')} [{n.get('npc_type', 'HUMANOID')}]" for n in npcs[:4]]
        lines.append(f"  NPCs already here: {', '.join(npc_bits)}")

    objs = scene.get("objects") or []
    if objs:
        obj_bits: list[str] = []
        for o in objs[:6]:
            tag = f"{o.get('name')} ({o.get('item_type', 'STANDARD')})"
            if o.get("damage_dice"):
                tag += f" [dmg: {o['damage_dice']}]"
            if o.get("in_container"):
                tag += f" [inside: {o['in_container']}]"
            obj_bits.append(tag)
        lines.append(f"  Objects already here: {', '.join(obj_bits)}")
    return lines


def build_cluster_consistency_prompt_section(
    zone: dict[str, Any],
    cluster_context: Optional[list[dict[str, Any]]] = None,
) -> str:
    """Format hierarchical cluster themes and optional existing cluster scenes/NPCs/items."""
    root_theme = str(zone.get("root_theme") or zone.get("theme") or "").strip()
    local_theme = str(zone.get("theme") or "").strip()
    lines = [f"Cluster Base Exit Theme: {root_theme}"]
    if local_theme and local_theme != root_theme:
        lines.append(f"Local Passage Sub-Theme: {local_theme}")

    if not zone.get("cluster_consistency", True) or not cluster_context:
        return "\n".join(lines)

    lines.append("")
    lines.append("CLUSTER CONSISTENCY CONTEXT (EXISTING SCENES IN THIS CLUSTER):")
    for scene in cluster_context:
        lines.extend(_format_cluster_scene_line(scene))
    lines.append(
        "CONSISTENCY RULES:\n"
        "- Maintain architectural, tonal, and environmental continuity with the adventure theme, "
        "cluster base theme, and existing cluster scenes above.\n"
        "- Do NOT duplicate unique NPCs or unique special loot already placed in existing cluster scenes.\n"
        "- Make this scene a distinct, connected part of the same area."
    )
    return "\n".join(lines)


def build_instructions_prompt_section(
    zone: dict[str, Any],
    cluster_context: Optional[list[dict[str, Any]]] = None,
) -> str:
    """Format author generation instructions (loose prompt or Blueprint) for the scene generator."""
    instructions = str(zone.get("instructions") or "").strip()
    if not instructions:
        return ""

    consistency_on = bool(zone.get("cluster_consistency", True))
    scene_keys, entity_keys = (
        _collect_cluster_entity_keys(cluster_context) if consistency_on else (set(), set())
    )
    already_note = ""
    if entity_keys or scene_keys:
        combined = sorted(entity_keys | scene_keys)[:20]
        already_note = (
            "\nALREADY GENERATED IN EARLIER CLUSTER SCENES (do not duplicate if unique): "
            + ", ".join(combined)
        )

    if has_blueprint_tags(instructions):
        bp = parse_blueprint(instructions)
        bp_json = json.dumps(blueprint_payload(bp), indent=1)
        return (
            "\nDYNAMIC EXIT BLUEPRINT INSTRUCTIONS (HIGH PRIORITY):\n"
            "Honor the structured blueprint below when fitting this location and its contents. "
            "If an item belongs inside a CONTAINER, emit both the CONTAINER object and the contained item(s) "
            "in `objects`, and put each contained item's `id` inside the container's `inventory` list.\n"
            f"{already_note}\n"
            f"Blueprint:\n{bp_json}"
        ).strip()

    return (
        "\nDYNAMIC EXIT GENERATION INSTRUCTIONS (HIGH PRIORITY):\n"
        f"{instructions}\n"
        "CONTAINER & LOOT RULE: Whenever instructions place item(s) inside a container (such as a chest, crate, or sack), "
        "create the CONTAINER in `objects` AND each contained item in `objects`, and list the contained item `id`(s) "
        "inside the container's `inventory` array. Preserve exact requested weapon damage dice such as '1d+2'."
        f"{already_note}"
    ).strip()


def _bp_item_to_dynamic_object(block: Any) -> tuple[DynamicGeneratedObject, str]:
    values = {**block.hints(), **block.fixed()}
    prose_kv = _extract_prose_kv(block.prose)
    raw_type = str(values.get("item_type") or prose_kv.get("item_type") or "STANDARD").upper()
    item_type = _DYNAMIC_ITEM_TYPE_MAP.get(raw_type, "STANDARD")
    obj_id = _norm_key(block.ref or block.name)[:24] or "BLUEPRINT_ITEM"
    damage_dice = (
        str(values.get("damage_dice") or prose_kv.get("damage_dice") or "").strip() or None
    )
    if damage_dice and item_type == "STANDARD":
        item_type = "WEAPON"

    inventory_raw = values.get("inventory") or []
    inv_tokens = [_norm_key(entry)[:24] for entry in inventory_raw if _norm_key(entry)]
    location_ref = str(
        prose_kv.get("location") or prose_kv.get("container") or values.get("start_scene_id") or ""
    ).strip()

    desc = block.description or prose_kv.get("description") or f"A notable {block.name or obj_id}."
    obj = DynamicGeneratedObject(
        id=obj_id,
        name=(block.name or obj_id)[:100],
        item_type=item_type,  # type: ignore[arg-type]
        description=desc[:1500],
        is_takeable=bool(values.get("is_portable", item_type not in {"CONTAINER", "SWITCH"})),
        wearable_slots=list(values.get("wearable_slots") or []),
        hp_change=int(values.get("hp_change") or 0),
        stamina_change=int(values.get("stamina_change") or 0),
        mana_change=int(values.get("mana_change") or 0),
        damage_dice=damage_dice[:20] if damage_dice else None,
        text_log_content=values.get("text_log_content"),
        inventory=inv_tokens,
    )
    return obj, _norm_key(location_ref)


def _bp_npc_to_dynamic_npc(block: Any) -> DynamicGeneratedNpc:
    values = {**block.hints(), **block.fixed()}
    raw_type = str(values.get("npc_type") or "HUMANOID").strip().upper()
    npc_type = raw_type if raw_type in {"HUMANOID", "ANIMAL", "MONSTER", "BEING"} else "HUMANOID"
    attack_mode = str(values.get("attack_mode") or "PASSIVE").upper()
    attitude = "hostile" if attack_mode == "ATTACK_ON_SIGHT" else "neutral"
    npc_id = _norm_key(block.ref or block.name)[:24] or "BLUEPRINT_NPC"
    return DynamicGeneratedNpc(
        id=npc_id,
        name=(block.name or npc_id)[:100],
        npc_type=npc_type,  # type: ignore[arg-type]
        role=str(values.get("goal") or "Local inhabitant")[:100],
        description=(block.description or f"{block.name or npc_id} watches closely.")[:1500],
        visual_description=str(values.get("appearance") or "")[:1000],
        attitude=attitude,  # type: ignore[arg-type]
        combat_role="standard" if attitude == "hostile" else "none",
    )


def _resolve_container_inventory_links(objects: list[DynamicGeneratedObject]) -> None:
    by_token: dict[str, str] = {}
    for obj in objects:
        by_token[_norm_key(obj.id)] = obj.id
        by_token[_norm_key(obj.name)] = obj.id

    for obj in objects:
        if obj.item_type != "CONTAINER" or not obj.inventory:
            continue
        resolved: list[str] = []
        for token in obj.inventory:
            mapped = by_token.get(_norm_key(token), token)
            if mapped and mapped != obj.id and mapped not in resolved:
                resolved.append(mapped)
        obj.inventory = resolved


def _upsert_blueprint_object(
    payload: DynamicGeneratedScenePayload,
    bp_obj: DynamicGeneratedObject,
    existing_by_key: dict[str, DynamicGeneratedObject],
) -> Optional[DynamicGeneratedObject]:
    match = existing_by_key.get(_norm_key(bp_obj.id)) or existing_by_key.get(_norm_key(bp_obj.name))
    if match is not None:
        match.item_type = bp_obj.item_type
        if bp_obj.damage_dice:
            match.damage_dice = bp_obj.damage_dice
        if bp_obj.inventory:
            match.inventory = list(dict.fromkeys([*match.inventory, *bp_obj.inventory]))
        return match
    if len(payload.objects) >= 5:
        return None
    payload.objects.append(bp_obj)
    existing_by_key[_norm_key(bp_obj.id)] = bp_obj
    existing_by_key[_norm_key(bp_obj.name)] = bp_obj
    return bp_obj


def _merge_blueprint_objects(
    payload: DynamicGeneratedScenePayload,
    item_blocks: list[Any],
    entity_keys: set[str],
    scene_keys: set[str],
) -> None:
    pending_location: list[tuple[str, str]] = []
    existing_by_key = {_norm_key(obj.id): obj for obj in payload.objects}
    for obj in payload.objects:
        existing_by_key[_norm_key(obj.name)] = obj

    for block in item_blocks:
        bp_obj, loc_key = _bp_item_to_dynamic_object(block)
        if _norm_key(bp_obj.id) in entity_keys or _norm_key(bp_obj.name) in entity_keys:
            continue
        if loc_key and loc_key in scene_keys:
            continue
        target_obj = _upsert_blueprint_object(payload, bp_obj, existing_by_key)
        if target_obj is not None and loc_key:
            pending_location.append((target_obj.id, loc_key))

    for child_id, loc_key in pending_location:
        container = existing_by_key.get(loc_key)
        if container and container.item_type == "CONTAINER" and child_id not in container.inventory:
            container.inventory.append(child_id)


def _merge_blueprint_npcs(
    payload: DynamicGeneratedScenePayload,
    npc_blocks: list[Any],
    entity_keys: set[str],
    max_npcs: int,
) -> None:
    existing_npc_keys = {_norm_key(k) for n in payload.npcs for k in (n.id, n.name) if _norm_key(k)}
    for block in npc_blocks:
        if len(payload.npcs) >= max_npcs:
            break
        bp_npc = _bp_npc_to_dynamic_npc(block)
        id_key, name_key = _norm_key(bp_npc.id), _norm_key(bp_npc.name)
        if id_key in entity_keys or name_key in entity_keys:
            continue
        if id_key in existing_npc_keys or name_key in existing_npc_keys:
            continue
        payload.npcs.append(bp_npc)
        existing_npc_keys.update({id_key, name_key})


def apply_instructions_backfill(
    payload: DynamicGeneratedScenePayload,
    zone: dict[str, Any],
    scene_plan: dict[str, Any],
    cluster_context: Optional[list[dict[str, Any]]] = None,
) -> None:
    """Deterministically enforce blueprint items/NPCs and resolve container inventory links."""
    del scene_plan
    instructions = str(zone.get("instructions") or "").strip()
    consistency_on = bool(zone.get("cluster_consistency", True))
    scene_keys, entity_keys = (
        _collect_cluster_entity_keys(cluster_context) if consistency_on else (set(), set())
    )

    if instructions and has_blueprint_tags(instructions):
        bp = parse_blueprint(instructions)
        _merge_blueprint_objects(payload, bp.of_kind("item"), entity_keys, scene_keys)
        max_npcs = max(0, int(zone.get("max_npcs", 2)))
        _merge_blueprint_npcs(payload, bp.of_kind("npc"), entity_keys, max_npcs)

    _resolve_container_inventory_links(payload.objects)


def select_planned_objects(
    objects: list[DynamicGeneratedObject],
    target_objects: int,
    max_cap: int = 5,
) -> list[DynamicGeneratedObject]:
    """Slice objects up to ``target_objects`` while retaining items placed inside kept containers."""
    limit = min(max_cap, max(0, int(target_objects)))
    if limit <= 0:
        return []
    kept = list(objects or [])[:limit]
    kept_ids = {_norm_key(obj.id) for obj in kept}
    child_ids = {
        _norm_key(child_id)
        for obj in kept
        if obj.item_type == "CONTAINER"
        for child_id in obj.inventory
    }
    for obj in list(objects or [])[limit:]:
        if len(kept) >= max_cap:
            break
        key = _norm_key(obj.id)
        if key in child_ids and key not in kept_ids:
            kept.append(obj)
            kept_ids.add(key)
    return kept
