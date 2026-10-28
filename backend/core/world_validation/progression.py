"""Key progression (softlock) analysis.

Explores the world like a player would: walk every passable exit, pick up every item
that is accessible, use those items as keys, and repeat until nothing new opens up.
A locked exit or container whose key item never becomes obtainable is a softlock.

Assumptions (deliberately optimistic, so only provable dead ends are reported):
- code/rule/expression locks are solvable; only item locks are modelled,
- hidden items can be revealed, NPCs hand over or drop what they carry,
- recipe results appear once all ingredients are obtainable; results without a reveal
  path of their own (reveal rule, another item's reveals_item_id) appear only that way,
- scripts are not executed (findings mention that a script could still grant the key).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.core.world_validation.context import (
    ValidationContext,
    entity_field,
    entity_id,
    finding,
    item_type,
    ref_id,
    ref_ids,
)
from backend.core.world_validation.topology import build_adjacency, reachable_scenes
from backend.schemas.validation import ValidationFinding


@dataclass
class _World:
    ctx: ValidationContext
    holders: dict[str, str]  # item id -> entity id whose inventory lists it
    recipes: dict[str, list[list[str]]] = field(default_factory=dict)  # result -> ingredients
    craft_only: set[str] = field(default_factory=set)  # results without another reveal path
    scenes: set[str] = field(default_factory=set)
    items: set[str] = field(default_factory=set)

    def craftable(self, eid: str) -> bool:
        return any(
            len(ingredients) >= 2 and all(i in self.items for i in ingredients)
            for ingredients in self.recipes.get(eid, [])
        )

    def exit_passable(self, exit_: dict[str, Any]) -> bool:
        key = str(exit_.get("item_to_unlock") or "").strip()
        return not exit_.get("is_locked") or not key or key in self.items

    def container_open(self, entity: dict[str, Any]) -> bool:
        key = str(entity_field(entity, "item_to_unlock") or "").strip()
        return not key or key in self.items

    def accessible(self, eid: str, visiting: frozenset[str] = frozenset()) -> bool:
        """True when the entity can be reached by the player in the current round."""
        entity = self.ctx.entities_by_id.get(eid)
        if entity is None or eid in visiting:
            return False
        visiting = visiting | {eid}
        # Recipes are meta items; their results appear once all ingredients are obtainable.
        if item_type(entity) == "CONSTRUCTABLE":
            return False
        if self.craftable(eid):
            return True
        if eid in self.craft_only:
            return False

        location = str(entity.get("current_scene_id") or "").strip()
        if location in self.scenes:
            return True
        parents = [p for p in (location, self.holders.get(eid)) if p in self.ctx.entities_by_id]
        return any(self._parent_yields(p, visiting) for p in parents)

    def _parent_yields(self, parent_id: str, visiting: frozenset[str]) -> bool:
        parent = self.ctx.entities_by_id[parent_id]
        return self.accessible(parent_id, visiting) and self.container_open(parent)


def _holders(ctx: ValidationContext) -> dict[str, str]:
    holders: dict[str, str] = {}
    for entity in ctx.entities:
        for item in ref_ids(entity.get("inventory")):
            holders.setdefault(item, entity_id(entity) or "")
    return holders


def _recipes(ctx: ValidationContext) -> dict[str, list[list[str]]]:
    recipes: dict[str, list[list[str]]] = {}
    for entity in ctx.entities:
        if item_type(entity) != "CONSTRUCTABLE":
            continue
        ingredients = ref_ids(entity.get("combination_ingredients"))
        for result in ref_ids(entity_field(entity, "result_item_ids")):
            recipes.setdefault(result, []).append(ingredients)
    return recipes


def _craft_only(ctx: ValidationContext, results: set[str]) -> set[str]:
    """Results that have no reveal rule and are not revealed by another item."""
    revealed = {
        str(e.get("reveals_item_id") or "").strip()
        for e in ctx.entities
        if item_type(e) != "CONSTRUCTABLE"
    }
    with_rule = {
        rid
        for rid in results
        if str((ctx.entities_by_id.get(rid) or {}).get("reveal_rule") or "").strip()
    }
    return results - revealed - with_rule


def _starting_items(ctx: ValidationContext) -> set[str]:
    equipment = ctx.protagonist.get("equipment")
    entries = list(ctx.protagonist.get("inventory") or [])
    entries += list(equipment.values()) if isinstance(equipment, dict) else []
    return {rid for rid in (ref_id(e) for e in entries) if rid}


def _explore(ctx: ValidationContext) -> _World:
    recipes = _recipes(ctx)
    world = _World(
        ctx=ctx,
        holders=_holders(ctx),
        recipes=recipes,
        craft_only=_craft_only(ctx, set(recipes)),
        items=_starting_items(ctx),
    )
    while True:
        scenes = reachable_scenes(
            ctx.start_scene_id, build_adjacency(ctx.exits, passable=world.exit_passable)
        )
        world.scenes = scenes
        # Items and scenes only ever grow, so this reaches a fixpoint after <= #locks rounds.
        items = world.items | {eid for eid in ctx.object_ids if world.accessible(eid)}
        if items == world.items:
            return world
        world.items = items


def _exit_findings(world: _World) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for ex in world.ctx.exits:
        key = str(ex.get("item_to_unlock") or "").strip()
        at_lock = {ex.get("from_scene_id"), ex.get("to_scene_id")} & world.scenes
        if not ex.get("is_locked") or not key or key in world.items:
            continue
        if not at_lock or key not in world.ctx.object_ids:
            continue
        findings.append(
            finding(
                "warn",
                "exit_key_unobtainable",
                f"Exit '{ex.get('label') or ex.get('id')}' needs item '{key}', but the player "
                "can never obtain it (unless a script grants it).",
                location=f"exit:{ex.get('id', '?')}",
                exit_id=ex.get("id"),
                key_item=key,
            )
        )
    return findings


def _container_findings(world: _World) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for eid in sorted(world.ctx.object_ids):
        container = world.ctx.entities_by_id[eid]
        key = str(entity_field(container, "item_to_unlock") or "").strip()
        if item_type(container) != "CONTAINER" or not key or key in world.items:
            continue
        if key not in world.ctx.object_ids or not world.accessible(eid):
            continue
        findings.append(
            finding(
                "warn",
                "container_key_unobtainable",
                f"Container '{eid}' needs item '{key}', but the player can never obtain it "
                "(unless a script grants it).",
                location=f"entity:{eid}",
                entity_id=eid,
                key_item=key,
            )
        )
    return findings


def check_key_progression(ctx: ValidationContext) -> list[ValidationFinding]:
    if not ctx.start_scene_id or ctx.start_scene_id not in ctx.scene_ids:
        return []
    world = _explore(ctx)
    return _exit_findings(world) + _container_findings(world)
