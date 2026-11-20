"""Inventory removals: the GM may only take items away that the player's action is about.

The Game Master sometimes lists items in ``removed_inventory_item_ids`` that the player never
gave away, dropped or used (e.g. after an engine-handled handover it "re-books" the transfer
and picks the wrong item). A removal survives only when the item is actually carried and the
player's message refers to it by ID, name, synonym or translation.

Engine reaction turns (``[ITEM_GIVEN]``, ``[ITEM_PICKUP]``, ``[TALENT_USED]``,
``[SEQUENCE_START]`` ...) carry no player wording: there a removal needs the item's exact ID or
name in the prompt, and no small-model check runs. Crafting adds its ingredient removals
afterwards, so this guard runs before it.

Quest items (``metadata_json.quest_item``) are never removed by the GM: the removal is
dropped and reported as a rule violation, so the narration keeps the item with the player.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from backend.engine.rules.quest_items import quest_item_ids
from backend.engine.rules.rule_engine import GameEvent

logger = logging.getLogger(__name__)

_ENGINE_PROMPT = re.compile(r"^\s*\[[A-Z_]+\]")


def _find_carried(ref: str, inventory: list[Any] | None) -> dict | None:
    """The carried item a removal reference points at, matched by ID or name."""
    needle = (ref or "").strip()
    if not needle:
        return None
    for item in inventory or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("id") or "").strip().upper() == needle.upper():
            return item
        if str(item.get("name") or "").strip().lower() == needle.lower():
            return item
    return None


class InventoryRemovalGuardMixin:
    """Drops GM inventory removals the player's action does not account for."""

    async def _removal_is_referenced(
        self, item: dict, lowered_msg: str, allow_llm_check: bool
    ) -> bool:
        item_id = str(item.get("id") or "").strip()
        name = str(item.get("name") or "").strip()
        if item_id and item_id.lower() in lowered_msg:
            return True
        if name and name.lower() in lowered_msg:
            return True
        if not allow_llm_check or not name:
            return False
        return await self._llm_says_referenced(item_id, name, lowered_msg)  # type: ignore[attr-defined]

    async def _enforce_inventory_removals(self, event: GameEvent, user_msg: str) -> list[str]:
        """Keeps only removals of carried items the player's message refers to.

        Dropped over-reaching removals are only logged (the player did nothing wrong). Quest
        items are kept too and returned as violations, so Pass 2 narrates that they stay.
        """
        if not event.removed_inventory_item_ids:
            return []
        violations = await self._keep_quest_items(event)
        message = user_msg or ""
        lowered_msg = message.lower()
        allow_llm_check = not _ENGINE_PROMPT.match(message)
        inventory = self.avatar.inventory  # type: ignore[attr-defined]
        kept: list[str] = []
        for ref in event.removed_inventory_item_ids:
            item = _find_carried(ref, inventory)
            if item is None or not await self._removal_is_referenced(
                item, lowered_msg, allow_llm_check
            ):
                logger.warning(
                    "[Turn %s] Dropped GM inventory removal %r: not carried or not part of "
                    "the player's action.",
                    self.game_id,  # type: ignore[attr-defined]
                    ref,
                )
                continue
            item_id = str(item.get("id") or ref)
            if item_id not in kept:
                kept.append(item_id)
        event.removed_inventory_item_ids = kept
        return violations

    async def _keep_quest_items(self, event: GameEvent) -> list[str]:
        """Drops GM removals of carried quest items; one violation per kept item."""
        inventory = self.avatar.inventory  # type: ignore[attr-defined]
        carried = {
            ref: item
            for ref in event.removed_inventory_item_ids or []
            if (item := _find_carried(ref, inventory)) is not None
        }
        if not carried:
            return []
        quest_ids = await quest_item_ids(
            self.db,  # type: ignore[attr-defined]
            self.state.session_id,  # type: ignore[attr-defined]
            (str(item.get("id") or "") for item in carried.values()),
        )
        violations: list[str] = []
        remaining: list[str] = []
        for ref in event.removed_inventory_item_ids or []:
            item = carried.get(ref)
            if item is None or str(item.get("id") or "").upper() not in quest_ids:
                remaining.append(ref)
                continue
            name = str(item.get("name") or item.get("id"))
            violations.append(
                f"{name} is a quest item: the player keeps it. It cannot be given away, "
                "sold, lost or used up."
            )
        event.removed_inventory_item_ids = remaining
        return violations
