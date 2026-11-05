"""Hidden entity reveal: hidden things in the scene appear once they are discovered."""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from backend.api.routes.adventures.guardrails.base import item_id_upper
from backend.api.routes.adventures.logic import AdventureLogic
from backend.core.prompts import HIDDEN_ENTITY_DISCOVERY_SYSTEM_PROMPT
from backend.engine.rules.crafting_recipes import (
    craft_only_result_ids,
    is_recipe,
    used_up_ingredient_ids,
)
from backend.engine.rules.reveal_policy import entity_is_script_only
from backend.engine.rules.rule_engine import GameEvent
from backend.models.world_entity import WorldEntity

logger = logging.getLogger(__name__)


class DiscoveryCheckResponse(BaseModel):
    discovered_ids: list[str] = Field(default_factory=list)


def _named(items, ent: WorldEntity) -> bool:
    """True when one of the GM's items is this entity (by ID or exact name)."""
    name = (ent.name or "").strip().lower()
    for item in items or []:
        item_name = str(getattr(item, "name", "") or "").strip().lower()
        if item_id_upper(item) == ent.id.upper() or (item_name and item_name == name):
            return True
    return False


def _parent_reveals(event: GameEvent, ent: WorldEntity, by_id: dict[str, WorldEntity]) -> bool:
    """True when an entity updated this turn reveals or hides this one (``reveals_item_id`` / ``##PARENT`` tags)."""
    position = str(ent.spatial_position or "").upper()
    rule = str(ent.reveal_rule or "").upper()
    for up in event.updated_entities or []:
        if not up.entity_id:
            continue
        parent = by_id.get(up.entity_id)
        if (
            parent
            and parent.reveals_item_id
            and parent.reveals_item_id.strip().upper() == ent.id.upper()
        ):
            return True
        tag = f"##{up.entity_id.upper()}"
        if tag in position or tag in rule or up.entity_id.upper() in position:
            return True
    return False


