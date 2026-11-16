"""Recovers handovers that Pass 1 booked as plain removals.

Pass 1 should report a handover in ``given_items``, but small models sometimes only list the
item in ``removed_inventory_item_ids`` ("Tina snatches the drink"). The item would then vanish
and the character's ``on_receive_item`` trigger never run. After the removal guard kept a
removal (carried item the player's message refers to), and when characters stand in the scene,
one small-model call decides for all removed items whether the player handed them to one of
those characters. Confirmed ones become handovers; the rest stay removals (eaten, dropped,
used up ...). Language-agnostic: the model judges the action, no keyword lists.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from backend.api.routes.adventures.guardrails.removals import _find_carried
from backend.engine.rules.rule_engine import GameEvent, ItemHandover

logger = logging.getLogger(__name__)

HANDOVER_CHECK_SYSTEM_PROMPT = (
    "You check a text adventure turn. The game removed the listed items from the player's "
    "inventory. For each item decide whether the player handed it to one of the listed "
    "characters this turn: gives it, offers it and the character takes it, tosses it to "
    "them, pays them with it. The player's message may be in any language and may be "
    "dialogue. Items the player eats, drinks, uses up, drops, destroys or puts somewhere are "
    "NOT handovers. Return only clear handovers as {item_id, npc_id} with the exact IDs "
    "given; return an empty list when unsure."
)


class HandoverCheckResponse(BaseModel):
    handovers: list[ItemHandover] = Field(default_factory=list)


def _user_prompt(user_msg: str, draft: str, items: list[dict], npcs: list[Any]) -> str:
    item_lines = "\n".join(f"- {i.get('id')}: {i.get('name')}" for i in items)
    npc_lines = "\n".join(f"- {n.id}: {n.name}" for n in npcs)
    return (
        f'Player message: "{user_msg}"\n'
        f'Game master draft of what happened: "{draft}"\n'
        f"Removed items:\n{item_lines}\n"
        f"Characters in the scene:\n{npc_lines}"
    )


class HandoverRecoveryMixin:
    """Turns removals that were really handovers into ``given_items``."""

    async def _handover_candidates(
        self, event: GameEvent, user_msg: str
    ) -> tuple[list[dict], list[Any]]:
        """(removed carried items, characters who could receive them); empty when not needed."""
        if not event.removed_inventory_item_ids or self._skip_handovers(user_msg):  # type: ignore[attr-defined]
            return [], []
        inventory = self.avatar.inventory  # type: ignore[attr-defined]
        items = [i for r in event.removed_inventory_item_ids if (i := _find_carried(r, inventory))]
        npcs = [
            npc
            for npc in await self.manager.combat._scene_npcs()  # type: ignore[attr-defined]
            if not self.manager._is_npc_defeated(npc)  # type: ignore[attr-defined]
        ]
        return (items, npcs) if items and npcs else ([], [])

    async def _ask_handovers(
        self, user_msg: str, draft: str, items: list[dict], npcs: list[Any]
    ) -> list[ItemHandover]:
        try:
            llm, model = self._small_llm()  # type: ignore[attr-defined]
            res = await llm.aexecute_complex_task(
                system_prompt=HANDOVER_CHECK_SYSTEM_PROMPT,
                user_prompt=_user_prompt(user_msg, draft, items, npcs),
                model=model,
                response_model=HandoverCheckResponse,
            )
        except Exception as exc:
            # Fail safe: without an answer the removals stay as they are.
            logger.error("Handover check failed: %s", exc)
            return []
        if isinstance(res, HandoverCheckResponse):
            return res.handovers
        return HandoverCheckResponse.model_validate(res).handovers if isinstance(res, dict) else []

    async def _recover_handovers_from_removals(self, event: GameEvent, user_msg: str) -> None:
        """Moves removals the small model confirms as handovers into ``given_items``."""
        items, npcs = await self._handover_candidates(event, user_msg)
        if not items:
            return
        answers = await self._ask_handovers(user_msg, event.narrative_description, items, npcs)
        item_ids = {str(i.get("id") or "").upper() for i in items}
        npc_ids = {str(n.id).upper(): str(n.id) for n in npcs}
        recovered = [
            ItemHandover(item_id=str(a.item_id).upper(), npc_id=npc_ids[str(a.npc_id).upper()])
            for a in answers
            if str(a.item_id).upper() in item_ids and str(a.npc_id).upper() in npc_ids
        ]
        if not recovered:
            return
        handed = {h.item_id for h in recovered}
        known = {h.item_id.upper() for h in event.given_items or []}
        event.given_items = [
            *(event.given_items or []),
            *(h for h in recovered if h.item_id not in known),
        ]
        inventory = self.avatar.inventory  # type: ignore[attr-defined]
        event.removed_inventory_item_ids = [
            ref
            for ref in event.removed_inventory_item_ids or []
            if str((_find_carried(ref, inventory) or {}).get("id") or ref).upper() not in handed
        ]
        logger.info("[Turn %s] Removals recovered as handovers: %s", self.game_id, recovered)  # type: ignore[attr-defined]
