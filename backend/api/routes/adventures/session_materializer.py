"""Builds the first game session of a freshly generated adventure from its template.

The session gets its own copy of the protagonist, world (scenes, exits, entities)
and visuals so that later template edits never leak into running sessions.
"""

import logging
from copy import deepcopy
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editing.entity_update.loadout import resolve_loadout
from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.session_assets import copy_data_asset_to_session
from backend.api.routes.adventures.session_items import (
    backfill_avatar_items_from_template_entities,
)
from backend.engine.rules.item_logic import normalize_equipment_keys
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

logger = logging.getLogger(__name__)

_AVATAR_COPY_FIELDS = (
    "user_id",
    "name",
    "role",
    "description",
    "goal",
    "character",
    "appearance",
    "profile_image",
    "voice",
    "hp",
    "max_hp",
    "stamina",
    "max_stamina",
    "mana",
    "max_mana",
    "strength",
    "dexterity",
    "intelligence",
    "wisdom",
    "charisma",
    "armor_class",
)
_EXIT_COPY_FIELDS = (
    "from_scene_id",
    "to_scene_id",
    "label",
    "exit_type",
    "is_locked",
    "lock_description",
    "code_to_unlock",
    "item_to_unlock",
    "rule_to_unlock",
)
_ENTITY_COPY_FIELDS = (
    "id",
    "entity_type",
    "name",
    "description",
    "appearance",
    "current_scene_id",
    "spatial_position",
    "item_type",
    "wearable_slots",
    "is_in_inventory",
    "is_hidden",
    "is_portable",
    "combination_ingredients",
    "reveals_item_id",
    "is_final_state",
    "state_comment",
    "npc_type",
    "movement_type",
    "hp",
    "max_hp",
    "mana",
    "max_mana",
    "stamina",
    "max_stamina",
    "stat_modifier_strength",
    "stat_modifier_dexterity",
    "stat_modifier_intelligence",
    "stat_modifier_wisdom",
    "stat_modifier_charisma",
    "stat_modifier_armor_class",
)


async def _first(db: AsyncSession, statement: Any) -> Any:
    return (await db.execute(statement)).scalars().first()


async def _template_rows(db: AsyncSession, model: Any, template_id: str) -> list[Any]:
    result = await db.execute(
        select(model).where(model.template_id == template_id, model.session_id.is_(None))
    )
    return list(result.scalars().all())


async def _clone_session_avatar(
    db: AsyncSession,
    template_id: str,
    session_id: str,
    avatar: Avatar,
    asset_cache: dict[str, str],
) -> Avatar:
    """Clone the template avatar so the session never mutates the template's protagonist."""
    healed_image = AdventureLogic.heal_template_avatar_profile_image(
        template_id, avatar.profile_image
    )
    if healed_image != avatar.profile_image:
        avatar.profile_image = healed_image
        db.add(avatar)
        await db.flush()

    # Older templates may list an equipped item in the backpack too; the slot wins.
    inventory, equipment = resolve_loadout(
        avatar.inventory,
        avatar.equipment,
        deepcopy(avatar.inventory or []),
        normalize_equipment_keys(avatar.equipment),
    )
    session_avatar = Avatar(
        template_id=template_id,
        **{field: getattr(avatar, field) for field in _AVATAR_COPY_FIELDS},
        stats=deepcopy(avatar.stats or {}),
        inventory=inventory,
        equipment=equipment,
        status_effects=deepcopy(avatar.status_effects or []),
    )
    db.add(session_avatar)
    await db.flush()

    # Template avatars store equipment as ID references (e.g. "MainHand": "LONGSWORD");
    # expand them to full item dicts so the character sheet renders them.
    template_objects = [
        e
        for e in await _template_rows(db, WorldEntity, template_id)
        if e.entity_type == "OBJECT" and e.id
    ]
    if template_objects:
        backfill_avatar_items_from_template_entities(
            session_avatar, {e.id: e for e in template_objects}
        )

    copied_protagonist = copy_data_asset_to_session(
        session_id, "protagonist", session_avatar.profile_image, asset_cache
    )
    if copied_protagonist:
        session_avatar.profile_image = copied_protagonist
    return session_avatar


