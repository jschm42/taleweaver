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
    # Abilities (special action IDs) the player switched off per companion (hero dialog).
    disabled_abilities: dict[str, list[str]] = field(default_factory=dict)

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
        self.disabled_abilities.pop(npc_id, None)
        if self.active_id == npc_id:
            self.active_id = None

    def activate(self, npc_id: str) -> bool:
        """Makes a recruited NPC the active companion; False if it is not in the party."""
        npc_id = _clean_id(npc_id)
        if npc_id not in self.recruited:
            return False
        self.active_id = npc_id
        return True

    def set_tactics(self, npc_id: str, tactics: str) -> None:
        npc_id = _clean_id(npc_id)
        if npc_id in self.recruited and tactics:
            self.tactics[npc_id] = tactics

    def set_ability(self, npc_id: str, ability_id: str, enabled: bool) -> None:
        npc_id, ability_id = _clean_id(npc_id), _clean_id(ability_id)
        if npc_id not in self.recruited or not ability_id:
            return
        off = [a for a in self.disabled_abilities.get(npc_id, []) if a != ability_id]
        if not enabled:
            off.append(ability_id)
        if off:
            self.disabled_abilities[npc_id] = off
        else:
            self.disabled_abilities.pop(npc_id, None)

    def ability_enabled(self, npc_id: str, ability_id: str) -> bool:
        return _clean_id(ability_id) not in self.disabled_abilities.get(_clean_id(npc_id), [])

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
            "disabled_abilities": {k: list(v) for k, v in self.disabled_abilities.items()},
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
    disabled = raw.get("disabled_abilities")
    disabled = disabled if isinstance(disabled, dict) else {}
    return PartyState(
        active_id=active_id,
        recruited=list(dict.fromkeys(recruited)),
        following=bool(raw.get("following", True)),
        tactics={_clean_id(k): str(v) for k, v in tactics.items() if _clean_id(k)},
        disabled_abilities={
            _clean_id(k): [_clean_id(a) for a in v if _clean_id(a)]
            for k, v in disabled.items()
            if _clean_id(k) and isinstance(v, list)
        },
    )


def store_party(entity_states: dict[str, Any], party: PartyState) -> None:
    """Writes the party into ``entity_states`` (in place); an empty party removes the key."""
    if not party.recruited:
        entity_states.pop(PARTY_KEY, None)
        return
    entity_states[PARTY_KEY] = party.to_dict()
