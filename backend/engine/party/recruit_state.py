"""Who the player may recruit with the Recruit action, and who rejoins for free.

A companion that was in the party before comes back without its price:

* replaced companions stay in ``__party__.recruited`` (only one is active), and
* an NPC that once accepted its ``recruit_item_id`` is marked ``recruit_paid`` in its
  ``entity_states`` entry, so even after being dismissed it never asks again.

Both rejoin through the Recruit action as if their ``recruit_mode`` were ``INSTANT``, also
companions that a script recruited the first time (``recruit_mode`` ``SCRIPT``).
"""

from __future__ import annotations

from typing import Any, Optional

from backend.engine.party.companion_config import CompanionConfig
from backend.engine.party.party_state import read_party

RECRUIT_PAID_KEY = "recruit_paid"


def is_active_companion(entity_states: Any, npc_id: str) -> bool:
    return read_party(entity_states).active_id == str(npc_id or "").strip()


def is_returning(entity_states: Any, npc_id: str) -> bool:
    """True for a former party member that rejoins without paying again."""
    npc_id = str(npc_id or "").strip()
    if read_party(entity_states).is_member(npc_id):
        return True
    entry = entity_states.get(npc_id) if isinstance(entity_states, dict) else None
    return isinstance(entry, dict) and entry.get(RECRUIT_PAID_KEY) is True


def can_offer_recruit(config: Optional[CompanionConfig], entity_states: Any, npc_id: str) -> bool:
    """The play view offers *Recruit* for this NPC (not the active companion itself)."""
    if config is None or not config.recruitable:
        return False
    if is_active_companion(entity_states, npc_id):
        return False
    return config.player_recruitable or is_returning(entity_states, npc_id)


def mark_recruit_paid(entity_states: dict[str, Any], npc_id: str) -> None:
    """Remembers that the NPC accepted its recruit item (in place)."""
    entry = entity_states.get(npc_id)
    entity_states[npc_id] = {**(entry if isinstance(entry, dict) else {}), RECRUIT_PAID_KEY: True}
