"""Item (OBJECT) updates: placement, type change, and type-specific configuration."""

from copy import deepcopy
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.editing.common import _get_template_avatar
from backend.api.routes.adventures.editing.entity_update import item_metadata
from backend.api.routes.adventures.editing.entity_update.fields import (
    clipped_or_none,
    copy_given,
    given,
    ref_id,
    validated_scene_ref,
)
from backend.api.routes.adventures.editing.schemas import EntityUpdateRequest
from backend.engine.crafting_recipes import is_recipe, recipe_results
from backend.models.adventure_template import AdventureTemplate
from backend.models.world_entity import WorldEntity

INVENTORY_LOCATION = "INVENTORY"
ITEM_TYPES = (
    "DEFAULT",
    "CONSUMABLE",
    "WEARABLE",
    "WEAPON",
    "CONSTRUCTABLE",
    "READABLE",
    "CONTAINER",
    "SWITCH",
)
_MAX_READABLE_DESCRIPTION = 200


def _without_item(entries: list[Any], item_id: str) -> list[Any]:
    return [e for e in entries if ref_id(e) != item_id]


def _drop_from_manifest_inventory(adv: AdventureTemplate, item_id: str) -> None:
    if not isinstance(adv.original_manifest, dict):
        return
    manifest = deepcopy(adv.original_manifest)
    protagonist = manifest.get("protagonist")
    if not isinstance(protagonist, dict):
        return
    start_inv = protagonist.get("starting_inventory") or protagonist.get("inventory") or []
    if not isinstance(start_inv, list):
        return
    protagonist["starting_inventory"] = _without_item(start_inv, item_id)
    adv.original_manifest = manifest
    flag_modified(adv, "original_manifest")


async def _take_from_protagonist(
    db: AsyncSession, template_id: str, adv: AdventureTemplate, item_id: str
) -> None:
    """An item placed in a scene is no longer carried or equipped by the protagonist."""
    avatar = await _get_template_avatar(db, template_id)
    if not avatar:
        return
    changed = False
    inventory = list(avatar.inventory or [])
    if inventory and len(_without_item(inventory, item_id)) != len(inventory):
        avatar.inventory = _without_item(inventory, item_id)
        flag_modified(avatar, "inventory")
        changed = True
    equipment = dict(avatar.equipment or {})
    if any(ref_id(v) == item_id for v in equipment.values()):
        avatar.equipment = {
            slot: (None if ref_id(v) == item_id else v) for slot, v in equipment.items()
        }
        flag_modified(avatar, "equipment")
        changed = True
    if changed:
        _drop_from_manifest_inventory(adv, item_id)


async def _update_placement(
    db: AsyncSession,
    template_id: str,
    adv: AdventureTemplate,
    item: WorldEntity,
    payload: EntityUpdateRequest,
) -> None:
    if given(payload, "current_scene_id"):
        scene_id = await validated_scene_ref(db, template_id, payload.current_scene_id)
        item.current_scene_id = scene_id
        if scene_id != INVENTORY_LOCATION:
            item.is_in_inventory = False
            await _take_from_protagonist(db, template_id, adv, item.id)
    if given(payload, "is_in_inventory"):
        item.is_in_inventory = bool(payload.is_in_inventory)


def _apply_type_change(item: WorldEntity, payload: EntityUpdateRequest) -> Optional[str]:
    """Set the new item type (validated). Returns it when the type actually changed.

    Applied before the type-specific sections so they run against the NEW type
    (e.g. CONTAINER -> READABLE keeps the readable text the user just entered).
    """
    new_type = str(payload.item_type or "").strip().upper()
    if not new_type or new_type == str(item.item_type or "").upper():
        return None
    if new_type not in ITEM_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                "item_type must be one of DEFAULT, CONSUMABLE, WEARABLE, "
                "WEAPON, CONSTRUCTABLE, READABLE, CONTAINER, SWITCH."
            ),
        )
    item.item_type = new_type
    return new_type


def _update_metadata(item: WorldEntity, payload: EntityUpdateRequest, item_type: str) -> None:
    metadata_json = dict(item.metadata_json or {})
    item_metadata.update_container(item, metadata_json, payload, item_type == "CONTAINER")
    if given(payload, "inventory"):
        item.inventory = payload.inventory
        flag_modified(item, "inventory")
    item_metadata.update_readable(metadata_json, payload, item_type == "READABLE")
    item_metadata.update_constructable(metadata_json, payload, item_type == "CONSTRUCTABLE")
    item_metadata.update_item_events(metadata_json, payload)
    item_metadata.update_pickup_trigger(metadata_json, payload)
    item_metadata.update_switch(metadata_json, payload, item_type == "SWITCH")
    item_metadata.update_consumable(metadata_json, payload, item_type == "CONSUMABLE")
    item.metadata_json = metadata_json
    flag_modified(item, "metadata_json")


def _update_columns(item: WorldEntity, payload: EntityUpdateRequest) -> None:
    copy_given(item, payload, ("is_portable", "stat_modifier_strength"))
    for field in ("wearable_slots", "combination_ingredients"):
        if given(payload, field):
            setattr(item, field, getattr(payload, field))
            flag_modified(item, field)
    if given(payload, "spatial_position"):
        item.spatial_position = clipped_or_none(payload.spatial_position, 255)
    if given(payload, "reveals_item_id"):
        item.reveals_item_id = str(payload.reveals_item_id or "").strip().upper() or None


async def hide_recipe_results(db: AsyncSession, template_id: str, recipe: WorldEntity) -> None:
    """Items produced by a recipe start hidden; crafting (or their own reveal path) reveals them."""
    result_ids = recipe_results(recipe) if is_recipe(recipe) else []
    if not result_ids:
        return
    rows = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.session_id.is_(None),
            func.upper(WorldEntity.id).in_(result_ids),
        )
    )
    for result in rows.scalars().all():
        result.is_hidden = True


def _update_visibility(item: WorldEntity, payload: EntityUpdateRequest, type_changed: bool) -> None:
    """CONSTRUCTABLE recipes are meta items: always hidden, never revealed by a rule."""
    if item.item_type == "CONSTRUCTABLE":
        item.is_hidden = True
        item.reveal_rule = None
        return
    if given(payload, "is_hidden"):
        item.is_hidden = bool(payload.is_hidden)
    elif type_changed:
        item.is_hidden = False
    if given(payload, "reveal_rule"):
        item.reveal_rule = clipped_or_none(payload.reveal_rule, 500)


async def update_item(
    db: AsyncSession,
    template_id: str,
    adv: AdventureTemplate,
    item: WorldEntity,
    payload: EntityUpdateRequest,
) -> None:
    await _update_placement(db, template_id, adv, item, payload)
    new_type = _apply_type_change(item, payload) if given(payload, "item_type") else None
    item_type = str(item.item_type or "").upper()
    description_too_long = len(payload.description or "") > _MAX_READABLE_DESCRIPTION
    if given(payload, "description") and item_type == "READABLE" and description_too_long:
        raise HTTPException(
            status_code=400,
            detail="description must be at most 200 characters for READABLE objects.",
        )
    _update_metadata(item, payload, item_type)
    _update_columns(item, payload)
    _update_visibility(item, payload, new_type is not None)
    await hide_recipe_results(db, template_id, item)
