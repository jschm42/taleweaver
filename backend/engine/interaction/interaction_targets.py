"""Resolves which world entities a player message interacts with (``on_interact`` scripts).

The GM's logic pass only reports entities whose state changed (``updated_entities``), so
merely examining, using or pushing an object never reached its ``on_interact`` script.
Context-menu commands always name their target ("Inspect Ticking Bomb", "Push Lever"), so
entities in the current scene or the inventory whose name or ID appears in the message are
treated as interacted with as well. Players also shorten names ("talk to Grimsby" for
"Grimsby the Gargoyle"): a single word of a name counts when no other candidate's name has it.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.world_entity import WorldEntity

_MIN_NAME_LENGTH = 3
# A single name word must be at least this long to identify an entity on its own.
_MIN_NAME_WORD_LENGTH = 4
_NAME_WORD = re.compile(r"[^\W\d_]+")
_FILLER_WORDS = frozenset(
    {"from", "into", "this", "that", "with", "your", "their", "over", "under"}
)


def _mentions(text: str, phrase: str) -> bool:
    phrase = phrase.strip().lower()
    if len(phrase) < _MIN_NAME_LENGTH:
        return False
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


def _name_words(name: str) -> set[str]:
    words = _NAME_WORD.findall((name or "").lower())
    return {w for w in words if len(w) >= _MIN_NAME_WORD_LENGTH and w not in _FILLER_WORDS}


def _unique_name_words(candidates: list[tuple[str, str]]) -> dict[str, set[str]]:
    """Per candidate ID, the name words no other candidate's name contains."""
    owners: dict[str, set[str]] = {}
    for entity_id, name in candidates:
        for word in _name_words(name):
            owners.setdefault(word, set()).add(entity_id)
    return {
        entity_id: {w for w in _name_words(name) if owners.get(w) == {entity_id}}
        for entity_id, name in candidates
    }


def mentioned_entity_ids(user_msg: str, candidates: list[tuple[str, str]]) -> list[str]:
    """IDs of ``(id, name)`` candidates whose name, ID or a unique name word is in ``user_msg``."""
    text = (user_msg or "").lower().strip()
    if not text or text.startswith("/give_items"):
        return []
    unique_words = _unique_name_words(candidates)
    return [
        entity_id
        for entity_id, name in candidates
        if _mentions(text, name)
        or _mentions(text, entity_id.replace("_", " "))
        or _mentions(text, entity_id)
        or any(_mentions(text, word) for word in unique_words.get(entity_id, ()))
    ]


async def _reachable_entities(db: AsyncSession, state: Any) -> list[tuple[str, str, str]]:
    res = await db.execute(
        select(WorldEntity.id, WorldEntity.name, WorldEntity.entity_type).where(
            WorldEntity.session_id == state.session_id,
            or_(
                (WorldEntity.current_scene_id == state.current_scene_id)
                & WorldEntity.is_hidden.is_(False),
                WorldEntity.is_in_inventory.is_(True),
            ),
        )
    )
    return [
        (row.id, row.name or "", str(row.entity_type or "").upper()) for row in res.all() if row.id
    ]


async def interacted_entity_ids(
    db: AsyncSession, state: Any, user_msg: str, reported_ids: list[str]
) -> list[str]:
    """GM-reported entity IDs plus reachable entities named in the message, without duplicates.

    IDs use the entity's stored spelling: script targets are matched case-sensitively.
    """
    candidates = await _reachable_entities(db, state)
    canonical = {entity_id.upper(): entity_id for entity_id, _name, _type in candidates}
    npc_ids = {entity_id.upper() for entity_id, _name, ent_type in candidates if ent_type == "NPC"}
    name_tuples = [(entity_id, name) for entity_id, name, _type in candidates]
    mentioned = mentioned_entity_ids(user_msg, name_tuples)

    ordered_ids: list[str] = []
    # If the player explicitly named entities in their message, those take priority.
    # Unmentioned NPCs that the GM merely updated in the background (e.g. reacting or speaking)
    # were not interacted with by the player and must not have their on_interact triggers fired.
    if mentioned:
        ordered_ids.extend(mentioned)
        for r_id in reported_ids:
            if r_id and r_id.upper() not in npc_ids:
                ordered_ids.append(r_id)
    else:
        ordered_ids.extend(reported_ids)

    unique: dict[str, str] = {}
    for entity_id in (i for i in ordered_ids if i):
        unique.setdefault(entity_id.upper(), canonical.get(entity_id.upper(), entity_id))
    return list(unique.values())
