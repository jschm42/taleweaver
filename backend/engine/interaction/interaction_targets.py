"""Resolves which world entities a player message interacts with (``on_interact`` scripts).

The GM's logic pass only reports entities whose state changed (``updated_entities``), so
merely examining, using or pushing an object never reached its ``on_interact`` script.
Context-menu commands always name their target ("Inspect Ticking Bomb", "Push Lever"), so
entities in the current scene or the inventory whose name or ID appears in the message are
treated as interacted with as well.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.world_entity import WorldEntity

_MIN_NAME_LENGTH = 3


def _mentions(text: str, phrase: str) -> bool:
    phrase = phrase.strip().lower()
    if len(phrase) < _MIN_NAME_LENGTH:
        return False
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


def mentioned_entity_ids(user_msg: str, candidates: list[tuple[str, str]]) -> list[str]:
    """IDs of ``(id, name)`` candidates whose name or ID appears in ``user_msg``."""
    text = (user_msg or "").lower()
    if not text:
        return []
    return [
        entity_id
        for entity_id, name in candidates
        if _mentions(text, name)
        or _mentions(text, entity_id.replace("_", " "))
        or _mentions(text, entity_id)
    ]


async def _reachable_entities(db: AsyncSession, state: Any) -> list[tuple[str, str]]:
    res = await db.execute(
        select(WorldEntity.id, WorldEntity.name).where(
            WorldEntity.session_id == state.session_id,
            or_(
                (WorldEntity.current_scene_id == state.current_scene_id)
                & WorldEntity.is_hidden.is_(False),
                WorldEntity.is_in_inventory.is_(True),
            ),
        )
    )
    return [(row.id, row.name or "") for row in res.all() if row.id]


async def interacted_entity_ids(
    db: AsyncSession, state: Any, user_msg: str, reported_ids: list[str]
) -> list[str]:
    """GM-reported entity IDs plus reachable entities named in the message, without duplicates.

    IDs use the entity's stored spelling: script targets are matched case-sensitively.
    """
    candidates = await _reachable_entities(db, state)
    canonical = {entity_id.upper(): entity_id for entity_id, _name in candidates}
    unique: dict[str, str] = {}
    for entity_id in (i for i in [*reported_ids, *mentioned_entity_ids(user_msg, candidates)] if i):
        unique.setdefault(entity_id.upper(), canonical.get(entity_id.upper(), entity_id))
    return list(unique.values())
