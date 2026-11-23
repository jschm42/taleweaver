"""Room plan of a procedural dynamic scene and its enforcement on the generated payload.

``roll_scene_plan`` rolls how many NPCs (with type and attitude slots) and objects a room gets
from the zone's caps and spawn chances, the cluster node's role and the author's instructions
and placed entities. ``apply_scene_plan_to_payload`` enforces that plan on the LLM output.
"""

from __future__ import annotations

import random
import re
from typing import Any, Optional

from backend.engine.world.dynamic_instructions_helper import (
    adjust_plan_for_instructions,
    apply_instructions_backfill,
    ensure_object_item_stats,
    select_planned_objects,
)
from backend.engine.world.dynamic_required_entities import (
    is_protected,
    merge_required_entities,
    raise_plan_for_required,
    required_blocks,
    split_protected,
)
from backend.engine.world.dynamic_scene_schemas import (
    DynamicGeneratedScenePayload,
    resolve_effective_dynamic_rules,
)

_NPC_SLOT_TYPES: tuple[tuple[str, str], ...] = (
    ("humanoid", "HUMANOID"),
    ("being", "BEING"),
    ("animal", "ANIMAL"),
    ("monster", "MONSTER"),
)


def _roll_npc_slots(
    target_npcs: int,
    npc_type_caps: dict[str, int],
    spawn_chances: dict[str, int],
    effective_danger: str,
) -> list[dict[str, str]]:
    """Roll per-NPC type and attitude slots respecting caps and spawn probabilities."""
    counts = {key: 0 for key, _ in _NPC_SLOT_TYPES}
    slots: list[dict[str, str]] = []
    for _ in range(target_npcs):
        available = [
            (key, label) for key, label in _NPC_SLOT_TYPES if counts[key] < npc_type_caps[key]
        ]
        if not available:
            break
        weights = [max(0, int(spawn_chances.get(key, 0))) for key, _ in available]
        if sum(weights) <= 0:
            break
        chosen_key, chosen_label = random.choices(available, weights=weights, k=1)[0]
        counts[chosen_key] += 1
        is_hostile = (
            effective_danger != "peaceful" and random.random() * 100 < spawn_chances["enemy"]
        )
        slots.append(
            {
                "npc_type": chosen_label,
                "attitude": "hostile" if is_hostile else "neutral",
            }
        )
    return slots


def _apply_cluster_node_floors(
    npc_slots: list[dict[str, str]],
    allow_items: bool,
    target_objects: int,
    *,
    zone: dict[str, Any],
    effective_danger: str,
    npc_allowed: bool,
    max_npcs: int,
    spawn_chances: dict[str, int],
    allowed_tokens: set[str],
) -> tuple[list[dict[str, str]], bool, int]:
    """Guarantee obstacle/branch blueprint roles have needed hostiles or loot."""
    cluster_node = zone.get("cluster_node")
    if not isinstance(cluster_node, dict):
        return npc_slots, allow_items, target_objects
    role = str(cluster_node.get("role") or "").lower()
    can_spawn_enemy = (
        effective_danger != "peaceful"
        and npc_allowed
        and max_npcs > 0
        and spawn_chances["npc"] > 0
        and spawn_chances["enemy"] > 0
    )
    if role == "obstacle" and can_spawn_enemy:
        if not npc_slots:
            npc_slots = [{"npc_type": "HUMANOID", "attitude": "hostile"}]
        elif not any(slot["attitude"] == "hostile" for slot in npc_slots):
            npc_slots[0]["attitude"] = "hostile"
    if role in {"obstacle", "branch"} and "OBJECT" in allowed_tokens and spawn_chances["item"] > 0:
        allow_items = True
        target_objects = max(1, target_objects)
    return npc_slots, allow_items, target_objects


