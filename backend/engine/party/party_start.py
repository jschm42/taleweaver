"""Companions who are in the party from the start (``companion.starts_in_party``)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.engine.party.companion_config import companion_config
from backend.engine.party.follow import place_entity, session_npc
from backend.engine.party.party_state import read_party, store_party


def seed_starting_party(
    entity_states: dict[str, Any], template_entities: Iterable[Any], first_scene_id: str
) -> None:
    """Recruits every ``starts_in_party`` NPC; the first one is active and starts with the player.

    Further starting companions are recruited but stay in their own scenes (one active
    companion in V1).
    """
    party = read_party(entity_states)
    starters = [
        ent
        for ent in template_entities
        if str(getattr(ent, "entity_type", "") or "").upper() == "NPC"
        and (config := companion_config(getattr(ent, "metadata_json", None)))
        and config.starts_in_party
    ]
    if not starters:
        return
    for ent in reversed(starters):
        config = companion_config(ent.metadata_json)
        party.recruit(ent.id, config.tactics if config else None)
    store_party(entity_states, party)
    if first_scene_id:
        place_entity(entity_states, None, starters[0].id, first_scene_id)


async def sync_starting_party_rows(
    db: AsyncSession, session_id: str, entity_states: dict[str, Any]
) -> None:
    """Moves the session row of the active starting companion to its seeded scene."""
    npc_id = read_party(entity_states).active_id
    entry = entity_states.get(npc_id) if npc_id else None
    if not isinstance(entry, dict) or not entry.get("current_scene_id"):
        return
    row = await session_npc(db, session_id, npc_id)
    if row is not None:
        place_entity({}, row, npc_id, entry["current_scene_id"])
