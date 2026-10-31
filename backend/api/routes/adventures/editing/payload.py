"""Serializes the editor world state (scenes, entities, exits, protagonist)."""

import logging
from types import SimpleNamespace
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editing.common import (
    _get_owned_adventure_or_404,
    _get_template_avatar,
    _is_npc_entity,
    _is_object_entity,
    _resolve_library_image_url,
    _restore_missing_template_avatar,
)
from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.schemas import (
    AdventureTemplateDebugResponse,
)
from backend.api.routes.adventures.session_items import backfill_avatar_items_from_template_entities
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.engine.media.media_engine import MediaEngine
from backend.engine.world.scene_fields import SCENE_SCRIPT_FIELDS
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Editor"])


_EXIT_SCRIPT_FIELDS = (
    "unlock_expression",
    "on_unlock_success_script",
    "on_unlock_success_text",
    "on_unlock_failure_script",
    "on_unlock_failure_text",
    "on_open_exit_script",
    "on_open_exit_text",
    "on_exit_used_script",
    "on_exit_used_text",
)
_AVATAR_STATS_SCRIPT_FIELDS = (
    "on_hp_change_script",
    "on_hp_change_text",
    "on_status_change_script",
    "on_status_change_text",
)
# Object metadata keys flattened onto the payload as strings for the editor UI.
_OBJECT_METADATA_FIELDS = (
    "code_to_unlock",
    "item_to_unlock",
    "rule_to_unlock",
    "unlock_expression",
    "on_unlock_success_script",
    "on_unlock_success_text",
    "on_unlock_failure_script",
    "on_unlock_failure_text",
    "on_items_added_script",
    "on_items_added_text",
    "on_read_script",
    "on_read_text",
    "craft_guard_expression",
    "on_craft_success_script",
    "on_craft_success_text",
    "on_craft_failure_script",
    "on_craft_failure_text",
    "on_equip_script",
    "on_equip_text",
    "on_unequip_script",
    "on_unequip_text",
)
_OBJECT_STAT_LABELS = (
    ("stat_modifier_strength", "STR"),
    ("stat_modifier_dexterity", "DEX"),
    ("stat_modifier_intelligence", "INT"),
    ("stat_modifier_wisdom", "WIS"),
    ("stat_modifier_charisma", "CHA"),
    ("stat_modifier_armor_class", "AC"),
)
_LOCK_KEYS = ("code_to_unlock", "item_to_unlock", "rule_to_unlock", "unlock_expression")


def _text_fields(source: Any, fields: tuple[str, ...]) -> dict[str, str]:
    getter = source.get if isinstance(source, dict) else lambda f: getattr(source, f, "")
    return {field: str(getter(field) or "") for field in fields}


def _scene_extras(scene: WorldScene, data: dict[str, Any]) -> dict[str, Any]:
    decor = data.get("decorative_objects")
    decor = decor if isinstance(decor, list) else []
    return {
        "decorative_objects": [str(d) for d in decor if isinstance(d, (str, int, float))],
        **_text_fields(scene, SCENE_SCRIPT_FIELDS),
    }


def _exit_extras(world_exit: WorldExit, _data: dict[str, Any]) -> dict[str, Any]:
    return _text_fields(world_exit, _EXIT_SCRIPT_FIELDS)


def _avatar_extras(avatar: Avatar, _data: dict[str, Any]) -> dict[str, Any]:
    return _text_fields(dict(avatar.stats or {}), _AVATAR_STATS_SCRIPT_FIELDS)


def _adventure_extras(adventure: AdventureTemplate, _data: dict[str, Any]) -> dict[str, Any]:
    return {
        "scripts": list(getattr(adventure, "scripts", []) or []),
        "init_script": getattr(adventure, "init_script", None),
    }


def _switch_fields(metadata_json: dict[str, Any]) -> dict[str, Any]:
    switch_config = metadata_json.get("switch") or {}

    def pick(flat_key: str, nested_key: str, default: Any) -> Any:
        return metadata_json.get(flat_key) or switch_config.get(nested_key) or default

    return {
        "switch_states": pick("switch_states", "states", []),
        "switch_state_labels": pick("switch_state_labels", "state_labels", {}),
        "switch_initial_state": pick("switch_initial_state", "initial_state", ""),
        "switch_transitions": pick("switch_transitions", "transitions", []),
        "on_success_script": pick("on_success_script", "on_success_script", ""),
        "on_failure_script": pick("on_failure_script", "on_failure_script", ""),
    }


def _object_extras(entity: WorldEntity) -> dict[str, Any]:
    metadata_json = dict(entity.metadata_json or {})
    locked = metadata_json.get("locked")
    if not isinstance(locked, bool):
        locked = any(metadata_json.get(k) for k in _LOCK_KEYS)
    return {
        "stats": {
            label: getattr(entity, col)
            for col, label in _OBJECT_STAT_LABELS
            if getattr(entity, col)
        },
        **_text_fields(metadata_json, _OBJECT_METADATA_FIELDS),
        "locked": locked,
        **_switch_fields(metadata_json),
    }


def _entity_extras(entity: WorldEntity, _data: dict[str, Any]) -> dict[str, Any]:
    """Group stats for easier frontend access."""
    if entity.entity_type == "NPC":
        return {"stats": {"hp": entity.hp, "mana": entity.mana, "stamina": entity.stamina}}
    if entity.entity_type == "OBJECT":
        return _object_extras(entity)
    return {}


_EXTRAS_BY_TYPE = (
    (WorldScene, _scene_extras),
    (WorldExit, _exit_extras),
    (Avatar, _avatar_extras),
    (AdventureTemplate, _adventure_extras),
    (WorldEntity, _entity_extras),
)


