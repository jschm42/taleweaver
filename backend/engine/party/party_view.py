"""Marks party members in the scene entity payload the client renders.

The play view shows the active companion as a small card next to the protagonist; it
finds that card through ``is_companion`` instead of reading ``__party__`` itself.
``companion_following`` picks the order its context menu offers (stay here / follow me).
"""

from __future__ import annotations

from typing import Any

from backend.engine.party.party_state import read_party

COMPANION_FLAG = "is_companion"
FOLLOWING_FLAG = "companion_following"


def mark_active_companion(entities: list[dict[str, Any]], entity_states: Any) -> None:
    """Sets ``is_companion`` (and ``companion_following``) on the active companion (in place)."""
    party = read_party(entity_states)
    if not party.active_id:
        return
    for entity in entities:
        if str(entity.get("id") or "") == party.active_id:
            entity[COMPANION_FLAG] = True
            entity[FOLLOWING_FLAG] = party.following