def roll_scene_plan(
    zone: dict[str, Any],
    max_npcs: int,
    effective_danger: str = "medium",
    generation_config: Optional[dict[str, Any]] = None,
    cluster_context: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Roll per-scene NPC and object composition targets from caps and spawn chances."""
    depth = int(zone.get("depth") or 1)
    max_depth = int(zone.get("max_depth") or 3)
    cul_de_sac = bool(zone.get("cul_de_sac_on_max_depth", True))
    is_climax = depth >= max_depth and cul_de_sac

    npc_type_caps, spawn_chances = resolve_effective_dynamic_rules(zone, generation_config)
    allowed_tokens = {
        str(token or "").strip().upper()
        for token in (zone.get("allowed_entity_types") or ["NPC", "OBJECT", "CONTAINER", "SWITCH"])
    }
    npc_allowed = bool(allowed_tokens & {"NPC", "FRIENDLY_NPC", "HOSTILE_NPC"})
    npc_roll_passes = (
        npc_allowed
        and max_npcs > 0
        and spawn_chances["npc"] > 0
        and random.random() * 100 < spawn_chances["npc"]
    )
    rolled_npcs = random.randint(1, max_npcs) if npc_roll_passes else 0
    npc_slots = _roll_npc_slots(rolled_npcs, npc_type_caps, spawn_chances, effective_danger)
    if is_climax and effective_danger != "peaceful" and npc_allowed and max_npcs > 0:
        if not npc_slots:
            npc_slots = [{"npc_type": "MONSTER", "attitude": "hostile"}]
        elif not any(slot["attitude"] == "hostile" for slot in npc_slots):
            npc_slots[0]["attitude"] = "hostile"

    allow_container = ("CONTAINER" in allowed_tokens) and (
        is_climax
        or (spawn_chances["container"] > 0 and random.random() * 100 < spawn_chances["container"])
    )
    allow_switch = (
        ("SWITCH" in allowed_tokens)
        and (not allow_container)
        and spawn_chances["switch"] > 0
        and random.random() * 100 < spawn_chances["switch"]
    )
    has_hostile_slot = any(slot["attitude"] == "hostile" for slot in npc_slots)
    needs_zone_key = has_hostile_slot and not is_climax and ("OBJECT" in allowed_tokens)
    allow_items = (
        is_climax
        or needs_zone_key
        or (spawn_chances["item"] > 0 and random.random() * 100 < spawn_chances["item"])
    )

    if allow_items:
        target_objects = max(2, random.randint(2, 3)) if is_climax else random.randint(1, 3)
    elif allow_container or allow_switch:
        target_objects = 1
    else:
        target_objects = 0

    npc_slots, allow_items, target_objects = _apply_cluster_node_floors(
        npc_slots,
        allow_items,
        target_objects,
        zone=zone,
        effective_danger=effective_danger,
        npc_allowed=npc_allowed,
        max_npcs=max_npcs,
        spawn_chances=spawn_chances,
        allowed_tokens=allowed_tokens,
    )

    allowed_item_types = (
        ["STANDARD", "CONSUMABLE", "WEARABLE", "WEAPON", "READABLE"] if allow_items else []
    )
    if allow_container:
        allowed_item_types.append("CONTAINER")
    if allow_switch:
        allowed_item_types.append("SWITCH")

    plan = adjust_plan_for_instructions(
        {
            "target_npcs": len(npc_slots),
            "npc_slots": npc_slots,
            "npc_type_caps": npc_type_caps,
            "allow_hostile": effective_danger != "peaceful" and spawn_chances["enemy"] > 0,
            "target_objects": target_objects,
            "allow_container": allow_container,
            "allow_switch": allow_switch,
            "allow_items": allow_items,
            "allowed_item_types": allowed_item_types,
            "is_climax": is_climax,
            "has_instructions": False,
        },
        zone,
        cluster_context,
    )
    return raise_plan_for_required(plan, required_blocks(zone, cluster_context))


def _filter_planned_npcs(
    npcs: list[Any],
    scene_plan: dict[str, Any],
) -> list[Any]:
    """Enforce target_npcs, per-type caps, and hostility rules on generated NPCs."""
    caps = dict(scene_plan.get("npc_type_caps") or {})
    allow_hostile = bool(scene_plan.get("allow_hostile", True))
    type_counts = {"humanoid": 0, "being": 0, "animal": 0, "monster": 0}
    filtered = []
    for npc in list(npcs or []):
        if len(filtered) >= int(scene_plan["target_npcs"]):
            break
        key = str(npc.npc_type or "HUMANOID").strip().lower()
        key = key if key in type_counts else "humanoid"
        if caps and type_counts[key] >= int(caps.get(key, 5)):
            continue
        type_counts[key] += 1
        if not allow_hostile and npc.attitude == "hostile":
            npc.attitude = "neutral"
            npc.combat_role = "none"
        filtered.append(npc)
    return filtered


def apply_scene_plan_to_payload(
    payload: DynamicGeneratedScenePayload,
    scene_plan: dict[str, Any],
    zone: Optional[dict[str, Any]] = None,
    cluster_context: Optional[list[dict[str, Any]]] = None,
) -> set[str]:
    """Enforce rolled NPC/object limits, per-type caps, hostility, and item stats. The
    author-placed zone entities are added and survive every cut; returns their keys."""
    protected: set[str] = set()
    if zone:
        apply_instructions_backfill(payload, zone, scene_plan, cluster_context)
        protected = merge_required_entities(payload, required_blocks(zone, cluster_context))
    own_npcs, other_npcs = split_protected(list(payload.npcs or []), protected)
    npc_plan = {**scene_plan, "target_npcs": int(scene_plan["target_npcs"]) - len(own_npcs)}
    payload.npcs = [*own_npcs, *_filter_planned_npcs(other_npcs, npc_plan)]

    max_cap = 5
    carried_ids = {
        re.sub(r"[^A-Z0-9]+", "_", str(item_id or "").strip().upper()).strip("_")
        for npc in (payload.npcs or [])
        for item_id in (npc.inventory or [])
    }
    own_objects, other_objects = split_protected(list(payload.objects or []), protected)
    sliced_objects = own_objects + select_planned_objects(
        other_objects,
        int(scene_plan["target_objects"]) - len(own_objects),
        max_cap=max_cap - len(own_objects),
        carried_ids=carried_ids,
    )
    allow_switch = bool(scene_plan["allow_switch"])
    allow_container = bool(scene_plan["allow_container"])
    seen_switch = False
    seen_container = False

    for obj in sliced_objects:
        if is_protected(obj, protected):
            ensure_object_item_stats(obj)
            continue
        if obj.item_type == "SWITCH":
            obj.item_type = "STANDARD" if (not allow_switch or seen_switch) else "SWITCH"
            seen_switch = seen_switch or (obj.item_type == "SWITCH")
        elif obj.item_type == "CONTAINER":
            obj.item_type = "STANDARD" if (not allow_container or seen_container) else "CONTAINER"
            seen_container = seen_container or (obj.item_type == "CONTAINER")
        ensure_object_item_stats(obj)

    payload.objects = sliced_objects
    return protected


def apply_peaceful_filter(npcs: list[Any]) -> None:
    """Ensure no hostile combat roles or attitudes appear in peaceful zones."""
    for npc in npcs:
        npc.combat_role = "none"
        if npc.attitude == "hostile":
            npc.attitude = "neutral"
