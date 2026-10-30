"""Hidden entity reveal: hidden things in the scene appear once they are discovered."""

from __future__ import annotations

import logging

from pydantic import BaseModel

from backend.api.routes.adventures.guardrails.base import item_id_upper
from backend.api.routes.adventures.logic import AdventureLogic
from backend.core.prompts import HIDDEN_ENTITY_DISCOVERY_SYSTEM_PROMPT
from backend.engine.rules.crafting_recipes import (
    craft_only_result_ids,
    is_recipe,
    used_up_ingredient_ids,
)
from backend.engine.rules.rule_engine import GameEvent
from backend.models.world_entity import WorldEntity

logger = logging.getLogger(__name__)


class DiscoveryCheckResponse(BaseModel):
    discovered: bool


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
            and e.id.upper() not in never
            and self._is_entity_hidden_now(e)
        ]

    async def _llm_says_discovered(self, ent: WorldEntity, user_msg: str, narration: str) -> bool:
        """Language-agnostic fallback: asks the small model whether the turn discovered the entity."""
        try:
            llm, model = self._small_llm()
            res = await llm.aexecute_complex_task(
                system_prompt=HIDDEN_ENTITY_DISCOVERY_SYSTEM_PROMPT,
                user_prompt=(
                    f"Hidden Entity ID: {ent.id}\n"
                    f"Hidden Entity Name: {ent.name}\n"
                    f"Entity Hidden At/Reveal Rule: {ent.spatial_position or ''} {ent.reveal_rule or ''}\n"
                    f'Player Message: "{user_msg}"\n'
                    f'Game Master Narration: "{narration}"'
                ),
                model=model,
                response_model=DiscoveryCheckResponse,
            )
        except Exception as exc:
            logger.error("Error checking hidden entity discovery with LLM: %s", exc)
            return False
        if isinstance(res, DiscoveryCheckResponse):
            return res.discovered
        return bool(res.get("discovered", False)) if isinstance(res, dict) else False

    async def _should_reveal(
        self,
        event: GameEvent,
        ent: WorldEntity,
        by_id: dict[str, WorldEntity],
        user_msg: str,
        narration: str,
    ) -> bool:
        discovered = {
            str(e).strip().upper() for e in getattr(event, "discovered_entity_ids", []) or []
        }
        if ent.id.upper() in discovered:
            return True
        if _named(event.spawned_items, ent) or _named(event.new_inventory_items, ent):
            return True
        if _parent_reveals(event, ent, by_id):
            return True
        if not (user_msg or narration):
            return False
        return await self._llm_says_discovered(ent, user_msg, narration)

    async def _enforce_hidden_entity_reveal(
        self, event: GameEvent, user_msg: str, draft_narration: str = ""
    ) -> list[str]:
        """Auto-reveals hidden entities in the current scene that this turn discovered."""
        entities = await self._session_entities()
        hidden = self._hidden_scene_entities(entities)
        if not hidden:
            return []
        by_id = {e.id: e for e in entities if e.id}
        revealed: list[str] = []
        for ent in hidden:
            already = any(
                (up.entity_id or "").upper() == ent.id.upper() and up.is_hidden is False
                for up in event.updated_entities or []
            )
            if already or not await self._should_reveal(
                event, ent, by_id, user_msg, draft_narration
            ):
                continue
            self._upsert_entity_update(event, ent.id, is_hidden=False)
            revealed.append(f"Revealed {ent.name}")
            logger.info(
                "[Turn %s] Auto-revealed hidden entity '%s' (%s) in scene '%s'",
                self.game_id,
                ent.id,
                ent.name,
                self.state.current_scene_id,
            )
        return revealed
