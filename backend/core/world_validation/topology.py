"""Scene graph, exit, ID, and placement checks."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from typing import Any, Optional

from backend.core.world_validation.context import (
    INVENTORY_LOCATION,
    ValidationContext,
    entity_id,
    entity_kind,
    exit_is_bidirectional,
    finding,
    ref_ids,
    scene_id,
)
from backend.schemas.validation import ValidationFinding

_EXIT_KEY_FIELDS = ("code_to_unlock", "item_to_unlock", "rule_to_unlock", "unlock_expression")


def build_adjacency(
    exits: Iterable[dict[str, Any]], *, passable: Any = None
) -> dict[str, set[str]]:
    """Directed adjacency of the scene graph; ``passable(exit)`` can filter exits."""
    adjacency: dict[str, set[str]] = {}
    for exit_ in exits:
        a, b = exit_.get("from_scene_id"), exit_.get("to_scene_id")
        if not a or not b or (passable and not passable(exit_)):
            continue
        adjacency.setdefault(a, set()).add(b)
        if exit_is_bidirectional(exit_):
            adjacency.setdefault(b, set()).add(a)
    return adjacency


def reachable_scenes(start: Optional[str], adjacency: dict[str, set[str]]) -> set[str]:
    if not start:
        return set()
    visited: set[str] = {start}
    queue: deque[str] = deque([start])
    while queue:
        for nxt in adjacency.get(queue.popleft(), ()):
            if nxt not in visited:
                visited.add(nxt)
                queue.append(nxt)
    return visited


def check_unreachable_scenes(ctx: ValidationContext) -> list[ValidationFinding]:
    if not ctx.scenes:
        return []
    start = ctx.start_scene_id
    if not start or start not in ctx.scene_ids:
        return [
            finding(
                "error",
                "missing_start_scene",
                "Adventure has no reachable start scene.",
                location=f"scene:{start}" if start else None,
                start_scene_id=start,
                scene_count=len(ctx.scenes),
            )
        ]
    reachable = reachable_scenes(start, build_adjacency(ctx.exits))
    return [
        finding(
            "error",
            "unreachable_scene",
            f"Scene '{sid}' is not reachable from the start scene.",
            location=f"scene:{sid}",
            scene_id=sid,
            start_scene_id=start,
        )
        for sid in sorted(ctx.scene_ids - reachable)
    ]


def check_exit_targets_exist(ctx: ValidationContext) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for ex in ctx.exits:
        location = f"exit:{ex.get('id', '?')}"
        to_id, from_id = ex.get("to_scene_id"), ex.get("from_scene_id")
        if to_id and to_id not in ctx.scene_ids:
            findings.append(
                finding(
                    "error",
                    "exit_to_missing_scene",
                    f"Exit references scene '{to_id}' which does not exist.",
                    location=location,
                    exit_id=ex.get("id"),
                    missing_scene=to_id,
                )
            )
        if from_id and from_id not in ctx.scene_ids:
            findings.append(
                finding(
                    "error",
                    "exit_from_missing_scene",
                    f"Exit originates from scene '{from_id}' which does not exist.",
                    location=location,
                    exit_id=ex.get("id"),
                    missing_scene=from_id,
                )
            )
    return findings


def check_exit_labels(ctx: ValidationContext) -> list[ValidationFinding]:
    return [
        finding(
            "warn",
            "exit_without_label",
            "Exit has no label — players will see a blank transition.",
            location=f"exit:{ex.get('id', '?')}",
            exit_id=ex.get("id"),
        )
        for ex in ctx.exits
        if not (ex.get("label") or "").strip()
    ]


def check_exit_locks(ctx: ValidationContext) -> list[ValidationFinding]:
    """Locked exits need a way to open them, and key items must exist."""
    findings: list[ValidationFinding] = []
    for ex in ctx.exits:
        location = f"exit:{ex.get('id', '?')}"
        key_item = str(ex.get("item_to_unlock") or "").strip()
        if key_item and key_item not in ctx.object_ids:
            findings.append(
                finding(
                    "error",
                    "exit_key_item_missing",
                    f"Exit '{ex.get('label') or ex.get('id')}' is unlocked by item '{key_item}' "
                    "which does not exist.",
                    location=location,
                    exit_id=ex.get("id"),
                    missing_ref=key_item,
                )
            )
        has_key = any(str(ex.get(k) or "").strip() for k in _EXIT_KEY_FIELDS)
        if ex.get("is_locked") and not has_key:
            findings.append(
                finding(
                    "warn",
                    "exit_locked_without_key",
                    f"Exit '{ex.get('label') or ex.get('id')}' is locked but has no "
                    "code/item/rule/expression to open it.",
                    location=location,
                    exit_id=ex.get("id"),
                )
            )
    return findings


def check_duplicate_ids(ctx: ValidationContext) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    seen_scenes: set[str] = set()
    for scene in ctx.scenes:
        sid = scene_id(scene)
        if sid and sid in seen_scenes:
            findings.append(
                finding(
                    "error",
                    "duplicate_scene_id",
                    f"Scene id '{sid}' is used more than once.",
                    location=f"scene:{sid}",
                    scene_id=sid,
                )
            )
        seen_scenes.add(sid or "")

    seen_entities: set[str] = set()
    for entity in ctx.entities:
        eid = entity_id(entity)
        if eid and eid in seen_entities:
            findings.append(
                finding(
                    "error",
                    "duplicate_entity_id",
                    f"Entity id '{eid}' is used more than once.",
                    location=f"entity:{eid}",
                    entity_id=eid,
                )
            )
        seen_entities.add(eid or "")

    for clash in sorted(ctx.scene_ids & ctx.entity_ids):
        findings.append(
            finding(
                "error",
                "scene_entity_id_clash",
                f"ID '{clash}' is used by both a scene and an entity.",
                location=f"entity:{clash}",
                entity_id=clash,
            )
        )
    return findings


def _inventory_holders(ctx: ValidationContext) -> set[str]:
    """IDs of all items held by the protagonist or carried in an NPC/container inventory."""
    held = set(ref_ids(ctx.protagonist.get("inventory")))
    equipment = ctx.protagonist.get("equipment")
    if isinstance(equipment, dict):
        held.update(ref_ids(list(equipment.values())))
    for entity in ctx.entities:
        held.update(ref_ids(entity.get("inventory")))
    return held


def check_entity_placement(ctx: ValidationContext) -> list[ValidationFinding]:
    """Every entity must live in a scene, an inventory, or inside another entity."""
    if not ctx.scenes:
        return []
    findings: list[ValidationFinding] = []
    held = _inventory_holders(ctx)
    for entity in ctx.entities:
        eid = entity_id(entity) or "?"
        location = str(entity.get("current_scene_id") or "").strip()
        if location == INVENTORY_LOCATION:
            if entity_kind(entity) == "OBJECT" and eid not in held:
                findings.append(
                    finding(
                        "warn",
                        "inventory_item_without_owner",
                        f"Item '{eid}' is marked as carried, but neither the protagonist nor "
                        "any NPC/container holds it.",
                        location=f"entity:{eid}",
                        entity_id=eid,
                    )
                )
            continue
        if location in ctx.scene_ids or location in ctx.entity_ids:
            continue
        findings.append(
            finding(
                "error",
                "entity_in_missing_scene",
                f"{entity_kind(entity)} '{eid}' is placed in '{location or '(none)'}', "
                "which is neither a scene nor an entity.",
                location=f"entity:{eid}",
                entity_id=eid,
                missing_scene=location or None,
            )
        )
    return findings


def check_npc_allowed_scenes(ctx: ValidationContext) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for npc in ctx.entities_of("NPC"):
        eid = entity_id(npc) or "?"
        for sid in ref_ids(npc.get("allowed_scenes")):
            if sid in ctx.scene_ids:
                continue
            findings.append(
                finding(
                    "warn",
                    "npc_allowed_scene_missing",
                    f"NPC '{eid}' may move to scene '{sid}', which does not exist.",
                    location=f"entity:{eid}",
                    entity_id=eid,
                    missing_scene=sid,
                )
            )
    return findings
