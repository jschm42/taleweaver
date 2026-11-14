"""Player orders to the active companion: stay here (``wait``) or come along (``follow``).

Both ways in use this module: the ``/companion wait|follow`` command (context menu of the
companion card) and the Pass 1 field ``companion_order``, which the mechanics model sets when
the player tells the companion so in their own words (any language).

An order only reaches a companion that stands in the protagonist's scene and is not defeated;
a waiting companion somewhere else cannot hear it, so the protagonist has to go back.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.engine.party.follow import companion_scene_id, is_out_of_action, session_npc
from backend.engine.party.party_state import read_party, store_party
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity

ORDER_WAIT = "wait"
ORDER_FOLLOW = "follow"
ORDERS = (ORDER_WAIT, ORDER_FOLLOW)


@dataclass
class OrderResult:
    """Outcome of an order; ``message`` is the line the player sees."""

    applied: bool
    message: str
    npc_id: Optional[str] = None
    npc_name: Optional[str] = None


def normalize_order(raw: Any) -> Optional[str]:
    value = str(raw or "").strip().lower()
    return value if value in ORDERS else None


def companion_refusal(
    entity_states: dict[str, Any], row: WorldEntity, scene_id: str
) -> Optional[str]:
    """Why the companion cannot act on an order or a handover right now (None: it can)."""
    if is_out_of_action(entity_states, row):
        return f"{row.name} is in no state to follow orders."
    if companion_scene_id(entity_states, row) != scene_id:
        return f"{row.name} is not here and cannot hear you."
    return None


def apply_order(
    entity_states: dict[str, Any], row: WorldEntity, order: str, scene_id: str
) -> OrderResult:
    """Applies an order to the active companion ``row`` in ``entity_states`` (in place)."""
    refusal = companion_refusal(entity_states, row, scene_id)
    if refusal:
        return OrderResult(False, refusal, row.id, row.name)
    party = read_party(entity_states)
    wants_follow = order == ORDER_FOLLOW
    if party.following == wants_follow:
        state_text = "already follows you" if wants_follow else "is already waiting here"
        return OrderResult(False, f"{row.name} {state_text}.", row.id, row.name)
    party.following = wants_follow
    store_party(entity_states, party)
    text = "follows you again" if wants_follow else "stays here and waits for you"
    return OrderResult(True, f"{row.name} {text}.", row.id, row.name)


async def give_companion_order(db: AsyncSession, state: SessionState, order: Any) -> OrderResult:
    """Gives ``order`` to the session's active companion and stores the result."""
    normalized = normalize_order(order)
    if not normalized:
        return OrderResult(False, "Companions understand 'wait' and 'follow'.")
    party = read_party(state.entity_states)
    row = await session_npc(db, state.session_id, party.active_id) if party.active_id else None
    if row is None:
        return OrderResult(False, "You have no companion.")
    entity_states = dict(state.entity_states or {})
    result = apply_order(entity_states, row, normalized, str(state.current_scene_id or ""))
    if result.applied:
        state.entity_states = entity_states
        flag_modified(state, "entity_states")
    return result
