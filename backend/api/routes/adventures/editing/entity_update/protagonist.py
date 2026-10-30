"""Updates for the adventure cover and the protagonist."""

from copy import deepcopy
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.editing.common import (
    _get_template_avatar,
    _restore_missing_template_avatar,
)
from backend.api.routes.adventures.editing.entity_update.fields import (
    apply_vitals,
    copy_given,
    given,
    ref_ids,
    template_rows,
)
from backend.api.routes.adventures.editing.entity_update.loadout import resolve_loadout
from backend.api.routes.adventures.editing.schemas import EntityUpdateRequest
from backend.api.routes.adventures.logic import AdventureLogic
from backend.engine.audio.elevenlabs_voices import storable_voice_or_none
from backend.engine.media.image_prompt_context import clean_appearance
from backend.engine.rules.item_logic import normalize_equipment_keys
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.world_entity import WorldEntity

_PROFILE_FIELDS = (
    "name",
    "description",
    "goal",
    "character",
    "strength",
    "intelligence",
    "wisdom",
    "dexterity",
    "charisma",
    "armor_class",
    "exp",
)
_SCRIPT_FIELDS = (
    "on_hp_change_script",
    "on_hp_change_text",
    "on_status_change_script",
    "on_status_change_text",
)
INVENTORY_LOCATION = "INVENTORY"


async def update_cover(
    db: AsyncSession, template_id: str, adv: AdventureTemplate, payload: EntityUpdateRequest
) -> None:
    if given(payload, "name"):
        adv.title = payload.name
    if given(payload, "teaser"):
        adv.teaser = payload.teaser
    if given(payload, "description"):
        adv.original_prompt = payload.description
    if given(payload, "appearance"):
        adv.cover_appearance = clean_appearance(payload.appearance)


def _protagonist_manifest(adv: AdventureTemplate) -> Optional[dict[str, Any]]:
    """A writable copy of the manifest when it has a protagonist section."""
    if not isinstance(adv.original_manifest, dict):
        return None
    manifest = deepcopy(adv.original_manifest)
    return manifest if isinstance(manifest.get("protagonist"), dict) else None


def _store_manifest(adv: AdventureTemplate, manifest: dict[str, Any]) -> None:
    adv.original_manifest = manifest
    flag_modified(adv, "original_manifest")


def _npc_held_ids(npcs: list[WorldEntity]) -> set[str]:
    held: set[str] = set()
    for npc in npcs:
        held |= ref_ids(npc.inventory)
    return held


async def _sync_template_items(db: AsyncSession, template_id: str, carried_ids: set[str]) -> None:
    """Mark carried items as in inventory; put dropped ones (not held by an NPC) back in play."""
    objects = await template_rows(db, WorldEntity, template_id, WorldEntity.entity_type == "OBJECT")
    npc_held = _npc_held_ids(
        await template_rows(db, WorldEntity, template_id, WorldEntity.entity_type == "NPC")
    )
    start_scene: Optional[str] = None
    for obj in objects:
        if obj.id in carried_ids:
            obj.is_in_inventory = True
            obj.current_scene_id = INVENTORY_LOCATION
            continue
        if not obj.is_in_inventory or obj.id in npc_held:
            continue
        obj.is_in_inventory = False
        if obj.current_scene_id == INVENTORY_LOCATION:
            start_scene = start_scene or await AdventureLogic.resolve_initial_scene_id(
                db, template_id
            )
            obj.current_scene_id = start_scene or obj.current_scene_id


async def _update_items(
    db: AsyncSession,
    template_id: str,
    adv: AdventureTemplate,
    avatar: Avatar,
    payload: EntityUpdateRequest,
) -> None:
    inventory = (
        list(payload.inventory or [])
        if given(payload, "inventory")
        else list(avatar.inventory or [])
    )
    equipment = (
        normalize_equipment_keys(payload.equipment)
        if given(payload, "equipment")
        else normalize_equipment_keys(avatar.equipment)
    )
    avatar.inventory, avatar.equipment = resolve_loadout(
        avatar.inventory, avatar.equipment, inventory, equipment
    )
    flag_modified(avatar, "inventory")
    flag_modified(avatar, "equipment")

    inventory_ids = ref_ids(avatar.inventory)
    equipment_ids = ref_ids(list((avatar.equipment or {}).values()))
    await _sync_template_items(db, template_id, inventory_ids | equipment_ids)

    manifest = _protagonist_manifest(adv)
    if manifest is not None:
        manifest["protagonist"]["starting_inventory"] = list(inventory_ids)
        manifest["protagonist"]["starting_equipment"] = dict(avatar.equipment or {})
        _store_manifest(adv, manifest)


def update_protagonist_scripts(
    adv: AdventureTemplate, avatar: Avatar, values: dict[str, Any]
) -> None:
    """HP/status trigger scripts live in ``avatar.stats`` and are mirrored into the manifest."""
    sent = [f for f in _SCRIPT_FIELDS if values.get(f) is not None]
    if not sent:
        return
    stats = dict(avatar.stats or {})
    manifest = _protagonist_manifest(adv)
    for field in sent:
        value = str(values[field]).strip()
        stats[field] = value or None
        if manifest is not None:
            manifest["protagonist"][field] = value
    avatar.stats = stats
    flag_modified(avatar, "stats")
    if manifest is not None:
        _store_manifest(adv, manifest)


async def update_protagonist(
    db: AsyncSession, template_id: str, adv: AdventureTemplate, payload: EntityUpdateRequest
) -> None:
    avatar = await _get_template_avatar(db, template_id)
    if not avatar:
        avatar = await _restore_missing_template_avatar(db, template_id, adv)
    if not avatar:
        return
    copy_given(avatar, payload, _PROFILE_FIELDS)
    if given(payload, "appearance"):
        avatar.appearance = clean_appearance(payload.appearance)
    if given(payload, "voice"):
        avatar.voice = storable_voice_or_none(payload.voice)
    apply_vitals(avatar, payload)
    if given(payload, "inventory") or given(payload, "equipment"):
        await _update_items(db, template_id, adv, avatar, payload)
    sent_scripts = {f: getattr(payload, f) for f in _SCRIPT_FIELDS if given(payload, f)}
    update_protagonist_scripts(adv, avatar, sent_scripts)
