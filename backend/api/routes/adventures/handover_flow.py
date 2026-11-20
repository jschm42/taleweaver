"""Performs the item handovers that Pass 1 reported and Pass 1.5 validated (``given_items``).

Runs in the turn after the event is applied and the interaction triggers fired, before the
logic-pass scripts and Pass 2. Each character gets its items in one batch through
``npc_give.hand_over_and_trigger``, exactly like ``/give_items``: the items move into its
inventory and its ``on_receive_item`` script / text runs (which may e.g. teleport the player
or open a choice dialog). Unlike the command, no extra reaction turn is chained: the turn's
own narration (Pass 2) already tells how the character takes the item.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

from backend.api.routes.adventures.npc_give import hand_over_and_trigger


def handover_recipients(game_event: Any) -> set[str]:
    """IDs (upper case) of the characters that receive items this turn.

    Their ``on_interact`` triggers are skipped for the turn: the handover is the interaction,
    and their receive trigger reacts to it.
    """
    handovers = getattr(game_event, "given_items", None) or []
    return {str(h.npc_id).upper() for h in handovers}


def _sse(role: str, text: str) -> str:
    return f"event: {role}\ndata: {json.dumps({'role': role, 'content': text})}\n\n"


def _items_by_npc(handovers: list[Any]) -> dict[str, set[str]]:
    grouped: dict[str, set[str]] = {}
    for handover in handovers:
        grouped.setdefault(str(handover.npc_id), set()).add(str(handover.item_id).upper())
    return grouped


def _carried(manager: Any, item_ids: set[str]) -> list[dict[str, Any]]:
    return [
        item
        for item in manager.avatar.inventory or []
        if isinstance(item, dict) and str(item.get("id") or "").upper() in item_ids
    ]


async def apply_item_handovers(manager: Any, game_event: Any) -> AsyncGenerator[str, None]:
    """Hands the validated items over and streams the handover notes and trigger output."""
    handovers = list(getattr(game_event, "given_items", None) or [])
    for npc_id, item_ids in _items_by_npc(handovers).items():
        # A receive trigger may have moved the player on: the next character must still be here.
        npc = await manager._find_scene_npc_by_hint(npc_id)
        picked = _carried(manager, item_ids)
        if npc is None or not picked:
            continue
        for role, text in await hand_over_and_trigger(manager, npc, picked):
            yield _sse(role, text)
