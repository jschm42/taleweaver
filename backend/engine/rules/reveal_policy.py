"""Reveal policy for hidden entities: which ones the Game Master may discover on its own.

A hidden entity normally has a reveal path: its ``reveal_rule`` text, or the engine default
("revealed when the protagonist searches the scene"). The reserved ``reveal_rule`` value
``script`` opts out of all of that: the entity is never shown to the Game Master as hidden,
never auto-discovered, and only scripts (``tw.npcs.reveal``, ``tw.objects.reveal``,
``set_hidden(False)``) or deterministic engine mechanics (crafting, ``reveals_item_id``)
make it visible.
"""

from __future__ import annotations

from typing import Any

SCRIPT_ONLY_REVEAL = "script"


def is_script_only_reveal(reveal_rule: Any) -> bool:
    """True when the reveal rule is the reserved value ``script`` (case-insensitive)."""
    return str(reveal_rule or "").strip().lower() == SCRIPT_ONLY_REVEAL


def entity_is_script_only(entity: Any) -> bool:
    """True for an entity (ORM object or dict) whose reveal rule is ``script``."""
    if isinstance(entity, dict):
        return is_script_only_reveal(entity.get("reveal_rule"))
    return is_script_only_reveal(getattr(entity, "reveal_rule", None))


def has_discoverable_reveal_rule(reveal_rule: Any) -> bool:
    """True when the reveal rule is a real discovery condition (set and not ``script``)."""
    return bool(str(reveal_rule or "").strip()) and not is_script_only_reveal(reveal_rule)
