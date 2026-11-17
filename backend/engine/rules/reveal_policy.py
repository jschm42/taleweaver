"""Reveal policy for hidden entities: which ones the Game Master may discover on its own.

A hidden entity normally has a reveal path: its ``reveal_rule`` text, or the engine default
("revealed when the protagonist searches the scene"). The reserved ``reveal_rule`` value
``script`` opts out of all of that: the entity is never shown to the Game Master as hidden,
never auto-discovered, and only scripts (``tw.npcs.reveal``, ``tw.objects.reveal``,
``set_hidden(False)``) or deterministic engine mechanics (crafting, ``reveals_item_id``)
make it visible.

Hidden NPCs are never discovered by the Game Master, whatever their ``reveal_rule`` says (the
text is kept for round trips but ignored). They appear through scripts or through their
``reveal_guard_expression`` (NPC metadata): the engine evaluates it after every player message
while the NPC is hidden in the protagonist's scene and reveals the NPC once it is True.
"""

from __future__ import annotations

from typing import Any

SCRIPT_ONLY_REVEAL = "script"
NPC_REVEAL_GUARD_KEY = "reveal_guard_expression"


def is_script_only_reveal(reveal_rule: Any) -> bool:
    """True when the reveal rule is the reserved value ``script`` (case-insensitive)."""
    return str(reveal_rule or "").strip().lower() == SCRIPT_ONLY_REVEAL


def _field(entity: Any, key: str) -> Any:
    if isinstance(entity, dict):
        return entity.get(key)
    return getattr(entity, key, None)


def is_npc(entity: Any) -> bool:
    """True for an NPC entity (ORM object or manifest dict)."""
    kind = _field(entity, "entity_type") or _field(entity, "type")
    return str(kind or "").strip().upper() == "NPC"


def entity_is_script_only(entity: Any) -> bool:
    """True for an entity the Game Master may never discover: every NPC, and others whose
    reveal rule is ``script``."""
    return is_npc(entity) or is_script_only_reveal(_field(entity, "reveal_rule"))


def npc_reveal_guard(entity: Any) -> str:
    """The NPC's reveal guard expression (metadata ``reveal_guard_expression``), or ''."""
    meta = _field(entity, "metadata_json")
    if not isinstance(meta, dict):
        meta = _field(entity, "metadata")
    if not isinstance(meta, dict):
        meta = {}
    value = meta.get(NPC_REVEAL_GUARD_KEY) or _field(entity, NPC_REVEAL_GUARD_KEY)
    return str(value or "").strip()


def has_discoverable_reveal_rule(reveal_rule: Any) -> bool:
    """True when the reveal rule is a real discovery condition (set and not ``script``)."""
    return bool(str(reveal_rule or "").strip()) and not is_script_only_reveal(reveal_rule)
