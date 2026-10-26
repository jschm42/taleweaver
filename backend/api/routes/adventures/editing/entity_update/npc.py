"""NPC-specific updates."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.editing.entity_update.fields import (
    clipped_or_none,
    copy_given,
    given,
    put_metadata,
    ref_ids,
    template_rows,
    validated_scene_ref,
)
from backend.api.routes.adventures.editing.schemas import EntityUpdateRequest
from backend.engine.elevenlabs_voices import storable_voice_or_none
from backend.models.world_entity import WorldEntity

_NPC_SCRIPT_FIELDS = (
    "on_defeat_script",
    "on_defeat_text",
    "on_protagonist_enters_scene_script",
    "on_protagonist_enters_scene_text",
    "on_interact_script",
    "on_interact_text",
)
INVENTORY_LOCATION = "INVENTORY"


async def _update_inventory(
    db: AsyncSession, template_id: str, npc: WorldEntity, payload: EntityUpdateRequest
) -> None:
    """Store the NPC inventory and move the carried items into inventory."""
    npc.inventory = list(payload.inventory or [])
    flag_modified(npc, "inventory")
    carried = ref_ids(npc.inventory)
    if not carried:
        return
    for item in await template_rows(db, WorldEntity, template_id, WorldEntity.id.in_(carried)):
        item.is_in_inventory = True
        item.current_scene_id = INVENTORY_LOCATION


def _update_voice(npc: WorldEntity, payload: EntityUpdateRequest) -> None:
    """Stores a list voice id or "custom:<id>"; anything else falls back to automatic casting."""
    if given(payload, "voice"):
        npc.voice = storable_voice_or_none(payload.voice)


def _update_movement(npc: WorldEntity, payload: EntityUpdateRequest) -> None:
    if given(payload, "moveable"):
        npc.moveable = bool(payload.moveable)
        npc.movement_type = "MOVABLE" if npc.moveable else "STATIONARY"
    if given(payload, "allowed_scenes"):
        npc.allowed_scenes = list(payload.allowed_scenes or [])
    if given(payload, "notes"):
        npc.notes = (payload.notes or "").strip() or None


async def update_npc(
    db: AsyncSession, template_id: str, npc: WorldEntity, payload: EntityUpdateRequest
) -> None:
    copy_given(npc, payload, ("goal", "character", "is_killable"))
    if given(payload, "inventory"):
        await _update_inventory(db, template_id, npc, payload)
    _update_movement(npc, payload)
    _update_voice(npc, payload)

    metadata_json = dict(npc.metadata_json or {})
    put_metadata(metadata_json, payload, _NPC_SCRIPT_FIELDS, empty_as_none=False)
    npc.metadata_json = metadata_json
    flag_modified(npc, "metadata_json")

    if given(payload, "is_hidden"):
        npc.is_hidden = bool(payload.is_hidden)
    if given(payload, "reveal_rule"):
        npc.reveal_rule = clipped_or_none(payload.reveal_rule, 500)
    if given(payload, "spatial_position"):
        npc.spatial_position = clipped_or_none(payload.spatial_position, 255)
    if given(payload, "current_scene_id"):
        npc.current_scene_id = await validated_scene_ref(db, template_id, payload.current_scene_id)
