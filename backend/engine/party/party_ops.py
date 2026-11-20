"""Ordered ``tw.party`` operations and their replay onto ``entity_states["__party__"]``.

Scripts never write the party directly: ``tw.party`` records ops in
``ScriptChangeset.party_ops`` and every changeset applier (turn, trigger service, session
start) replays them with :func:`apply_party_ops`, like ``tw.time`` and ``tw.audio``.

Op shapes:
    {"op": "recruit", "npc_id": ..., "tactics": ... | None}
    {"op": "dismiss", "npc_id": ...}
    {"op": "activate", "npc_id": ...}
    {"op": "follow", "value": bool}
    {"op": "tactics", "npc_id": ..., "tactics": ...}
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from backend.engine.party.party_state import PartyState, read_party, store_party


def _recruit(party: PartyState, op: dict[str, Any]) -> None:
    party.recruit(str(op.get("npc_id") or ""), op.get("tactics") or None)


def _dismiss(party: PartyState, op: dict[str, Any]) -> None:
    party.dismiss(str(op.get("npc_id") or ""))


def _activate(party: PartyState, op: dict[str, Any]) -> None:
    party.activate(str(op.get("npc_id") or ""))


def _follow(party: PartyState, op: dict[str, Any]) -> None:
    party.following = bool(op.get("value"))


def _tactics(party: PartyState, op: dict[str, Any]) -> None:
    party.set_tactics(str(op.get("npc_id") or ""), str(op.get("tactics") or ""))


_HANDLERS: dict[str, Callable[[PartyState, dict[str, Any]], None]] = {
    "recruit": _recruit,
    "dismiss": _dismiss,
    "activate": _activate,
    "follow": _follow,
    "tactics": _tactics,
}


def apply_party_op_list(party: PartyState, ops: Iterable[dict[str, Any]]) -> PartyState:
    """Applies ops to a party in place (unknown ops are ignored) and returns it."""
    for op in ops or []:
        handler = _HANDLERS.get(str(op.get("op") or "")) if isinstance(op, dict) else None
        if handler:
            handler(party, op)
    return party


def apply_party_ops(entity_states: dict[str, Any], ops: Iterable[dict[str, Any]]) -> None:
    """Replays a changeset's party ops onto ``entity_states`` (in place)."""
    ops = list(ops or [])
    if not ops:
        return
    store_party(entity_states, apply_party_op_list(read_party(entity_states), ops))


def apply_session_party_ops(state: Any, ops: Iterable[dict[str, Any]]) -> None:
    """Replays party ops onto a ``SessionState`` and marks its ``entity_states`` as changed."""
    ops = list(ops or [])
    if not ops:
        return
    entity_states = dict(state.entity_states or {})
    apply_party_ops(entity_states, ops)
    state.entity_states = entity_states
    flag_modified(state, "entity_states")
