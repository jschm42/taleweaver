"""``tw.party``: the protagonist's companions (sidekicks).

Calls record ordered ops in ``changeset.party_ops`` (replayed by
``engine/party/party_ops.apply_party_ops``) and mirror them on a local copy, so a script reads
its own changes back (``tw.party.recruit("LARA"); tw.party.active`` is ``"LARA"``).
NPC arguments accept an ID, an exact name or an NPC proxy (``tw.npcs.get(...)``).
"""

from __future__ import annotations

from typing import Any, Optional

from backend.engine.party.companion_config import TACTICS, companion_config
from backend.engine.party.party_ops import apply_party_op_list
from backend.engine.party.party_state import PARTY_KEY, read_party


class PartyProxy:
    """Safe proxy exposed to scripts as ``tw.party``."""

    def __init__(
        self,
        changeset: Any,
        party: Optional[dict[str, Any]],
        npc_entities: dict[str, dict[str, Any]],
        npcs: Any,
        context: Any = None,
    ):
        self._changeset = changeset
        self._party = read_party({PARTY_KEY: party})
        self._npc_entities = npc_entities or {}
        self._npcs = npcs
        self._context = context

    # --- helpers -------------------------------------------------------------------------

    def _record(self, op: dict[str, Any]) -> None:
        self._changeset.party_ops.append(op)
        apply_party_op_list(self._party, [op])

    def _error(self, api: str, message: str) -> None:
        """A script error the player sees in the chat (like an unknown award key)."""
        from backend.engine.scripting.runner import SCRIPT_ERROR_PREFIX

        self._changeset.system_messages.append(f"{SCRIPT_ERROR_PREFIX} in '{api}': {message}")

    def _debug(self, message: str) -> None:
        if self._context is not None:
            self._context.debug(message)

    def _resolve(self, npc: Any) -> Optional[str]:
        """NPC ID for an ID, exact name (case-insensitive) or NPC proxy; None if unknown."""
        key = str(getattr(npc, "id", npc) or "").strip()
        if not key:
            return None
        if key in self._npc_entities:
            return key
        upper, lower = key.upper(), key.lower()
        for eid, data in self._npc_entities.items():
            if str(eid).strip().upper() == upper:
                return eid
            if str(data.get("name") or "").strip().lower() == lower:
                return eid
        return None

    def _member(self, api: str, npc: Any) -> Optional[str]:
        """The party member meant by ``npc`` (the active companion when omitted)."""
        npc_id = self._resolve(npc) if npc is not None else self._party.active_id
        if npc_id and self._party.is_member(npc_id):
            return npc_id
        self._debug(
            f"{api} ignored: '{npc if npc is not None else 'active companion'}' is not in the party."
        )
        return None

    def _tactics(self, api: str, tactics: Any) -> Optional[str]:
        value = str(tactics or "").strip().upper()
        if value in TACTICS:
            return value
        self._error(api, f"unknown tactics '{tactics}'. Use one of: {', '.join(TACTICS)}.")
        return None

    # --- reading -------------------------------------------------------------------------

    @property
    def active(self) -> Optional[str]:
        """ID of the active companion, else None."""
        return self._party.active_id

    @property
    def companion(self) -> Any:
        """The active companion as an NPC proxy (like ``tw.npcs.get``), else None."""
        if not self._party.active_id:
            return None
        return self._npcs.get(self._party.active_id)

    @property
    def members(self) -> list[str]:
        """IDs of all recruited companions (active or not)."""
        return list(self._party.recruited)

    @property
    def following(self) -> bool:
        """True while the active companion follows the protagonist through scene changes."""
        return self._party.following

    @property
    def is_empty(self) -> bool:
        return not self._party.recruited

    def is_member(self, npc: Any) -> bool:
        npc_id = self._resolve(npc)
        return bool(npc_id) and self._party.is_member(npc_id)

    def is_active(self, npc: Any) -> bool:
        npc_id = self._resolve(npc)
        return bool(npc_id) and npc_id == self._party.active_id

    def tactics_of(self, npc: Any = None) -> Optional[str]:
        """Combat tactics of a member (default: the active companion), else None."""
        npc_id = self._resolve(npc) if npc is not None else self._party.active_id
        if not npc_id or not self._party.is_member(npc_id):
            return None
        if npc_id in self._party.tactics:
            return self._party.tactics[npc_id]
        config = companion_config((self._npc_entities.get(npc_id) or {}).get("metadata_json"))
        return config.tactics if config else TACTICS[0]

    # --- changing ------------------------------------------------------------------------

    def recruit(self, npc: Any, tactics: Optional[str] = None) -> bool:
        """Adds the NPC to the party and makes it the active companion that follows.

        The NPC stays where it is; it travels along from the next scene change on, once it
        is in the scene the protagonist leaves. False when the NPC is unknown or its
        companion settings say it cannot be recruited.
        """
        npc_id = self._resolve(npc)
        if not npc_id:
            self._error("tw.party.recruit", f"no NPC '{getattr(npc, 'id', npc)}'.")
            return False
        config = companion_config((self._npc_entities.get(npc_id) or {}).get("metadata_json"))
        if config is not None and not config.recruitable:
            self._debug(f"tw.party.recruit ignored: '{npc_id}' is not recruitable.")
            return False
        chosen = self._tactics("tw.party.recruit", tactics) if tactics else None
        if tactics and not chosen:
            return False
        self._record({"op": "recruit", "npc_id": npc_id, "tactics": chosen})
        return True

    def dismiss(self, npc: Any = None) -> bool:
        """Removes a member (default: the active companion); it stays in its scene."""
        npc_id = self._member("tw.party.dismiss", npc)
        if not npc_id:
            return False
        self._record({"op": "dismiss", "npc_id": npc_id})
        return True

    def set_active(self, npc: Any) -> bool:
        """Makes another recruited member the active companion."""
        npc_id = self._member("tw.party.set_active", npc)
        if not npc_id:
            return False
        self._record({"op": "activate", "npc_id": npc_id})
        return True

    def wait(self) -> None:
        """The active companion stays where it is until ``follow()``."""
        self._record({"op": "follow", "value": False})

    def follow(self) -> None:
        """The active companion follows the protagonist again (from the scene it waits in)."""
        self._record({"op": "follow", "value": True})

    def set_tactics(self, tactics: str, npc: Any = None) -> bool:
        """Sets a member's combat tactics: BALANCED, OFFENSIVE, DEFENSIVE or SUPPORT."""
        npc_id = self._member("tw.party.set_tactics", npc)
        chosen = self._tactics("tw.party.set_tactics", tactics) if npc_id else None
        if not chosen:
            return False
        self._record({"op": "tactics", "npc_id": npc_id, "tactics": chosen})
        return True