class RevealGuardMixin:
    """Reveals hidden scene entities that the turn discovered."""

    def _is_entity_hidden_now(self, ent: WorldEntity) -> bool:
        override = (self.state.entity_states or {}).get(ent.id, {})
        if override.get("is_hidden") is not None:
            return bool(override["is_hidden"])
        return bool(ent.is_hidden)

    def _hidden_scene_entities(self, entities: list[WorldEntity]) -> list[WorldEntity]:
        """Hidden scene entities that may be discovered.

        Never: recipes, craft-only results, and ingredients a crafting already used up.
        """
        contained = AdventureLogic.collect_container_item_ids(
            [{"item_type": e.item_type, "inventory": e.inventory} for e in entities]
        )
        never = craft_only_result_ids(entities) | used_up_ingredient_ids(
            entities, self._is_entity_hidden_now
        )
        return [
            e
            for e in entities
            if e.id
            and e.current_scene_id == self.state.current_scene_id
            and not getattr(e, "is_in_inventory", False)
            and str(e.id) not in contained
            and not is_recipe(e)
            and not entity_is_script_only(e)
            and e.id.upper() not in never
            and self._is_entity_hidden_now(e)
        ]

    async def _block_script_only_reveals(self, event: GameEvent) -> list[str]:
        """Drops Game Master reveals of entities whose reveal rule is ``script``.

        Runs before the deterministic guardrails (crafting, ``reveals_item_id``), so only
        reveals the Game Master proposed are affected; scripts apply their changes directly.
        """
        if not event.updated_entities and not event.discovered_entity_ids:
            return []
        script_only = {
            e.id.upper()
            for e in await self._session_entities()
            if e.id and entity_is_script_only(e)
        }
        if not script_only:
            return []
        event.discovered_entity_ids = [
            eid for eid in event.discovered_entity_ids or [] if str(eid).upper() not in script_only
        ] or None
        for update in event.updated_entities or []:
            if update.is_hidden is False and (update.entity_id or "").upper() in script_only:
                update.is_hidden = None
                logger.info(
                    "[Turn %s] Blocked GM reveal of script-only entity '%s'",
                    self.game_id,
                    update.entity_id,
                )
        return []

    async def _llm_discovered_ids(
        self, candidates: list[WorldEntity], user_msg: str, narration: str
    ) -> set[str]:
        """Language-agnostic fallback: one small-model call for all candidates of the turn."""
        listing = "\n".join(
            f"- ID: {ent.id} | Name: {ent.name} | Hidden at / reveal rule: "
            f"{ent.spatial_position or ''} {ent.reveal_rule or ''}".rstrip()
            for ent in candidates
        )
        try:
            llm, model = self._small_llm()
            res = await llm.aexecute_complex_task(
                system_prompt=HIDDEN_ENTITY_DISCOVERY_SYSTEM_PROMPT,
                user_prompt=(
                    f"Hidden entities:\n{listing}\n"
                    f'Player Message: "{user_msg}"\n'
                    f'Game Master Narration: "{narration}"'
                ),
                model=model,
                response_model=DiscoveryCheckResponse,
            )
        except Exception as exc:
            logger.error("Error checking hidden entity discovery with LLM: %s", exc)
            return set()
        ids = res.discovered_ids if isinstance(res, DiscoveryCheckResponse) else None
        if ids is None and isinstance(res, dict):
            ids = res.get("discovered_ids")
        candidate_ids = {ent.id.upper() for ent in candidates}
        return {str(i).strip().upper() for i in ids or []} & candidate_ids

    @staticmethod
    def _deterministic_reveal(
        event: GameEvent, ent: WorldEntity, by_id: dict[str, WorldEntity]
    ) -> bool:
        """The turn itself names the entity: GM discovery, item handout or a parent update."""
        discovered = {
            str(e).strip().upper() for e in getattr(event, "discovered_entity_ids", []) or []
        }
        if ent.id.upper() in discovered:
            return True
        if _named(event.spawned_items, ent) or _named(event.new_inventory_items, ent):
            return True
        return _parent_reveals(event, ent, by_id)

    def _is_movement_turn(self, event: GameEvent, moved: bool) -> bool:
        """Leaving or entering a scene discovers nothing hidden there: no small-model check.

        ``moved``: the caller knows the scene changed this turn; ``arrival_narration``: the
        narration of an exit traversal; ``new_scene_id``: the GM moves the player this turn.
        """
        if moved or getattr(self.manager, "arrival_narration", False):
            return True
        target = str(event.new_scene_id or "").strip().upper()
        return bool(target) and target != str(self.state.current_scene_id or "").upper()

    def _reveal(self, event: GameEvent, ent: WorldEntity, revealed: list[str]) -> None:
        self._upsert_entity_update(event, ent.id, is_hidden=False)
        revealed.append(f"Revealed {ent.name}")
        logger.info(
            "[Turn %s] Auto-revealed hidden entity '%s' (%s) in scene '%s'",
            self.game_id,
            ent.id,
            ent.name,
            self.state.current_scene_id,
        )

    async def _enforce_hidden_entity_reveal(
        self, event: GameEvent, user_msg: str, draft_narration: str = "", moved: bool = False
    ) -> list[str]:
        """Auto-reveals hidden entities in the current scene that this turn discovered.

        Deterministic reveals come first; the rest is checked with one small-model call, which
        is skipped on movement turns and when there is no text to check.
        """
        entities = await self._session_entities()
        hidden = self._hidden_scene_entities(entities)
        if not hidden:
            return []
        by_id = {e.id: e for e in entities if e.id}
        revealed: list[str] = []
        candidates: list[WorldEntity] = []
        for ent in hidden:
            already = any(
                (up.entity_id or "").upper() == ent.id.upper() and up.is_hidden is False
                for up in event.updated_entities or []
            )
            if already:
                continue
            if self._deterministic_reveal(event, ent, by_id):
                self._reveal(event, ent, revealed)
                continue
            candidates.append(ent)

        if not candidates or not (user_msg or draft_narration):
            return revealed
        if self._is_movement_turn(event, moved):
            return revealed
        found = await self._llm_discovered_ids(candidates, user_msg, draft_narration)
        for ent in candidates:
            if ent.id.upper() in found:
                self._reveal(event, ent, revealed)
        return revealed
