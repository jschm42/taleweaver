"""Builds the first game session of a freshly generated adventure from its template.

The session gets its own copy of the protagonist, world (scenes, exits, entities)
and visuals so that later template edits never leak into running sessions.
"""

import glob
import logging
import os
import shutil
import uuid
from copy import deepcopy
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.logic import AdventureLogic
from backend.core.config import settings
from backend.engine.item_logic import normalize_equipment_keys
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from backend.utils.path_security import (
    data_url_to_local_path,
    ensure_within_data_dir,
    local_path_to_data_url,
    sanitize_path_component,
)

logger = logging.getLogger(__name__)

SAFE_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"}
_AVATAR_COPY_FIELDS = (
    "user_id",
    "name",
    "role",
    "description",
    "goal",
    "character",
    "profile_image",
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


def normalize_data_asset_url(source_url: Optional[str]) -> Optional[str]:
    """Normalize legacy relative asset URLs to the canonical /data/... form."""
    if not isinstance(source_url, str):
        return source_url

    candidate = source_url.strip()
    if not candidate:
        return candidate

    lowered = candidate.lower()
    if lowered.startswith(("http://", "https://", "data:", "blob:")):
        return candidate
    if candidate.startswith("/data/"):
        return candidate
    if candidate.startswith("/"):
        return f"/data{candidate}"
    return f"/data/{candidate.lstrip('/')}"


def _first_existing_file(pattern: str) -> Optional[str]:
    for candidate in glob.iglob(pattern, recursive=True):
        try:
            resolved = ensure_within_data_dir(candidate)
        except ValueError:
            continue
        if os.path.isfile(resolved):
            return resolved
    return None


def find_existing_data_asset_path(filename: str) -> Optional[str]:
    """Search the library and session folders for a file with this name."""
    if not filename:
        return None

    for bucket in ("library", "sessions"):
        root = ensure_within_data_dir(os.path.join(settings.DATA_DIR, "adventures", bucket))
        if not os.path.isdir(root):
            continue
        found = _first_existing_file(os.path.join(root, "**", filename))
        if found:
            return found
    return None


def _existing_source_path(source_path: str) -> Optional[str]:
    """The file itself, or a same-named file elsewhere in the data folders."""
    if os.path.isfile(source_path):
        return source_path
    return find_existing_data_asset_path(os.path.basename(source_path))


def _session_visuals_target(safe_session_id: str, safe_bucket: str, source_path: str) -> str:
    ext = os.path.splitext(source_path)[1].lower()
    if ext not in SAFE_IMAGE_EXTENSIONS:
        ext = ".png"
    target_dir = ensure_within_data_dir(
        os.path.join(
            settings.DATA_DIR, "adventures", "sessions", safe_session_id, "visuals", safe_bucket
        )
    )
    os.makedirs(target_dir, exist_ok=True)
    return ensure_within_data_dir(os.path.join(target_dir, f"{uuid.uuid4().hex}{ext}"))


def _copy_into_session(session_id: str, bucket: str, normalized_url: str) -> Optional[str]:
    """Copied URL; ``normalized_url`` when the source is missing; None on any failure."""
    safe_session_id = sanitize_path_component(session_id)
    safe_bucket = sanitize_path_component(bucket)
    if not safe_session_id or not safe_bucket:
        logger.warning(
            "Skipping asset copy due to invalid session/bucket: %s / %s", session_id, bucket
        )
        return None

    local_path = data_url_to_local_path(normalized_url)
    if not local_path:
        logger.warning("Skipping asset copy for unsafe source URL: %s", normalized_url)
        return None
    source_path = _existing_source_path(local_path)
    if not source_path:
        return normalized_url

    target_path = _session_visuals_target(safe_session_id, safe_bucket, source_path)
    try:
        shutil.copy2(source_path, target_path)
    except OSError:
        logger.exception(
            "Failed copying asset to session folder: %s -> %s", source_path, target_path
        )
        return None
    return local_path_to_data_url(target_path)


def copy_data_asset_to_session(
    session_id: str,
    bucket: str,
    source_url: Optional[str],
    cache: dict[str, str],
) -> Optional[str]:
    """Copy a /data asset into the session's visuals folder and return its new URL.

    Non-/data URLs, unsafe input and copy failures return the original URL.
    """
    normalized_url = normalize_data_asset_url(source_url)
    if not isinstance(normalized_url, str) or not normalized_url.startswith("/data/"):
        return source_url
    if cache.get(normalized_url):
        return cache[normalized_url]

    copied = _copy_into_session(session_id, bucket, normalized_url)
    if copied is None:
        return source_url
    if copied != normalized_url:
        cache[normalized_url] = copied
    return copied


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

    session_avatar = Avatar(
        template_id=template_id,
        **{field: getattr(avatar, field) for field in _AVATAR_COPY_FIELDS},
        stats=deepcopy(avatar.stats or {}),
        inventory=deepcopy(avatar.inventory or []),
        equipment=normalize_equipment_keys(avatar.equipment),
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
        from backend.api.routes.adventures.sessions import (
            _backfill_avatar_items_from_template_entities,
        )

        _backfill_avatar_items_from_template_entities(
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
