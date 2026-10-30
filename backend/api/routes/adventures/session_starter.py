"""Starts a new game session from an adventure template.

The session gets its own avatar, world copy (scenes, exits, entities), visuals and
initial state; the adventure's init script and ``on_init`` triggers run once here.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.session_assets import (
    copy_data_asset_to_session,
    ensure_session_dir,
)
from backend.api.routes.adventures.session_cloning import (
    clone_avatar,
    clone_entity,
    clone_exit,
    clone_scene,
)
from backend.api.routes.adventures.session_items import (
    backfill_avatar_items_from_template_entities,
)
from backend.core.config import settings
from backend.engine.rules.item_logic import normalize_equipment_keys
from backend.engine.scripting.context import GameContext
from backend.engine.scripting.dialog import store_pending_dialog
from backend.engine.scripting.gm_directions import store_gm_directions
from backend.engine.scripting.scene_helpers import runner_for_manifest
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.base import utc_now
from backend.models.chat import ChatMessage
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from backend.utils.text_utils import generate_session_id

_DEFAULT_PROTAGONIST_POOL = 200
_DEFAULT_PROTAGONIST_STAT = 10
_DEFAULT_MEMORY_TURNS = 10
_LOCK_KEYS = ("code_to_unlock", "item_to_unlock", "rule_to_unlock")


async def _template_rows(db: AsyncSession, model: Any, template_id: str) -> list[Any]:
    result = await db.execute(
        select(model).where(model.template_id == template_id, model.session_id.is_(None))
    )
    return list(result.scalars().all())


def _avatar_from_manifest(adventure: AdventureTemplate, user_id: str) -> Avatar:
    """Fallback for legacy/imported templates without a template avatar."""
    prot = (adventure.original_manifest or {}).get("protagonist", {})
    pool = {key: prot.get(key, _DEFAULT_PROTAGONIST_POOL) for key in ("hp", "stamina", "mana")}
    stats = {
        key: prot.get(key, _DEFAULT_PROTAGONIST_STAT)
        for key in ("strength", "dexterity", "intelligence", "wisdom", "charisma", "armor_class")
    }
    return Avatar(
        user_id=user_id,
        template_id=adventure.id,
        name=prot.get("name", "You"),
        role=prot.get("role"),
        description=prot.get("description"),
        voice=prot.get("voice"),
        profile_image=prot.get("profile_image"),
        **pool,
        max_hp=pool["hp"],
        max_stamina=pool["stamina"],
        max_mana=pool["mana"],
        **stats,
        stats=prot.get("stats", {}),
        inventory=deepcopy(prot.get("starting_inventory") or prot.get("inventory", [])),
        equipment=normalize_equipment_keys(prot.get("starting_equipment")),
        status_effects=deepcopy(prot.get("status_effects", [])),
    )


async def _template_avatar(db: AsyncSession, template_id: str) -> Optional[Avatar]:
    result = await db.execute(
        select(Avatar)
        .where(Avatar.template_id == template_id)
        .order_by(Avatar.created_at.asc())
        .limit(1)
    )
    template_avatar = result.scalars().first()
    if not template_avatar:
        return None
    # Heal the template avatar image on the fly if it points to a deleted session path.
    healed_image = AdventureLogic.heal_template_avatar_profile_image(
        template_id, template_avatar.profile_image
    )
    if healed_image != template_avatar.profile_image:
        template_avatar.profile_image = healed_image
        db.add(template_avatar)
        await db.flush()
    return template_avatar


async def _build_session_avatar(
    db: AsyncSession,
    adventure: AdventureTemplate,
    user: User,
    template_entities: list[WorldEntity],
) -> Avatar:
    template_id = adventure.id
    template_avatar = await _template_avatar(db, template_id)
    if template_avatar:
        avatar = clone_avatar(template_avatar, user.id, template_id)
    else:
        avatar = _avatar_from_manifest(adventure, user.id)

    # Repair legacy imported avatars: backfill missing item effects/stats from template entities.
    objects_by_id = {
        ent.id: ent for ent in template_entities if ent.entity_type == "OBJECT" and ent.id
    }
    if objects_by_id:
        backfill_avatar_items_from_template_entities(avatar, objects_by_id)
    db.add(avatar)
    await db.flush()
    return avatar


def _initial_lock_state(entity: WorldEntity) -> Optional[dict[str, bool]]:
    if str(getattr(entity, "entity_type", "") or "").upper() != "OBJECT":
        return None
    metadata = dict(getattr(entity, "metadata_json", None) or {})
    if any(metadata.get(key) for key in _LOCK_KEYS):
        return {"locked": True}
    locked = metadata.get("locked")
    return {"locked": locked} if isinstance(locked, bool) else None


def _initial_entity_states(
    adventure: AdventureTemplate,
    asset_snapshot: dict[str, Any],
    template_entities: list[WorldEntity],
) -> dict[str, Any]:
    states: dict[str, Any] = {
        AdventureLogic.SESSION_MANIFEST_SNAPSHOT_KEY: AdventureLogic.build_session_manifest_snapshot(
            adventure
        ),
        "__asset_snapshot__": asset_snapshot,
    }
    for ent in template_entities:
        lock_state = _initial_lock_state(ent)
        if lock_state is not None:
            states[ent.id] = lock_state
    return states


def _init_scripts(adventure: AdventureTemplate) -> tuple[list[Any], Optional[str]]:
    manifest = getattr(adventure, "original_manifest", None) or {}
    scripts = manifest.get("scripts", [])
    init_script = manifest.get("init_script") or getattr(adventure, "init_script", None)
    return scripts, init_script


def _clamp(value: int, change: int, maximum: int) -> int:
    return max(0, min(maximum, value + change))


def _apply_avatar_changes(avatar: Avatar, changes: Any) -> None:
    if changes.player_hp_change:
        avatar.hp = _clamp(avatar.hp, changes.player_hp_change, avatar.max_hp)
    if changes.player_mana_change:
        avatar.mana = _clamp(avatar.mana, changes.player_mana_change, avatar.max_mana)
    if changes.player_stamina_change:
        avatar.stamina = _clamp(avatar.stamina, changes.player_stamina_change, avatar.max_stamina)


def _run_init_scripts(
    adventure: AdventureTemplate,
    avatar: Avatar,
    first_scene_id: str,
    template_entities: list[WorldEntity],
    entity_states: dict[str, Any],
) -> list[str]:
    """Runs init_script / on_init triggers once; returns narrative messages for the chat."""
    scripts, init_script = _init_scripts(adventure)
    has_on_init = any(isinstance(s, dict) and s.get("trigger") == "on_init" for s in scripts)
    if not init_script and not has_on_init:
        return []

    init_context = GameContext(
        avatar_data={
            "name": avatar.name,
            "hp": avatar.hp,
            "mana": avatar.mana,
            "stamina": avatar.stamina,
            "inventory": list(avatar.inventory or []),
            "status_effects": list(avatar.status_effects or []),
        },
        current_scene_id=first_scene_id,
        entities={ent.id: ent.__dict__.copy() for ent in template_entities if ent.id},
        exit_states={},
        quests=deepcopy(adventure.quests or []),
        script_vars={},
        in_game_time=0,
        story_flags={},
        is_debug_enabled=bool(settings.TALEWEAVER_DEBUG_ENABLED),
    )
    runner = runner_for_manifest(
        getattr(adventure, "original_manifest", None),
        scripts,
        init_script or "",
        sequences=getattr(adventure, "sequences", None),
    )
    changes = runner.run_init_script(init_context)

    entity_states["__script_vars__"] = {**changes.var_updates, "__init_script_executed__": True}
    if getattr(changes, "story_flag_updates", None):
        entity_states["__switch_story_flags__"] = dict(changes.story_flag_updates)
    store_pending_dialog(entity_states, changes.pending_dialog)
    store_gm_directions(entity_states, changes.gm_directions)
    _apply_avatar_changes(avatar, changes)
    return [str(message) for message in changes.narrative_messages]


def _memory_settings(user: User, adventure: AdventureTemplate) -> tuple[int, bool]:
    llm_settings = getattr(user, "llm_settings", None) or {}
    configured_turns = llm_settings.get("turns_before_compacting") or llm_settings.get(
        "default_max_memory_turns"
    )
    adventure_turns = getattr(adventure, "max_memory_turns", None)
    turns = adventure_turns if adventure_turns is not None else configured_turns
    compression = bool(llm_settings.get("enable_history_compression", True))
    return turns or _DEFAULT_MEMORY_TURNS, compression


def _build_session_state(
    adventure: AdventureTemplate,
    session_id: str,
    user: User,
    avatar: Avatar,
    first_scene_id: str,
    entity_states: dict[str, Any],
) -> SessionState:
    memory_turns, compression = _memory_settings(user, adventure)
    return SessionState(
        session_id=session_id,
        user_id=user.id,
        template_id=adventure.id,
        avatar_id=avatar.id,
        current_scene_id=first_scene_id,
        in_game_time=0,
        max_memory_turns=memory_turns,
        enable_history_compression=compression,
        quests=deepcopy(adventure.quests or []),
        entity_states=entity_states,
        time_system=adventure.time_system or "calendar",
        time_config=deepcopy(adventure.time_config) if adventure.time_config else None,
        start_datetime=AdventureLogic.resolve_start_datetime(
            adventure.original_manifest, time_config=adventure.time_config
        ),
        plot=adventure.plot,
        rules=adventure.rules,
        completed_condition=adventure.completed_condition,
        gameover_condition=adventure.gameover_condition,
        completed_guard_expression=adventure.completed_guard_expression,
        gameover_guard_expression=adventure.gameover_guard_expression,
        tts_director_notes=adventure.tts_director_notes,
        selected_image_styles=deepcopy(adventure.selected_image_styles),
        selected_tone=deepcopy(adventure.selected_tone),
    )


async def _add_opening_messages(
    db: AsyncSession, session_id: str, adventure: AdventureTemplate, script_messages: list[str]
) -> None:
    license_payload = {
        "creator": adventure.creator,
        "copyright": adventure.copyright,
        "license": adventure.license,
        "license_url": adventure.license_url,
    }
    if any(license_payload.values()):
        # Pin created_at explicitly so the license_info row sorts before the intro text.
        license_msg = ChatMessage(
            session_id=session_id, role="license_info", content=json.dumps(license_payload)
        )
        license_msg.created_at = utc_now()
        db.add(license_msg)
        await db.flush()

    intro_text = (adventure.intro_text or "").strip()
    messages = ([intro_text] if intro_text else []) + script_messages
    for content in messages:
        db.add(ChatMessage(session_id=session_id, role="system", content=content))


def _item_ids(items: Any) -> set[Optional[str]]:
    return {
        item if isinstance(item, str) else (item.get("id") if isinstance(item, dict) else None)
        for item in (items or [])
    }


def _starts_in_inventory(entity: WorldEntity, avatar: Avatar, npc_item_ids: set) -> bool:
    """Keeps ``is_in_inventory`` only for items really held by the avatar or an NPC."""
    if entity.current_scene_id != "INVENTORY":
        return False
    if not avatar.inventory or entity.id in _item_ids(avatar.inventory):
        return bool(entity.is_in_inventory)
    return bool(entity.is_in_inventory) and entity.id in npc_item_ids


async def _clone_template_world(
    db: AsyncSession,
    template_id: str,
    session_id: str,
    avatar: Avatar,
    template_entities: list[WorldEntity],
    entity_images: dict[str, Optional[str]],
    asset_cache: dict[str, str],
) -> None:
    for scene in await _template_rows(db, WorldScene, template_id):
        image = copy_data_asset_to_session(session_id, "scenes", scene.image_url, asset_cache)
        db.add(clone_scene(scene, session_id, image))

    for exit_row in await _template_rows(db, WorldExit, template_id):
        db.add(clone_exit(exit_row, session_id))

    npc_item_ids = set().union(
        *(_item_ids(e.inventory) for e in template_entities if e.entity_type == "NPC")
    )
    for ent in template_entities:
        image = entity_images.get(ent.id)
        if image is None:
            image = copy_data_asset_to_session(session_id, "entities", ent.image_url, asset_cache)
        db.add(
            clone_entity(
                ent,
                session_id,
                image,
                is_in_inventory=_starts_in_inventory(ent, avatar, npc_item_ids),
                unlock_rule=ent.unlock_rule,
            )
        )


def _copy_entity_images(
    session_id: str, template_entities: list[WorldEntity], asset_cache: dict[str, str]
) -> dict[str, Optional[str]]:
    return {
        ent.id: copy_data_asset_to_session(session_id, "entities", ent.image_url, asset_cache)
        or ent.image_url
        for ent in template_entities
        if getattr(ent, "id", None)
    }


async def start_session(db: AsyncSession, adventure: AdventureTemplate, user: User) -> dict:
    """Creates the session rows for ``adventure`` and returns its identifiers (commits)."""
    template_id = adventure.id
    template_entities = await _template_rows(db, WorldEntity, template_id)
    avatar = await _build_session_avatar(db, adventure, user, template_entities)
    first_scene_id = await AdventureLogic.resolve_initial_scene_id(db, template_id)

    new_session = GameSession(
        id=generate_session_id(adventure.title or template_id),
        user_id=user.id,
        avatar_id=avatar.id,
        template_id=template_id,
        adventure_title=adventure.title,
        adventure_image_url=adventure.image_url,
        status="active",
    )
    db.add(new_session)
    await db.flush()
    session_id = new_session.id
    ensure_session_dir(session_id)

    asset_cache: dict[str, str] = {}
    new_session.adventure_image_url = (
        copy_data_asset_to_session(session_id, "cover", adventure.image_url, asset_cache)
        or adventure.image_url
    )
    avatar.profile_image = (
        copy_data_asset_to_session(session_id, "protagonist", avatar.profile_image, asset_cache)
        or avatar.profile_image
    )
    entity_images = _copy_entity_images(session_id, template_entities, asset_cache)
    entity_states = _initial_entity_states(
        adventure,
        {
            "cover": new_session.adventure_image_url,
            "protagonist": avatar.profile_image,
            "entity_images": entity_images,
        },
        template_entities,
    )
    script_messages = _run_init_scripts(
        adventure, avatar, first_scene_id, template_entities, entity_states
    )

    db.add(_build_session_state(adventure, session_id, user, avatar, first_scene_id, entity_states))
    await _add_opening_messages(db, session_id, adventure, script_messages)
    await _clone_template_world(
        db, template_id, session_id, avatar, template_entities, entity_images, asset_cache
    )
    await db.commit()
    return {"game_id": session_id, "template_id": template_id, "avatar_id": avatar.id}
