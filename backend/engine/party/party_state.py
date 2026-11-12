"""The session party, stored in ``entity_states["__party__"]``.

V1 supports exactly one active companion. Recruited companions who are not active stay
where they are. ``following`` is a party-wide switch: while it is on, the active companion
moves along whenever the protagonist leaves the scene the companion is in. Because the
state lives in ``entity_states``, checkpoints and saves include it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

PARTY_KEY = "__party__"


def _clean_id(raw: Any) -> str:
    return str(raw or "").strip()


@dataclass
class PartyState:
    """Mutable view of the session party; write it back with ``store_party``."""

    active_id: Optional[str] = None
    recruited: list[str] = field(default_factory=list)
    following: bool = True
    tactics: dict[str, str] = field(default_factory=dict)

    def is_member(self, npc_id: str) -> bool:
        return _clean_id(npc_id) in self.recruited

    def recruit(self, npc_id: str, tactics: Optional[str] = None) -> None:
        """Adds the NPC to the party and makes it the active companion."""
        npc_id = _clean_id(npc_id)
        if not npc_id:
            return
        if npc_id not in self.recruited:
            self.recruited.append(npc_id)
        self.active_id = npc_id
        self.following = True
        if tactics:
            self.tactics[npc_id] = tactics

    def dismiss(self, npc_id: str) -> None:
        """Removes the NPC from the party; it stays in its current scene."""
        npc_id = _clean_id(npc_id)
        self.recruited = [m for m in self.recruited if m != npc_id]
        self.tactics.pop(npc_id, None)
        if self.active_id == npc_id:
            self.active_id = None

    def follower_id(self) -> Optional[str]:
        """The companion that moves along with the protagonist, if any."""
        if not self.following or not self.active_id:
            return None
        return self.active_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_id": self.active_id,
            "recruited": list(self.recruited),
            "following": self.following,
            "tactics": dict(self.tactics),
        }


def read_party(entity_states: Any) -> PartyState:
    """Reads the party defensively; a missing or malformed entry is an empty party."""
    raw = entity_states.get(PARTY_KEY) if isinstance(entity_states, dict) else None
    if not isinstance(raw, dict):
        return PartyState()
    recruited = [_clean_id(m) for m in raw.get("recruited") or [] if _clean_id(m)]
    active_id = _clean_id(raw.get("active_id")) or None
    if active_id and active_id not in recruited:
        recruited.append(active_id)
    tactics = raw.get("tactics") if isinstance(raw.get("tactics"), dict) else {}
    return PartyState(
        active_id=active_id,
        recruited=list(dict.fromkeys(recruited)),
        following=bool(raw.get("following", True)),
        tactics={_clean_id(k): str(v) for k, v in tactics.items() if _clean_id(k)},
    )


def store_party(entity_states: dict[str, Any], party: PartyState) -> None:
    """Writes the party into ``entity_states`` (in place); an empty party removes the key."""
    if not party.recruited:
        entity_states.pop(PARTY_KEY, None)
        return
    entity_states[PARTY_KEY] = party.to_dict()
