"""Combat groups: which NPCs in a scene join a fight on their own.

An NPC's ``combat_group`` is a free tag (e.g. ``BANDITS``). Its ``assist_mode`` says when it
joins a fight without being attacked itself:

- ``GROUP``: as soon as an engaged combatant shares its group.
- ``ANYONE``: as soon as anyone in its scene fights.
- ``NEVER``: only when the protagonist attacks it directly (a bystander).

Without an explicit mode an NPC with a group uses ``GROUP`` and an NPC without one ``NEVER``.
"""

from __future__ import annotations

import re
from typing import Any

ASSIST_GROUP = "GROUP"
ASSIST_ANYONE = "ANYONE"
ASSIST_NEVER = "NEVER"
ASSIST_MODES = (ASSIST_GROUP, ASSIST_ANYONE, ASSIST_NEVER)
MAX_GROUP_LENGTH = 64


def normalize_group(raw: Any) -> str | None:
    """``Red Bandits`` / ``red-bandits`` -> ``RED_BANDITS``; empty values clear the group."""
    clean = re.sub(r"[^A-Za-z0-9]+", "_", str(raw or "")).strip("_").upper()
    return clean[:MAX_GROUP_LENGTH] or None


def normalize_assist_mode(raw: Any) -> str | None:
    """A known assist mode, or ``None`` (automatic) for empty or unknown values."""
    clean = str(raw or "").strip().upper()
    return clean if clean in ASSIST_MODES else None


def resolve_assist_mode(group: str | None, mode: Any) -> str:
    """The effective mode: the explicit one, else ``GROUP`` with a group and ``NEVER`` without."""
    explicit = normalize_assist_mode(mode)
    if explicit:
        return explicit
    return ASSIST_GROUP if group else ASSIST_NEVER


def _wants_to_join(combatant: dict[str, Any], groups: set[str], anyone_fighting: bool) -> bool:
    mode = combatant.get("assist_mode") or ASSIST_NEVER
    if mode == ASSIST_ANYONE:
        return anyone_fighting
    if mode != ASSIST_GROUP:
        return False
    return bool(combatant.get("combat_group")) and combatant["combat_group"] in groups


def joining_allies(
    idle: list[dict[str, Any]], engaged: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Idle combatants that join because of the engaged ones, chain reactions included.

    The lists are not changed; the caller marks the returned combatants as engaged.
    """
    fighting = list(engaged)
    waiting = list(idle)
    joined: list[dict[str, Any]] = []
    while waiting:
        groups = {str(c["combat_group"]) for c in fighting if c.get("combat_group")}
        new = [c for c in waiting if _wants_to_join(c, groups, bool(fighting))]
        if not new:
            break
        joined.extend(new)
        fighting.extend(new)
        new_ids = {id(c) for c in new}
        waiting = [c for c in waiting if id(c) not in new_ids]
    return joined


def is_ally_of(combatant: dict[str, Any], target: dict[str, Any]) -> bool:
    """True when the combatant would join a fight against ``target`` right away."""
    groups = {str(target["combat_group"])} if target.get("combat_group") else set()
    return _wants_to_join(combatant, groups, True)
