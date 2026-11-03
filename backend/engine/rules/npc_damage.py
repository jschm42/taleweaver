"""The editor's "NPC can be damaged" switch (stored as ``is_killable``).

When it is off, the NPC never loses HP: scripts, the GM and combat cannot hurt or defeat it,
and it cannot be fought. The game may switch it at runtime via an ``is_killable`` override in
``entity_states``, which wins over the template value.
"""

from __future__ import annotations

from typing import Any, Optional


def can_be_damaged(override: Optional[dict[str, Any]], entity: Any) -> bool:
    """True unless the switch is off (session override first, then the entity row/dict)."""
    if isinstance(override, dict) and "is_killable" in override:
        return override["is_killable"] is not False
    value = (
        entity.get("is_killable")
        if isinstance(entity, dict)
        else getattr(entity, "is_killable", None)
    )
    return value is not False


def blocks_hp_loss(override: Optional[dict[str, Any]], entity: Any, new_hp: Any) -> bool:
    """True when ``new_hp`` would lower the HP of an NPC that cannot be damaged."""
    if can_be_damaged(override, entity):
        return False
    current = (override or {}).get("hp")
    if current is None:
        current = entity.get("hp") if isinstance(entity, dict) else getattr(entity, "hp", None)
    try:
        return current is not None and int(new_hp) < int(current)
    except (TypeError, ValueError):
        return False