def _serialize_model(obj):
    if not obj:
        return None
    data = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    for model_type, extras in _EXTRAS_BY_TYPE:
        if isinstance(obj, model_type):
            data.update(extras(obj, data))
    return data


def _serialize_protagonist_with_items(
    avatar: Optional[Avatar], entities: list[WorldEntity]
) -> Optional[dict[str, Any]]:
    """Serialize the avatar with inventory/equipment backfilled as full item dicts.

    Works on a detached copy: mutating the ORM row would be autoflushed and persisted by any
    later commit (e.g. the validation run), rewriting the stored ID-list inventory.
    """
    if not avatar:
        return None
    payload = _serialize_model(avatar)
    entities_by_id = {ent.id: ent for ent in entities if getattr(ent, "id", None)}
    items_view = SimpleNamespace(
        inventory=list(avatar.inventory or []), equipment=dict(avatar.equipment or {})
    )
    if entities_by_id:
        backfill_avatar_items_from_template_entities(items_view, entities_by_id)
    payload["inventory"] = items_view.inventory
    payload["equipment"] = items_view.equipment
    return payload


async def _build_adventure_editor_assets(
    template_id: str, db: AsyncSession
) -> AdventureTemplateDebugResponse:
    """Builds full world/editor asset state for a specific adventure."""
    adv_res = await db.execute(select(AdventureTemplate).where(AdventureTemplate.id == template_id))
    adventure = adv_res.scalars().first()
    if not adventure:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found")

    try:
        await MediaEngine.ensure_thumbnails(template_id)
    except Exception as exc:
        logger.warning("Thumbnail ensure failed for adventure %s: %s", template_id, exc)

    scene_res = await db.execute(
        select(WorldScene).where(
            WorldScene.template_id == template_id,
            WorldScene.session_id.is_(None),
        )
    )
    scenes = scene_res.scalars().all()

    exit_res = await db.execute(
        select(WorldExit).where(
            WorldExit.template_id == template_id,
            WorldExit.session_id.is_(None),
        )
    )
    exits = exit_res.scalars().all()

    entity_res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.session_id.is_(None),
        )
    )
    entities = entity_res.scalars().all()

    # Self-heal: If world tables have no scenes yet but original_manifest has world data, restore them
    if (
        not scenes
        and isinstance(adventure.original_manifest, dict)
        and adventure.original_manifest.get("scenes")
    ):
        try:
            from backend.engine.world.world_generator import WorldGenerator
            from backend.models.user import User

            user = None
            if adventure.owner_id:
                user_res = await db.execute(select(User).where(User.id == adventure.owner_id))
                user = user_res.scalars().first()
            await WorldGenerator.apply_manifest(
                db=db,
                template_id=template_id,
                manifest_dict=adventure.original_manifest,
                user=user,
            )
            adventure.is_ready = True
            adventure.creation_status = "Ready"
            await db.commit()

            scene_res = await db.execute(
                select(WorldScene).where(
                    WorldScene.template_id == template_id,
                    WorldScene.session_id.is_(None),
                )
            )
            scenes = scene_res.scalars().all()
            exit_res = await db.execute(
                select(WorldExit).where(
                    WorldExit.template_id == template_id,
                    WorldExit.session_id.is_(None),
                )
            )
            exits = exit_res.scalars().all()
            entity_res = await db.execute(
                select(WorldEntity).where(
                    WorldEntity.template_id == template_id,
                    WorldEntity.session_id.is_(None),
                )
            )
            entities = entity_res.scalars().all()
        except Exception as exc:
            logger.warning(
                "Failed to auto-restore template entities from manifest for %s: %s",
                template_id,
                exc,
            )

    # Heal stale library image URLs (e.g. slug changed after import/reuse) without failing the editor UI.
    for scene in scenes:
        scene.image_url = _resolve_library_image_url(getattr(scene, "image_url", None))
    for ent in entities:
        ent.image_url = _resolve_library_image_url(getattr(ent, "image_url", None))

    avatar = await _get_template_avatar(db, template_id)
    if not avatar:
        avatar = await _restore_missing_template_avatar(db, template_id, adventure)

    protagonist_payload = _serialize_protagonist_with_items(avatar, entities)

    db_scenes = [_serialize_model(s) for s in scenes]
    db_npcs = [_serialize_model(ent) for ent in entities if _is_npc_entity(ent)]
    db_objects = [_serialize_model(ent) for ent in entities if _is_object_entity(ent)]
    db_exits = [_serialize_model(ex) for ex in exits]

    adventure_payload = _serialize_model(adventure) or {}
    adventure_payload["start_scene_id"] = await AdventureLogic.resolve_initial_scene_id(
        db, template_id
    )

    return AdventureTemplateDebugResponse(
        adventure=adventure_payload,
        protagonist=protagonist_payload,
        scenes=db_scenes,
        npcs=db_npcs,
        objects=db_objects,
        exits=db_exits,
        entities_all=[_serialize_model(ent) for ent in entities],
    )


@router.get("/{template_id}/editor/assets", response_model=AdventureTemplateDebugResponse)
async def get_adventure_editor_assets(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns full world/editor asset data for the AdventureTemplate Editor UI (owner only)."""
    await _get_owned_adventure_or_404(db, template_id, current_user.id)
    return await _build_adventure_editor_assets(template_id, db)


@router.get("/{template_id}/debug", response_model=AdventureTemplateDebugResponse)
async def get_adventure_debug(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Legacy debug endpoint (owner only)."""
    await _get_owned_adventure_or_404(db, template_id, current_user.id)
    return await _build_adventure_editor_assets(template_id, db)
