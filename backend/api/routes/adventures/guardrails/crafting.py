"""CONSTRUCTABLE recipes: deterministic crafting and blocking of illegal spawns/reveals.

A CONSTRUCTABLE is a recipe (a meta item that never appears in the world). When the player
combines ALL of its ``combination_ingredients`` (minimum 2), the ingredients are used up
(except the ``kept_ingredients``) and its hidden ``result_item_ids`` are revealed. Crafting
requires the GM's ``combination_intent`` (set by the LLM in any language), every ingredient
to be reachable, and at least one ingredient to be referenced (or the GM granting a result).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from backend.api.routes.adventures.guardrails.base import item_id_upper
from backend.engine.interaction.switch_service import SwitchService
from backend.engine.rules.crafting_recipes import (
    craft_only_result_ids,
    is_recipe,
    recipe_ingredients,
    recipe_kept,
    recipe_results,
)
from backend.engine.rules.rule_engine import GameEvent, InventoryItem
from backend.models.world_entity import WorldEntity

logger = logging.getLogger(__name__)

MIN_INGREDIENTS = 2
MIN_TOKEN_LENGTH = 3
CRAFT_TOO_FEW_MESSAGE = "Choose at least two items to combine."
CRAFT_UNREACHABLE_MESSAGE = "You can only combine items you carry or that are here with you."
CRAFT_NO_MATCH_MESSAGE = "You try to combine them, but nothing comes of it."
CRAFT_BLOCKED_MESSAGE = "You cannot craft that right now."

Reporter = Callable[[str, str], None]


@dataclass
class CraftingState:
    """Per-turn crafting bookkeeping."""

    lowered_msg: str
    entities_by_id: dict[str, WorldEntity]
    inventory_ids: dict[str, str]  # upper id -> original id (for removal)
    accessible_ids: set[str]
    consumed: set[str] = field(default_factory=set)
    constructed: set[str] = field(default_factory=set)  # upper ids of the results produced
    messages: list[str] = field(default_factory=list)


def _granted_by_gm(event: GameEvent, result_ids: list[str]) -> bool:
    items = [*(event.new_inventory_items or []), *(event.spawned_items or [])]
    return any(item_id_upper(item) in result_ids for item in items)


def _ignore(_kind: str, _fallback: str) -> None:
    return None


class CraftingGuardMixin:
    """Resolves crafting and reverts recipe results the GM produced without crafting."""

    def _crafting_state(self, entities: list[WorldEntity], lowered: str) -> CraftingState:
        inventory_ids = {
            str(i["id"]).strip().upper(): str(i["id"])
            for i in self.avatar.inventory or []
            if isinstance(i, dict) and i.get("id")
        }
        scene_ids = set()
        for ent in entities:
            # Scene presence uses the stored location; only the hidden flag honours overrides.
            in_scene = (
                ent.current_scene_id == self.state.current_scene_id and not ent.is_in_inventory
            )
            if ent.id and in_scene and not self._is_hidden_now(ent):
                scene_ids.add(ent.id.upper())
        return CraftingState(
            lowered_msg=lowered,
            entities_by_id={e.id.upper(): e for e in entities if e.id},
            inventory_ids=inventory_ids,
            accessible_ids=set(inventory_ids) | scene_ids,
        )

    def _scene_of(self, ent: WorldEntity) -> str | None:
        override = (self.state.entity_states or {}).get(ent.id, {})
        return override.get("current_scene_id") or ent.current_scene_id

    def _is_hidden_now(self, ent: WorldEntity) -> bool:
        # Recipes are meta items and never become visible.
        if is_recipe(ent):
            return True
        override = (self.state.entity_states or {}).get(ent.id, {})
        if override.get("is_hidden") is not None:
            return bool(override["is_hidden"])
        return bool(ent.is_hidden)

    @staticmethod
    def _ingredient_referenced(needed: set[str], cs: CraftingState) -> bool:
        for ingredient in needed:
            ent = cs.entities_by_id.get(ingredient)
            for token in (ingredient, ent.name if ent and ent.name else ""):
                low = token.lower()
                if len(low) >= MIN_TOKEN_LENGTH and re.search(
                    r"\b" + re.escape(low) + r"\b", cs.lowered_msg
                ):
                    return True
        return False

    def _pending_results(self, recipe: WorldEntity, cs: CraftingState) -> list[WorldEntity]:
        """The recipe's results still waiting to be crafted (existing and hidden)."""
        results = [cs.entities_by_id.get(rid) for rid in recipe_results(recipe)]
        return [
            res
            for res in results
            if res is not None and res.id.upper() not in cs.constructed and self._is_hidden_now(res)
        ]

    def _is_craftable(self, recipe: WorldEntity, needed: set[str], cs: CraftingState) -> bool:
        if len(needed) < MIN_INGREDIENTS or needed & cs.consumed:
            return False
        if not self._pending_results(recipe, cs):
            return False
        return needed.issubset(cs.accessible_ids)

    async def _craft_guard_blocks(self, recipe: WorldEntity) -> list[str] | None:
        """Runs the craft guard expression; returns failure messages or None when allowed.

        The adventure's ``on_craft_failure_text`` replaces the default failure message. The
        messages are returned unsaved; the caller persists them.
        """
        meta = dict(recipe.metadata_json or {})
        expression = str(meta.get("craft_guard_expression") or "").strip()
        if not expression:
            return None
        passed, detail = SwitchService.evaluate_gate_expression(
            expression, await self.manager._build_script_context()
        )
        if passed:
            return None
        messages = []
        if meta.get("on_craft_failure_script"):
            messages += await self.manager._execute_inline_script(
                meta["on_craft_failure_script"], "on_craft_failure", recipe.id
            )
        fail_text = str(meta.get("on_craft_failure_text") or detail or CRAFT_BLOCKED_MESSAGE)
        return [fail_text, *messages]

    def _consume_ingredients(
        self, event: GameEvent, needed: set[str], kept: set[str], cs: CraftingState
    ) -> bool:
        """Removes inventory ingredients / hides scene ingredients, except the kept ones.

        Returns True if all ingredients (kept ones included) came from the inventory.
        """
        all_in_inventory = needed.issubset(cs.inventory_ids)
        for ingredient in needed - kept:
            if ingredient in cs.inventory_ids:
                event.removed_inventory_item_ids = event.removed_inventory_item_ids or []
                original = cs.inventory_ids[ingredient]
                if original not in event.removed_inventory_item_ids:
                    event.removed_inventory_item_ids.append(original)
            else:
                self._upsert_entity_update(event, ingredient, is_hidden=True)
            cs.consumed.add(ingredient)
        return all_in_inventory

    def _place_result(self, event: GameEvent, res: WorldEntity, all_in_inventory: bool) -> None:
        """The result lands in the inventory, or in the scene when any ingredient lay there."""
        self._upsert_entity_update(event, res.id, is_hidden=False)
        if not all_in_inventory:
            if self._scene_of(res) != self.state.current_scene_id:
                self._upsert_entity_movement(event, res.id, self.state.current_scene_id)
            return
        event.new_inventory_items = event.new_inventory_items or []
        if any(i.id == res.id for i in event.new_inventory_items):
            return
        event.new_inventory_items.append(
            InventoryItem(
                id=res.id,
                name=res.name or "Unknown Item",
                description=res.description,
                item_type=res.item_type,
                image_url=res.image_url,
            )
        )

    async def _craft(
        self, event: GameEvent, recipe: WorldEntity, needed: set[str], cs: CraftingState
    ) -> None:
        produced = self._pending_results(recipe, cs)
        all_in_inventory = self._consume_ingredients(event, needed, recipe_kept(recipe), cs)
        for res in produced:
            self._place_result(event, res, all_in_inventory)
            cs.constructed.add(res.id.upper())

        names = [
            cs.entities_by_id[i].name if i in cs.entities_by_id and cs.entities_by_id[i].name else i
            for i in sorted(needed)
        ]
        created = ", ".join(res.name or res.id for res in produced)
        meta = dict(recipe.metadata_json or {})
        # The adventure's own success text replaces the default message.
        success_text = str(meta.get("on_craft_success_text") or "").strip()
        cs.messages.append(success_text or f"You combine {', '.join(names)} to create {created}!")
        if meta.get("on_craft_success_script"):
            cs.messages += await self.manager._execute_inline_script(
                meta["on_craft_success_script"], "on_craft_success", recipe.id
            )
        logger.info(
            "[Turn %s] Recipe '%s' crafted %s from ingredients %s",
            self.game_id,
            recipe.id,
            [res.id for res in produced],
            sorted(needed),
        )

    async def _try_craft(
        self, event: GameEvent, recipes: list[WorldEntity], cs: CraftingState
    ) -> None:
        for recipe in recipes:
            needed = recipe_ingredients(recipe)
            if not self._is_craftable(recipe, needed, cs):
                continue
            granted = _granted_by_gm(event, recipe_results(recipe))
            if not granted and not self._ingredient_referenced(needed, cs):
                continue
            blocked = await self._craft_guard_blocks(recipe)
            if blocked is not None:
                cs.messages += blocked
                continue
            await self._craft(event, recipe, needed, cs)

    @staticmethod
    def _resolve_craft_refs(raw_args: str, cs: CraftingState) -> set[str]:
        """Upper-case entity ids for the ``A | B`` references of ``/craft`` (ids or names)."""
        by_name = {
            ent.name.strip().upper(): eid for eid, ent in cs.entities_by_id.items() if ent.name
        }
        refs = {part.strip().upper() for part in raw_args.split("|") if part.strip()}
        return {ref if ref in cs.entities_by_id else by_name.get(ref, ref) for ref in refs}

    async def _craft_selected(self, raw_args: str) -> tuple[list[str], list[str]]:
        """Deterministic crafting from the combine panel (``/craft A | B``), without the GM.

        The chosen items must be reachable and exactly the ingredients of a recipe with
        results left to craft. Nothing is consumed on a miss. Returns the crafting messages
        (unsaved; the caller persists them) and the messages of the applied state changes
        (already stored).
        """
        entities = await self._session_entities()
        cs = self._crafting_state(entities, "")
        selected = self._resolve_craft_refs(raw_args, cs)
        if len(selected) < MIN_INGREDIENTS:
            return [CRAFT_TOO_FEW_MESSAGE], []
        if not selected.issubset(cs.accessible_ids):
            return [CRAFT_UNREACHABLE_MESSAGE], []

        match = next(
            (
                ent
                for ent in entities
                if ent.id
                and is_recipe(ent)
                and recipe_ingredients(ent) == selected
                and self._is_craftable(ent, selected, cs)
            ),
            None,
        )
        if match is None:
            return [CRAFT_NO_MATCH_MESSAGE], []

        blocked = await self._craft_guard_blocks(match)
        if blocked is not None:
            return blocked, []

        event = GameEvent()
        await self._craft(event, match, selected, cs)
        applied = await self.manager._apply_game_event(event)
        return cs.messages, applied

    @staticmethod
    def _violation(
        kind: str, res: WorldEntity | None, recipe: WorldEntity | None, cid: str, fallback: str
    ) -> str:
        name = res.name if res else fallback
        ingredients = ", ".join(sorted(recipe_ingredients(recipe))) if recipe else ""
        actions = {
            "inventory": "add crafted item '{name}' ({cid}) to inventory",
            "spawn": "spawn crafted item '{name}' ({cid}) in scene",
            "reveal": "reveal crafted item '{name}' ({cid})",
        }
        action = actions[kind].format(name=name, cid=cid)
        return f"Rule Violation: Attempted to {action} without combining its ingredients: {ingredients or 'unknown'}."

    @staticmethod
    def _strip_items(items: list, cid: str, kind: str | None, report: Reporter) -> list:
        """Removes ``cid`` from a GM item list, reporting a violation if ``kind`` is set."""
        kept = []
        for item in items:
            if item_id_upper(item) != cid:
                kept.append(item)
            elif kind:
                report(kind, item.name)
        return kept

    @staticmethod
    def _strip_entity_changes(event: GameEvent, cid: str, report: Reporter) -> None:
        def matches(entity_id: str | None) -> bool:
            return bool(entity_id) and entity_id.upper() == cid

        if event.updated_entities:
            for up in event.updated_entities:
                if matches(up.entity_id) and up.is_hidden is False:
                    report("reveal", up.entity_id)
            event.updated_entities = [
                up for up in event.updated_entities if not matches(up.entity_id)
            ]
        if event.moved_entities:
            event.moved_entities = [m for m in event.moved_entities if not matches(m.entity_id)]

    def _revert_illegal(self, event: GameEvent, cid: str, report: Reporter) -> None:
        """Drops every GM change that would bring ``cid`` into the world."""
        if event.new_inventory_items:
            event.new_inventory_items = self._strip_items(
                event.new_inventory_items, cid, "inventory", report
            )
        if event.updated_inventory_items:
            event.updated_inventory_items = self._strip_items(
                event.updated_inventory_items, cid, None, report
            )
        if event.spawned_items:
            event.spawned_items = self._strip_items(event.spawned_items, cid, "spawn", report)
        self._strip_entity_changes(event, cid, report)

    def _result_reporter(
        self, res: WorldEntity, recipe: WorldEntity | None, cid: str, cs: CraftingState
    ) -> Reporter:
        def report(kind: str, fallback: str) -> None:
            cs.messages.append(self._violation(kind, res, recipe, cid, fallback))

        return report

    def _revert_uncrafted(
        self,
        event: GameEvent,
        entities: list[WorldEntity],
        recipes: list[WorldEntity],
        cs: CraftingState,
    ) -> None:
        """Recipes never enter the world; hidden craft-only results only through crafting."""
        recipe_of = {rid: recipe for recipe in recipes for rid in recipe_results(recipe)}
        for rid in sorted(craft_only_result_ids(entities) - cs.constructed):
            res = cs.entities_by_id.get(rid)
            if res is None or not self._is_hidden_now(res):
                continue
            self._revert_illegal(
                event, rid, self._result_reporter(res, recipe_of.get(rid), rid, cs)
            )
        for recipe in recipes:
            self._revert_illegal(event, recipe.id.upper(), _ignore)

    async def _enforce_constructable_combination(
        self, event: GameEvent, user_msg: str
    ) -> list[str]:
        """Crafts recipes on a combine action and reverts results the GM produced without crafting."""
        entities = await self._session_entities()
        recipes = [e for e in entities if e.id and is_recipe(e)]
        if not recipes:
            return []
        lowered = (user_msg or "").strip().lower()
        cs = self._crafting_state(entities, lowered)
        if lowered and event.combination_intent:
            await self._try_craft(event, recipes, cs)
        self._revert_uncrafted(event, entities, recipes, cs)
        return cs.messages
