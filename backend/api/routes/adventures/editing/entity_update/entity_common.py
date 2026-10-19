"""Entity ID rename cascade and the fields shared by NPCs and items."""

from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editing.common import _get_template_avatar
from backend.api.routes.adventures.editing.entity_update.fields import (
    apply_vitals,
    copy_given,
    ref_id,
    template_row_exists,
    template_rows,
    validated_new_id,
)
from backend.api.routes.adventures.editing.schemas import EntityUpdateRequest
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

_MAX_ENTITY_ID_LENGTH = 30


def _renamed_ref(item: Any, old_id: str, new_id: str) -> Any:
    """The inventory/equipment entry pointing at ``new_id`` instead of ``old_id``."""
    if ref_id(item) != old_id:
        return item
    return new_id if isinstance(item, str) else {**item, "id": new_id}


def _renamed_list(items: list[Any], old_id: str, new_id: str) -> list[Any] | None:
    """Renamed copy of ``items``, or None when nothing referenced ``old_id``."""
    if not any(ref_id(i) == old_id for i in items):
        return None
    return [_renamed_ref(i, old_id, new_id) for i in items]


def _rename_entity_refs(other: WorldEntity, old_id: str, new_id: str) -> None:
    ingredients = list(other.combination_ingredients or [])
    if old_id in ingredients:
        other.combination_ingredients = [new_id if x == old_id else x for x in ingredients]
    if other.reveals_item_id == old_id:
        other.reveals_item_id = new_id
    renamed_inventory = _renamed_list(list(other.inventory or []), old_id, new_id)
    if renamed_inventory is not None:
        other.inventory = renamed_inventory


async def _rename_avatar_refs(db: AsyncSession, template_id: str, old_id: str, new_id: str) -> None:
    avatar = await _get_template_avatar(db, template_id)
    if not avatar:
        return
    renamed_inventory = _renamed_list(list(avatar.inventory or []), old_id, new_id)
    if renamed_inventory is not None:
        avatar.inventory = renamed_inventory
    equipment = dict(avatar.equipment or {})
    if any(ref_id(v) == old_id for v in equipment.values()):
        avatar.equipment = {slot: _renamed_ref(v, old_id, new_id) for slot, v in equipment.items()}


async def rename_entity(db: AsyncSession, template_id: str, ent: WorldEntity, raw_id: str) -> None:
    """Change an entity ID and repoint exit keys, recipes, reveals, and inventories."""
    old_id = ent.id
    new_id = validated_new_id(raw_id, "Entity", _MAX_ENTITY_ID_LENGTH)
    if new_id == old_id:
        return
    if await template_row_exists(db, WorldEntity, template_id, new_id):
        raise HTTPException(status_code=409, detail=f"Entity ID '{new_id}' already exists")
    if await template_row_exists(db, WorldScene, template_id, new_id):
        raise HTTPException(status_code=409, detail=f"ID '{new_id}' is already taken by a scene")

    ent.id = new_id
    for world_exit in await template_rows(db, WorldExit, template_id):
        if world_exit.item_to_unlock == old_id:
            world_exit.item_to_unlock = new_id
    for other in await template_rows(db, WorldEntity, template_id):
        _rename_entity_refs(other, old_id, new_id)
    await _rename_avatar_refs(db, template_id, old_id, new_id)


def apply_common_fields(ent: WorldEntity, payload: EntityUpdateRequest) -> None:
    copy_given(ent, payload, ("name", "description"))
    apply_vitals(ent, payload)
