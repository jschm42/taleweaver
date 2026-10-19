"""Deterministic checks that run once a turn has been resolved, right before its final event.

* Special attack unlocks (item / scene / defeated NPC / guard expression rules).
* NPC attack triggers ("attack on sight", configured attack rules, script ``attack()`` calls).

When a hook changes state, the turn's ``final`` SSE payload is refreshed so the client
sees the new sheet and, if an NPC attacked, the combat dialog.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from fastapi.encoders import jsonable_encoder

from backend.api.routes.adventures.combat.context import system_event
from backend.api.routes.adventures.logic import AdventureLogic

if TYPE_CHECKING:
    from backend.api.routes.adventures.gameplay_logic import GameTurnManager

logger = logging.getLogger(__name__)

FINAL_PREFIX = "event: final\ndata: "


def _parse_final(chunk: str) -> dict[str, Any] | None:
    if not chunk.startswith(FINAL_PREFIX):
        return None
    try:
        data = json.loads(chunk[len(FINAL_PREFIX) :].strip())
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


class PostTurnHooks:
    """Runs unlock and NPC aggression checks for one turn."""

    def __init__(self, manager: GameTurnManager) -> None:
        self.manager = manager

    def _ready(self) -> bool:
        m = self.manager
        return bool(
            getattr(m, "state", None)
            and getattr(m, "avatar", None)
            and getattr(m, "adventure", None)
        )

    async def _collect_messages(self) -> list[str]:
        combat = self.manager.combat
        messages = await combat.check_special_unlocks()
        attack_msg = await combat.check_npc_attack_triggers()
        if attack_msg:
            messages.append(attack_msg)
        return messages

    async def process_final(self, chunk: str) -> AsyncGenerator[str, None]:
        """Yields hook messages followed by the (possibly refreshed) final event."""
        data = _parse_final(chunk)
        if data is None or not self._ready():
            yield chunk
            return
        try:
            messages = await self._collect_messages()
        except Exception:
            logger.exception("[Turn %s] Post-turn hooks failed", self.manager.game_id)
            yield chunk
            return
        if not messages:
            yield chunk
            return

        for msg in messages:
            yield system_event(msg)
        yield await self._refreshed_final(data)

    async def _refreshed_final(self, data: dict[str, Any]) -> str:
        m = self.manager
        await m.db.commit()
        combat_snap = AdventureLogic.get_combat_snapshot(m.state)
        data.update(
            {
                "sheet": await AdventureLogic.build_sheet_snapshot(m.avatar, m.state, m.db),
                "entities": await AdventureLogic.build_session_entities(m.db, m.state),
                "combat": combat_snap
                if combat_snap and combat_snap.get("active")
                else data.get("combat"),
            }
        )
        return f"{FINAL_PREFIX}{json.dumps(jsonable_encoder(data))}\n\n"
