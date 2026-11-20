"""Item handovers reported by Pass 1 (``given_items``): validated before they happen.

When the player hands a carried item to a character in other words than the ``/give_items``
command (e.g. inside dialogue, in any language), Pass 1 reports ``{item_id, npc_id}``. A
handover survives only when:

* the turn is a player's action (no arrival narration, no engine reaction prompt such as
  ``[ITEM_GIVEN]``),
* the player carries the item and the message refers to it (same rule as removals:
  ID, name, or the small-model synonym/translation check),
* the character stands visible in the current scene and is not defeated.

Valid handovers are taken off ``removed_inventory_item_ids`` and ``moved_entities`` so the item
cannot vanish or be moved twice; ``handover_flow.apply_item_handovers`` then performs them
after the state is applied, with the character's receive trigger. Dropped entries are only
logged: the Game Master over-reached, the player did nothing wrong.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.api.routes.adventures.guardrails.removals import _ENGINE_PROMPT, _find_carried
from backend.engine.rules.rule_engine import GameEvent, ItemHandover

logger = logging.getLogger(__name__)


class ItemHandoverGuardMixin:
    """Validates ``given_items`` and keeps the handed items out of removals and moves."""

    async def _valid_handover(
        self, handover: ItemHandover, lowered_msg: str
    ) -> ItemHandover | None:
        item = _find_carried(handover.item_id, self.avatar.inventory)  # type: ignore[attr-defined]
        if item is None:
            return None
        if not await self._removal_is_referenced(item, lowered_msg, True):  # type: ignore[attr-defined]
            return None
        npc = await self.manager._find_scene_npc_by_hint(handover.npc_id)  # type: ignore[attr-defined]
        if npc is None or self.manager._is_npc_defeated(npc):  # type: ignore[attr-defined]
            return None
        return ItemHandover(item_id=str(item.get("id") or handover.item_id), npc_id=str(npc.id))

    def _skip_handovers(self, user_msg: str) -> bool:
        return bool(getattr(self.manager, "arrival_narration", False)) or bool(  # type: ignore[attr-defined]
            _ENGINE_PROMPT.match(user_msg or "")
        )

    async def _enforce_item_handovers(self, event: GameEvent, user_msg: str) -> list[str]:
        """Keeps the valid handovers (one per item); returns no violations."""
        if not event.given_items:
            return []
        if self._skip_handovers(user_msg):
            event.given_items = []
            return []
        lowered_msg = (user_msg or "").lower()
        valid: list[ItemHandover] = []
        for handover in event.given_items:
            checked = await self._valid_handover(handover, lowered_msg)
            if checked is None or any(v.item_id == checked.item_id for v in valid):
                logger.warning(
                    "[Turn %s] Dropped GM handover %s -> %s: not carried, not part of the "
                    "player's action, or the character is not here.",
                    self.game_id,  # type: ignore[attr-defined]
                    handover.item_id,
                    handover.npc_id,
                )
                continue
            valid.append(checked)
        event.given_items = valid
        _drop_competing_changes(
            event,
            {v.item_id.upper() for v in valid},
            self.avatar.inventory,  # type: ignore[attr-defined]
        )
        return []


def _drop_competing_changes(event: GameEvent, handed: set[str], inventory: Any) -> None:
    """The engine moves handed items itself: no removal or GM move for them."""
    if not handed:
        return
    event.removed_inventory_item_ids = [
        ref
        for ref in event.removed_inventory_item_ids or []
        if not _refers_to(ref, handed, inventory)
    ]
    event.moved_entities = [
        move for move in event.moved_entities or [] if str(move.entity_id).upper() not in handed
    ]


def _refers_to(ref: Any, handed: set[str], inventory: Any) -> bool:
    """Whether a removal reference (ID or name) points at a handed item."""
    item = _find_carried(str(ref or ""), inventory)
    item_id = str(item.get("id") if item else ref or "").strip().upper()
    return item_id in handed
