"""Quest items: items the story depends on, so the player can never give them away.

An item with ``metadata_json.quest_item = true`` stays with the protagonist: ``/give_items``
(and a typed "give X to Y"), ``/companion_give`` and Game Master inventory removals all refuse
it. Scripts are author-controlled and may still move it (``tw.player.transfer_item`` & co.),
so a hand-in quest delivers the item with a script.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.engine.scripting.item_transfer import ref_id
from backend.models.world_entity import WorldEntity

QUEST_ITEM_KEY = "quest_item"


def is_quest_item_metadata(metadata: Any) -> bool:
    """True when an item's ``metadata_json`` declares it a quest item."""
    return isinstance(metadata, dict) and metadata.get(QUEST_ITEM_KEY) is True


async def quest_item_ids(db: AsyncSession, session_id: str, item_ids: Iterable[str]) -> set[str]:
    """Upper-case IDs among ``item_ids`` whose session item row is a quest item."""
    wanted = {str(item_id).strip().upper() for item_id in item_ids if str(item_id).strip()}
    if not wanted:
        return set()
    res = await db.execute(
        select(WorldEntity.id, WorldEntity.metadata_json).where(
            WorldEntity.session_id == session_id,
            func.upper(WorldEntity.id).in_(wanted),
        )
    )
    return {str(row.id).upper() for row in res.all() if is_quest_item_metadata(row.metadata_json)}


async def split_quest_items(
    db: AsyncSession, session_id: str, entries: list[Any]
) -> tuple[list[Any], list[Any]]:
    """Splits inventory entries into (giftable, quest items)."""
    locked = await quest_item_ids(db, session_id, (ref_id(entry) for entry in entries))
    giftable = [entry for entry in entries if ref_id(entry) not in locked]
    kept = [entry for entry in entries if ref_id(entry) in locked]
    return giftable, kept


def quest_item_refusal(names: list[str]) -> str:
    """Player-facing line for quest items that stay with the protagonist."""
    joined = ", ".join(names)
    verb = "is" if len(names) == 1 else "are"
    return f"{joined} {verb} too important for your quest to give away."


async def mark_carried_quest_items(db: AsyncSession, session_id: str, items: list[dict]) -> None:
    """Sets ``quest_item: True`` on carried item dicts so the client can frame them."""
    quest_ids = await quest_item_ids(db, session_id, (ref_id(item) for item in items))
    for item in items:
        if ref_id(item) in quest_ids:
            item[QUEST_ITEM_KEY] = True


def _mark_from_metadata(entity: Any) -> None:
    if isinstance(entity, dict) and is_quest_item_metadata(entity.get("metadata_json")):
        entity[QUEST_ITEM_KEY] = True


def mark_scene_quest_items(entities: list[dict[str, Any]]) -> None:
    """Sets ``quest_item: True`` on scene entities and container contents from their metadata."""
    for entity in entities:
        _mark_from_metadata(entity)
        for content in entity.get("inventory") or []:
            _mark_from_metadata(content)