def _copy_entity(entity: WorldEntity, session_id: str, image_url: Optional[str]) -> WorldEntity:
    return WorldEntity(
        **{field: getattr(entity, field) for field in _ENTITY_COPY_FIELDS},
        session_id=session_id,
        template_id=None,
        image_url=image_url or entity.image_url,
        inventory=deepcopy(entity.inventory),
        metadata_json=deepcopy(entity.metadata_json),
    )


async def _copy_world_to_session(
    db: AsyncSession, template_id: str, session_id: str, asset_cache: dict[str, str]
) -> None:
    """Copy template scenes, exits and entities into the session (skipped if already present)."""
    existing = await db.execute(
        select(WorldScene.id).where(WorldScene.session_id == session_id).limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return

    for scene in await _template_rows(db, WorldScene, template_id):
        image = copy_data_asset_to_session(session_id, "scenes", scene.image_url, asset_cache)
        db.add(
            WorldScene(
                id=scene.id,
                session_id=session_id,
                template_id=None,
                label=scene.label,
                description=scene.description,
                image_url=image or scene.image_url,
            )
        )

    for exit_row in await _template_rows(db, WorldExit, template_id):
        db.add(
            WorldExit(
                session_id=session_id,
                template_id=None,
                **{field: getattr(exit_row, field) for field in _EXIT_COPY_FIELDS},
            )
        )

    for entity in await _template_rows(db, WorldEntity, template_id):
        image = copy_data_asset_to_session(session_id, "entities", entity.image_url, asset_cache)
        db.add(_copy_entity(entity, session_id, image))


async def _store_asset_snapshot(
    db: AsyncSession,
    template_id: str,
    session_id: str,
    session_state: SessionState,
    cover_url: Optional[str],
    protagonist_image: Optional[str],
    has_avatar: bool,
    asset_cache: dict[str, str],
) -> None:
    entity_images: dict[str, Optional[str]] = {}
    for ent in await _template_rows(db, WorldEntity, template_id):
        if not ent.id:
            continue
        copied = copy_data_asset_to_session(session_id, "entities", ent.image_url, asset_cache)
        entity_images[ent.id] = copied or ent.image_url

    entity_states = deepcopy(session_state.entity_states or {})
    raw_snapshot = entity_states.get("__asset_snapshot__")
    snapshot = dict(raw_snapshot) if isinstance(raw_snapshot, dict) else {}
    snapshot["cover"] = cover_url
    snapshot["protagonist"] = protagonist_image if has_avatar else snapshot.get("protagonist")
    snapshot["entity_images"] = entity_images
    entity_states["__asset_snapshot__"] = snapshot
    session_state.entity_states = entity_states


async def materialize_initial_session_from_template(
    db: AsyncSession,
    template_id: str,
    session_id: str,
) -> None:
    """Ensure the initial session is a complete session-owned copy of template world + visuals."""
    game_session = await _first(db, select(GameSession).where(GameSession.id == session_id))
    if not game_session:
        return

    avatar = await _first(db, select(Avatar).where(Avatar.id == game_session.avatar_id))
    session_state = await _first(
        db, select(SessionState).where(SessionState.session_id == session_id)
    )
    template = await _first(
        db, select(AdventureTemplate).where(AdventureTemplate.id == template_id)
    )

    asset_cache: dict[str, str] = {}
    copied_cover = copy_data_asset_to_session(
        session_id, "cover", template.image_url if template else None, asset_cache
    )
    if copied_cover:
        game_session.adventure_image_url = copied_cover

    protagonist_image = avatar.profile_image if avatar else None
    if avatar:
        session_avatar = await _clone_session_avatar(
            db, template_id, session_id, avatar, asset_cache
        )
        game_session.avatar_id = session_avatar.id
        if session_state:
            session_state.avatar_id = session_avatar.id
        protagonist_image = session_avatar.profile_image

    await _copy_world_to_session(db, template_id, session_id, asset_cache)

    if session_state:
        await _store_asset_snapshot(
            db,
            template_id,
            session_id,
            session_state,
            game_session.adventure_image_url,
            protagonist_image,
            avatar is not None,
            asset_cache,
        )
