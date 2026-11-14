"""``/companion wait|follow``: orders to the active companion (context menu of its card).

The order is applied by the engine (``engine/party/orders.py``); afterwards the caller chains
a Game Master turn so the companion answers in character, like a handover with
``/give_items``. Typed orders ("Batlin, stay here") need no command: Pass 1 reports them in
``companion_order``.
"""

from __future__ import annotations

from typing import Any

from backend.api.routes.adventures.npc_give import GiveOutcome
from backend.engine.party.orders import ORDER_FOLLOW, give_companion_order, normalize_order

COMPANION_USAGE = "Usage: /companion wait | follow"


def _reaction_prompt(npc_name: str, npc_id: str, order: str) -> str:
    told = "to come along again" if order == ORDER_FOLLOW else "to stay here and wait"
    return (
        f"[COMPANION_ORDER] The player told {npc_name} (ID {npc_id}) {told}. The engine already "
        f"applied the order: do not set companion_order and do not move {npc_name}. Let "
        f"{npc_name} acknowledge it briefly in character."
    )


async def companion_order_command(manager: Any, args: str) -> GiveOutcome:
    """Runs ``/companion <order>``; returns the events and the reaction prompt."""
    order = normalize_order(args)
    if not order:
        return GiveOutcome([("system", COMPANION_USAGE)])
    result = await give_companion_order(manager.db, manager.state, order)
    events = [("system", result.message)]
    if not result.applied:
        return GiveOutcome(events)
    return GiveOutcome(events, _reaction_prompt(result.npc_name or "", result.npc_id or "", order))
