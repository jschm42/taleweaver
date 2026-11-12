"""Marks party members in the scene entity payload the client renders.

The play view shows the active companion as a small card next to the protagonist; it
finds that card through ``is_companion`` instead of reading ``__party__`` itself.
"""

from __future__ import annotations

from typing import Any

from backend.engine.party.party_state import read_party

COMPANION_FLAG = "is_companion"


def mark_active_companion(entities: list[dict[str, Any]], entity_states: Any) -> None:
    """Sets ``is_companion`` on the active companion's entity dict (in place)."""
    active_id = read_party(entity_states).active_id
    if not active_id:
        return
    for entity in entities:
        if str(entity.get("id") or "") == active_id:
            entity[COMPANION_FLAG] = True
