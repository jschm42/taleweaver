"""NPCs and items the author placed in a dynamic zone (``in: ZONE_ID`` in the blueprint).

The blueprint moves them into the zone config as blueprint text (``required_entities``,
``engine/blueprint/zone_entities.py``). Unlike loose instructions they are guaranteed: each
one appears exactly once per cluster, in the first generated room of its ``depth:`` (``max`` =
the deepest room; no depth = the first room generated). The scene generator asks for them in
the prompt, raises the room plan so they fit, and adds them afterwards when the model left
them out; the later NPC and object cuts never remove them, even beyond ``max_npcs``.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from backend.engine.blueprint.models import BlueprintBlock
from backend.engine.blueprint.parser import parse_blueprint
from backend.engine.blueprint.prompt import block_payload
from backend.engine.world.dynamic_instructions_helper import (
    bp_item_to_dynamic_object,
    bp_npc_to_dynamic_npc,
    resolve_container_inventory_links,
)
from backend.engine.world.dynamic_scene_schemas import (
    DynamicGeneratedNpc,
    DynamicGeneratedObject,
    DynamicGeneratedScenePayload,
)

_ENTITY_KINDS = ("npc", "item")
_ITEM_TYPES = {"CONTAINER": "allow_container", "SWITCH": "allow_switch"}


def _key(raw: object) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", str(raw or "").strip().upper()).strip("_")


def _generated_keys(cluster_context: Optional[list[dict[str, Any]]]) -> set[str]:
    """Ids and names of the NPCs and items already generated in this cluster."""
    keys: set[str] = set()
    for scene in cluster_context or []:
        for entry in [*(scene.get("npcs") or []), *(scene.get("objects") or [])]:
            keys.update(k for k in (_key(entry.get("id")), _key(entry.get("name"))) if k)
    return keys


def _target_depth(block: BlueprintBlock, max_depth: int) -> Optional[int]:
    raw = block.fields.get("dynamic_depth")
    if raw is None:
        return None
    if raw.value == "max":
        return max_depth
    return min(int(raw.value), max_depth)


def _is_due(block: BlueprintBlock, depth: int, max_depth: int, generated: set[str]) -> bool:
    if {_key(block.ref), _key(block.name)} & generated:
        return False
    target = _target_depth(block, max_depth)
    return target is None or target == depth


def required_blocks(
    zone: dict[str, Any], cluster_context: Optional[list[dict[str, Any]]] = None
) -> list[BlueprintBlock]:
    """The author-placed NPC/item blocks this room must contain."""
    text = str(zone.get("required_entities") or "").strip()
    if not text:
        return []
    depth = int(zone.get("depth") or 1)
    max_depth = int(zone.get("max_depth") or 3)
    generated = _generated_keys(cluster_context)
    return [
        block
        for block in parse_blueprint(text).blocks
        if block.kind in _ENTITY_KINDS and _is_due(block, depth, max_depth, generated)
    ]


def required_prompt_section(blocks: list[BlueprintBlock]) -> str:
    """The prompt block that asks for the author-placed entities of this room."""
    if not blocks:
        return ""
    entries = [{"kind": block.kind, **block_payload(block)} for block in blocks]
    return (
        "AUTHOR-REQUIRED ENTITIES IN THIS ROOM (MANDATORY):\n"
        "Include every entity below exactly once with EXACTLY the given `id` (NPCs in `npcs`, "
        "items in `objects`). `fixed` values are final, `notes` describe them. Build the room's "
        "description around them.\n" + json.dumps(entries, indent=1)
    )


def raise_plan_for_required(plan: dict[str, Any], blocks: list[BlueprintBlock]) -> dict[str, Any]:
    """Makes room in the rolled plan for the author-placed entities."""
    items = [b for b in blocks if b.kind == "item"]
    npcs = [b for b in blocks if b.kind == "npc"]
    if not blocks:
        return plan
    updated = dict(plan)
    updated["target_npcs"] = max(int(updated.get("target_npcs") or 0), len(npcs))
    if not items:
        return updated
    updated["target_objects"] = max(int(updated.get("target_objects") or 0), len(items))
    updated["allow_items"] = True
    types = list(updated.get("allowed_item_types") or [])
    for block in items:
        item_type = bp_item_to_dynamic_object(block)[0].item_type
        if item_type not in types:
            types.append(item_type)
        if item_type in _ITEM_TYPES:
            updated[_ITEM_TYPES[item_type]] = True
    updated["allowed_item_types"] = types
    return updated


def _upsert(entities: list[Any], entity: Any) -> Any:
    """Replaces a generated entity with the same id or name, else appends; returns the kept one."""
    keys = {_key(entity.id), _key(entity.name)}
    for index, current in enumerate(entities):
        if {_key(current.id), _key(current.name)} & keys:
            entity.id = current.id
            entities[index] = entity
            return entity
    entities.append(entity)
    return entity


def merge_required_entities(
    payload: DynamicGeneratedScenePayload, blocks: list[BlueprintBlock]
) -> set[str]:
    """Adds the author-placed entities to the room; returns their keys (protected from cuts)."""
    protected: set[str] = set()
    for block in blocks:
        if block.kind == "npc":
            kept = _upsert(payload.npcs, bp_npc_to_dynamic_npc(block))
        else:
            kept = _upsert(payload.objects, bp_item_to_dynamic_object(block)[0])
        protected.add(_key(kept.id))
    if protected:
        resolve_container_inventory_links(payload.objects)
        payload._required_keys = payload._required_keys | protected
    return protected


def split_protected(entities: list[Any], protected: set[str]) -> tuple[list[Any], list[Any]]:
    """(author-placed entities, the rest) in their original order."""
    mine = [e for e in entities if _key(e.id) in protected]
    rest = [e for e in entities if _key(e.id) not in protected]
    return mine, rest


def cap_npcs(
    npcs: list[DynamicGeneratedNpc], max_npcs: int, protected: set[str]
) -> list[DynamicGeneratedNpc]:
    """``max_npcs`` for the generated NPCs; author-placed NPCs always stay."""
    mine, rest = split_protected(npcs, protected)
    return [*mine, *rest[: max(0, max_npcs - len(mine))]]


def is_protected(obj: DynamicGeneratedObject, protected: set[str]) -> bool:
    return _key(obj.id) in protected


def required_entities_summary(zone: dict[str, Any]) -> str:
    """One line per author-placed entity of the zone, for the cluster planner."""
    text = str(zone.get("required_entities") or "").strip()
    if not text:
        return ""
    max_depth = int(zone.get("max_depth") or 3)
    lines = []
    for block in parse_blueprint(text).blocks:
        if block.kind not in _ENTITY_KINDS:
            continue
        target = _target_depth(block, max_depth)
        where = f"room depth {target}" if target else "the first room"
        lines.append(f"- {block.kind.upper()} {block.ref} ({block.name or block.ref}) in {where}")
    if not lines:
        return ""
    return (
        "AUTHOR-PLACED ENTITIES (they appear in these rooms; build the story around them, "
        "do not plan duplicates):\n" + "\n".join(lines)
    )


def npcs_to_persist(
    payload: DynamicGeneratedScenePayload, max_npcs: int
) -> list[DynamicGeneratedNpc]:
    """The NPCs a generated scene keeps: the author-placed ones plus ``max_npcs`` others."""
    return cap_npcs(list(payload.npcs or []), max_npcs, payload._required_keys)


def objects_to_persist(
    payload: DynamicGeneratedScenePayload, max_objects: int = 5
) -> list[DynamicGeneratedObject]:
    """The objects a generated scene keeps: the author-placed ones plus up to the cap."""
    mine, rest = split_protected(list(payload.objects or []), payload._required_keys)
    return [*mine, *rest[: max(0, max_objects - len(mine))]]
