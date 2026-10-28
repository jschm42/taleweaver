"""CONSTRUCTABLE items: deterministic crafting and blocking of illegal spawns/reveals.

A CONSTRUCTABLE is a hidden object that materializes when the player combines ALL of its
``combination_ingredients`` (minimum 2). Crafting requires the GM's ``combination_intent``
(set by the LLM in any language), every ingredient to be reachable, and at least one
ingredient to be referenced (or the GM granting the result directly).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from backend.api.routes.adventures.guardrails.base import item_id_upper
from backend.engine.rule_engine import GameEvent, InventoryItem
from backend.engine.switch_service import SwitchService
from backend.models.world_entity import WorldEntity

logger = logging.getLogger(__name__)

MIN_INGREDIENTS = 2
MIN_TOKEN_LENGTH = 3
CRAFT_TOO_FEW_MESSAGE = "Choose at least two items to combine."
CRAFT_UNREACHABLE_MESSAGE = "You can only combine items you carry or that are here with you."
CRAFT_NO_MATCH_MESSAGE = "You try to combine them, but nothing comes of it."


@dataclass
class CraftingState:
    """Per-turn crafting bookkeeping."""

    lowered_msg: str
    entities_by_id: dict[str, WorldEntity]
    inventory_ids: dict[str, str]  # upper id -> original id (for removal)
    accessible_ids: set[str]
    consumed: set[str] = field(default_factory=set)
    constructed: set[str] = field(default_factory=set)
    messages: list[str] = field(default_factory=list)


def _ingredients(ent: WorldEntity) -> set[str]:
    return {
        str(i).strip().upper() for i in ent.combination_ingredients or [] if i and str(i).strip()
    }


def _granted_by_gm(event: GameEvent, entity_id: str) -> bool:
    items = [*(event.new_inventory_items or []), *(event.spawned_items or [])]
    return any(item_id_upper(item) == entity_id.upper() for item in items)


class CraftingGuardMixin:
    """Resolves crafting and reverts constructables the GM produced without crafting."""

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

    def _is_hidden_now(self, ent: WorldEntity) -> bool:
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

    def _is_craftable(self, ent: WorldEntity, needed: set[str], cs: CraftingState) -> bool:
        if len(needed) < MIN_INGREDIENTS or ent.id.upper() in cs.consumed:
            return False
        if not self._is_hidden_now(ent) or needed & cs.consumed:
            return False
        return needed.issubset(cs.accessible_ids)

    async def _craft_guard_blocks(self, ent: WorldEntity) -> list[str] | None:
        """Runs the craft guard expression; returns failure messages or None when allowed."""
        meta = dict(ent.metadata_json or {})
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
                meta["on_craft_failure_script"], "on_craft_failure", ent.id
            )
        fail_text = str(
            meta.get("on_craft_failure_text")
            or detail
            or f"You cannot construct {ent.name} right now."
        )
        await self._save_chat_message("system", fail_text)
        return [*messages, fail_text]

    def _consume_ingredients(self, event: GameEvent, needed: set[str], cs: CraftingState) -> bool:
        """Removes inventory ingredients / hides scene ingredients. True if all came from the inventory."""
        all_in_inventory = True
        for ingredient in needed:
            if ingredient in cs.inventory_ids:
                event.removed_inventory_item_ids = event.removed_inventory_item_ids or []
                original = cs.inventory_ids[ingredient]
                if original not in event.removed_inventory_item_ids:
                    event.removed_inventory_item_ids.append(original)
            else:
                self._upsert_entity_update(event, ingredient, is_hidden=True)
                all_in_inventory = False
            cs.consumed.add(ingredient)
        return all_in_inventory

    async def _craft(
        self, event: GameEvent, ent: WorldEntity, needed: set[str], cs: CraftingState
    ) -> None:
        all_in_inventory = self._consume_ingredients(event, needed, cs)
        self._upsert_entity_update(event, ent.id, is_hidden=False)
        self._upsert_entity_movement(event, ent.id, self.state.current_scene_id)
        if all_in_inventory:
            event.new_inventory_items = event.new_inventory_items or []
            if not any(i.id == ent.id for i in event.new_inventory_items):
                event.new_inventory_items.append(
                    InventoryItem(
                        id=ent.id,
                        name=ent.name or "Unknown Item",
                        description=ent.description,
                        item_type=ent.item_type,
                        image_url=ent.image_url,
                    )
                )
        cs.constructed.add(ent.id.upper())

        names = [
            cs.entities_by_id[i].name if i in cs.entities_by_id and cs.entities_by_id[i].name else i
            for i in needed
        ]
        cs.messages.append(f"You combine {', '.join(names)} to create {ent.name}!")
        meta = dict(ent.metadata_json or {})
        if meta.get("on_craft_success_script"):
            cs.messages += await self.manager._execute_inline_script(
                meta["on_craft_success_script"], "on_craft_success", ent.id
            )
        if meta.get("on_craft_success_text"):
            await self._save_chat_message("system", meta["on_craft_success_text"])
            cs.messages.append(meta["on_craft_success_text"])
        logger.info(
            "[Turn %s] CONSTRUCTABLE '%s' materialized from ingredients %s",
            self.game_id,
            ent.id,
            sorted(needed),
        )

    async def _try_craft(
        self, event: GameEvent, constructables: list[WorldEntity], cs: CraftingState
    ) -> None:
        for ent in constructables:
            needed = _ingredients(ent)
            if not self._is_craftable(ent, needed, cs):
                continue
            if not self._ingredient_referenced(needed, cs) and not _granted_by_gm(event, ent.id):
                continue
            blocked = await self._craft_guard_blocks(ent)
            if blocked is not None:
                cs.messages += blocked
                continue
            await self._craft(event, ent, needed, cs)

    @staticmethod
    def _resolve_craft_refs(raw_args: str, cs: CraftingState) -> set[str]:
        """Upper-case entity ids for the ``A | B`` references of ``/craft`` (ids or names)."""
        by_name = {
            ent.name.strip().upper(): eid for eid, ent in cs.entities_by_id.items() if ent.name
        }
        refs = {part.strip().upper() for part in raw_args.split("|") if part.strip()}
        return {ref if ref in cs.entities_by_id else by_name.get(ref, ref) for ref in refs}

    async def _craft_selected(self, raw_args: str) -> tuple[str, list[str]]:
        """Deterministic crafting from the combine panel (``/craft A | B``), without the GM.

        The chosen items must be reachable and exactly the ingredients of a hidden constructable.
        Nothing is consumed on a miss. Returns the response text (persisted by the caller) and
        further messages that are already stored (scripts, success or failure texts).
        """
        entities = await self._session_entities()
        cs = self._crafting_state(entities, "")
        selected = self._resolve_craft_refs(raw_args, cs)
        if len(selected) < MIN_INGREDIENTS:
            return CRAFT_TOO_FEW_MESSAGE, []
        if not selected.issubset(cs.accessible_ids):
            return CRAFT_UNREACHABLE_MESSAGE, []

        match = next(
            (
                ent
                for ent in entities
                if ent.id
                and str(ent.item_type or "").upper() == "CONSTRUCTABLE"
                and _ingredients(ent) == selected
                and self._is_craftable(ent, selected, cs)
            ),
            None,
        )
        if match is None:
            return CRAFT_NO_MATCH_MESSAGE, []

        blocked = await self._craft_guard_blocks(match)
        if blocked is not None:
            return "", blocked

        event = GameEvent()
        await self._craft(event, match, selected, cs)
        applied = await self.manager._apply_game_event(event)
        response, *extra = cs.messages
        return response, [*extra, *applied]

    @staticmethod
    def _violation(kind: str, ent: WorldEntity | None, cid: str, fallback_name: str) -> str:
        name = ent.name if ent else fallback_name
        ingredients = ", ".join(ent.combination_ingredients or []) if ent else ""
        actions = {
            "inventory": "add constructable item '{name}' ({cid}) to inventory",
            "spawn": "spawn constructable item '{name}' ({cid}) in scene",
            "reveal": "reveal constructable entity '{name}' ({cid})",
        }
        action = actions[kind].format(name=name, cid=cid)
        return f"Rule Violation: Attempted to {action} without combining its ingredients: {ingredients or 'unknown'}."

    def _strip_items(
        self, items: list, cid: str, ent: WorldEntity | None, kind: str | None, messages: list[str]
    ) -> list:
        """Removes the constructable from a GM item list, recording a violation if ``kind`` is set."""
        kept = []
        for item in items:
            if item_id_upper(item) != cid:
                kept.append(item)
            elif kind:
                messages.append(self._violation(kind, ent, cid, item.name))
        return kept

    def _strip_entity_changes(
        self, event: GameEvent, cid: str, ent: WorldEntity | None, messages: list[str]
    ) -> None:
        def is_constructable(entity_id: str | None) -> bool:
            return bool(entity_id) and entity_id.upper() == cid

        if event.updated_entities:
            for up in event.updated_entities:
                if is_constructable(up.entity_id) and up.is_hidden is False:
                    messages.append(self._violation("reveal", ent, cid, up.entity_id))
            event.updated_entities = [
                up for up in event.updated_entities if not is_constructable(up.entity_id)
            ]
        if event.moved_entities:
            event.moved_entities = [
                m for m in event.moved_entities if not is_constructable(m.entity_id)
            ]

    def _revert_illegal_constructable(
        self, event: GameEvent, cid: str, ent: WorldEntity | None, messages: list[str]
    ) -> None:
        if event.new_inventory_items:
            event.new_inventory_items = self._strip_items(
                event.new_inventory_items, cid, ent, "inventory", messages
            )
        if event.updated_inventory_items:
            event.updated_inventory_items = self._strip_items(
                event.updated_inventory_items, cid, ent, None, messages
            )
        if event.spawned_items:
            event.spawned_items = self._strip_items(
                event.spawned_items, cid, ent, "spawn", messages
            )
        self._strip_entity_changes(event, cid, ent, messages)

    async def _enforce_constructable_combination(
        self, event: GameEvent, user_msg: str
    ) -> list[str]:
        """Crafts constructables on a combine action and reverts any the GM produced without crafting."""
        entities = await self._session_entities()
        constructables = [
            e for e in entities if e.id and str(e.item_type or "").upper() == "CONSTRUCTABLE"
        ]
        if not constructables:
            return []
        lowered = (user_msg or "").strip().lower()
        cs = self._crafting_state(entities, lowered)
        if lowered and event.combination_intent:
            await self._try_craft(event, constructables, cs)

        by_id = {e.id.upper(): e for e in constructables}
        for cid, ent in by_id.items():
            if cid not in cs.constructed:
                self._revert_illegal_constructable(event, cid, ent, cs.messages)
        return cs.messages
