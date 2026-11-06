"""Keeps an item in exactly one holder when it reaches the player's inventory.

Scene containers list their contents in ``entity_states[<container>]["inventory"]`` (or,
until first changed, in the row's ``inventory`` column). Taking an item with a plain
``/take`` or receiving it from the Game Master moves it to the inventory but used to leave
it in that list, so a later ``/container_take_*`` handed out a second copy.
"""

from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.models.world_entity import WorldEntity

CONTAINER_ITEM_TYPES = ("CONTAINER", "CONTAINER_SWITCH")


def entry_id(entry: Any) -> str:
    """Upper-cased item id of a container or inventory entry (dict or plain id)."""
    raw = entry.get("id") if isinstance(entry, dict) else entry
    return str(raw or "").strip().upper()


def carried_ids(inventory: Iterable[Any] | None) -> set[str]:
    return {entry_id(entry) for entry in inventory or []} - {""}


async def load_session_containers(db: AsyncSession, session_id: str) -> list[WorldEntity]:
    res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.session_id == session_id,
            WorldEntity.entity_type == "OBJECT",
            WorldEntity.item_type.in_(CONTAINER_ITEM_TYPES),
        )
    )
    return list(res.scalars().all())


def _contents(states: dict[str, Any], container: WorldEntity) -> list[Any]:
    listed = (states.get(container.id) or {}).get("inventory")
    return list(listed) if isinstance(listed, list) else list(container.inventory or [])


def detach_from_containers(
    states: dict[str, Any], containers: Iterable[WorldEntity], item_ids: Iterable[str]
) -> list[str]:
    """Remove the items from every container's contents; returns the changed container ids.

    ``states`` is edited in place (the caller writes it back to the session).
    """
    wanted = {str(i or "").strip().upper() for i in item_ids} - {""}
    changed: list[str] = []
    if not wanted:
        return changed
    for container in containers:
        contents = _contents(states, container)
        remaining = [entry for entry in contents if entry_id(entry) not in wanted]
        if len(remaining) == len(contents):
            continue
        container.inventory = remaining
        states[container.id] = {**(states.get(container.id) or {}), "inventory": remaining}
        changed.append(container.id)
    return changed


async def detach_carried_items(db: AsyncSession, state: Any, item_ids: Iterable[str]) -> list[str]:
    """Same as ``detach_from_containers`` for the session state itself (writes it back)."""
    states = dict(state.entity_states or {})
    containers = await load_session_containers(db, state.session_id)
    changed = detach_from_containers(states, containers, item_ids)
    if changed:
        state.entity_states = states
        flag_modified(state, "entity_states")
    return changed
