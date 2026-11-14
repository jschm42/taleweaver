"""COMPANION block of the CURRENT STATE: tells both passes who travels with the protagonist.

Pass 1 learns where the companion is and that it reports orders in ``companion_order``
instead of moving the companion itself. Pass 2 learns whether the companion is present and
how talkative it is (``banter``), so it can give the companion a voice in the narration.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Optional

from backend.engine.party.companion_config import companion_config
from backend.engine.party.follow import companion_scene_id, is_out_of_action
from backend.engine.party.party_state import read_party
from backend.models.world_entity import WorldEntity

_BANTER_HINTS = {
    "QUIET": "speaks rarely and briefly",
    "NORMAL": "comments now and then in character",
    "CHATTY": "often adds short remarks, jokes or worries",
}


def _active_row(entity_states: Any, entities: Iterable[WorldEntity]) -> Optional[WorldEntity]:
    active_id = read_party(entity_states).active_id
    if not active_id:
        return None
    return next((row for row in entities if str(row.id) == active_id), None)


def _whereabouts(
    entity_states: dict[str, Any], row: WorldEntity, scene_id: str, scene_labels: dict[str, str]
) -> tuple[bool, str]:
    """(present, short description of where the companion is and what it does)."""
    if is_out_of_action(entity_states, row):
        return False, "is defeated and cannot act"
    where = companion_scene_id(entity_states, row)
    following = read_party(entity_states).following
    if where != scene_id:
        label = scene_labels.get(where, where or "unknown")
        return False, f"is NOT here; it waits in {label}"
    return True, "is here and follows the protagonist" if following else "is here but waits"


def companion_prompt_block(
    entity_states: dict[str, Any],
    entities: Iterable[WorldEntity],
    scene_id: str,
    scene_labels: dict[str, str],
    *,
    for_mechanics: bool,
) -> str:
    """The COMPANION block for Pass 1 (``for_mechanics``) or Pass 2; empty without companion."""
    states = entity_states or {}
    row = _active_row(states, entities)
    if row is None:
        return ""
    present, where = _whereabouts(states, row, str(scene_id or ""), scene_labels)
    head = f"\n\nCOMPANION: {row.name} (ID {row.id}) travels with the protagonist and {where}."
    if for_mechanics:
        return head + (
            " The engine moves the companion along through scene changes: never move it with "
            "moved_entities. When the player tells the companion (in any words or language) to "
            "stay behind here, set companion_order to 'wait'; to come along again, 'follow'."
        )
    if not present:
        return head + " Do not let it speak or act in this scene."
    config = companion_config(row.metadata_json if isinstance(row.metadata_json, dict) else {})
    banter = _BANTER_HINTS.get(config.banter if config else "NORMAL", _BANTER_HINTS["NORMAL"])
    return head + f" It is loyal to the protagonist and {banter}."
