"""Marks party members in the scene entity payload the client renders.

The play view shows the active companion as a small card next to the protagonist; it
finds that card through ``is_companion`` instead of reading ``__party__`` itself.
``companion_following`` picks the order its context menu offers (stay here / follow me).
"""

from __future__ import annotations

from typing import Any

from backend.engine.party.companion_config import RECRUIT_INSTANT, companion_config
from backend.engine.party.party_state import read_party
from backend.engine.party.recruit_state import can_offer_recruit, is_returning

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


RECRUITABLE_FLAG = "is_recruitable"


def mark_recruitable_npcs(entities: list[dict[str, Any]], entity_states: Any) -> None:
    """Flags NPCs the player can recruit with the Recruit action (frame, tag, context menu).

    Sets ``is_recruitable``, ``recruit_mode`` and ``recruit_hint``; never the wanted item.
    A former party member (``recruit_state.is_returning``) rejoins for free, so it is sent as
    ``INSTANT``. The active companion and script-only companions are left alone.
    """
    for entity in entities:
        npc_id = str(entity.get("id") or "")
        config = companion_config(entity.get("metadata_json"))
        if not can_offer_recruit(config, entity_states, npc_id):
            continue
        returning = is_returning(entity_states, npc_id)
        entity[RECRUITABLE_FLAG] = True
        entity["recruit_mode"] = RECRUIT_INSTANT if returning else config.recruit_mode
        entity["recruit_hint"] = "" if returning else config.recruit_hint
