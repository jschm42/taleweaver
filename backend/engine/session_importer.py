import io
import json
import logging
import os
import zipfile
import uuid6
from typing import Any, Optional
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from backend.models.world_map import WorldMap

logger = logging.getLogger(__name__)


def _ensure_within_data_dir(path: str) -> str:
    """Validate that a path resolves inside DATA_DIR and return absolute path."""
    data_root = os.path.abspath(settings.DATA_DIR)
    resolved = os.path.abspath(path)
    try:
        if os.path.commonpath([resolved, data_root]) != data_root:
            raise ValueError("Resolved path escapes DATA_DIR.")
    except ValueError as exc:
        raise ValueError("Invalid path: cannot resolve against DATA_DIR.") from exc
    return resolved


def _safe_data_path(*parts: str) -> str:
    """Build a safe path rooted at DATA_DIR."""
    return _ensure_within_data_dir(os.path.join(settings.DATA_DIR, *parts))


def restore_session_paths(data: Any, new_session_id: str) -> Any:
    """
    Recursively replaces relative assets/ paths with the new session's data paths.
    E.g., assets/tts/abc.mp3 -> /data/adventures/sessions/{new_session_id}/tts/abc.mp3
    """
    prefix = f"/data/adventures/sessions/{new_session_id}/"

    if isinstance(data, dict):
        return {k: restore_session_paths(v, new_session_id) for k, v in data.items()}
    elif isinstance(data, list):
        return [restore_session_paths(item, new_session_id) for item in data]
    elif isinstance(data, str):
        if data.startswith("assets/"):
            return data.replace("assets/", prefix, 1)
        return data
    return data


class SessionImporter:
    @staticmethod
    async def import_ads(db: AsyncSession, content: bytes, owner_id: str) -> Optional[str]:
        """
        Unpacks a .ads ZIP file, reconstructs the game session and associated state/entities,
        and extracts assets into the local session directory.

        Returns:
            The new game session ID if successful, else None.
        """
        try:
            zip_buffer = io.BytesIO(content)
            with zipfile.ZipFile(zip_buffer, "r") as zip_file:
                # 1. Read session manifest
                if "session.json" not in zip_file.namelist():
                    logger.error("session.json missing in .ads archive")
                    return None

                manifest = json.loads(zip_file.read("session.json").decode("utf-8"))

                # 2. Setup new IDs
                new_session_id = str(uuid6.uuid7())
                new_avatar_id = str(uuid6.uuid7())

                # Restore the relative assets paths to the new session id
                manifest = restore_session_paths(manifest, new_session_id)

                game_session_data = manifest.get("game_session")
                session_state_data = manifest.get("session_state")
                avatar_data = manifest.get("avatar")
                chat_messages_data = manifest.get("chat_messages") or []
                world_scenes_data = manifest.get("world_scenes") or []
                world_exits_data = manifest.get("world_exits") or []
                world_entities_data = manifest.get("world_entities") or []
                world_map_data = manifest.get("world_map")

                if not game_session_data or not avatar_data or not session_state_data:
                    logger.error("Core session components missing in manifest")
                    return None

                # Check if template still exists in the system
                template_id = game_session_data.get("template_id")
                template_exists = False
                if template_id:
                    template_res = await db.execute(
                        select(AdventureTemplate.id).where(AdventureTemplate.id == template_id)
                    )
                    if template_res.scalar_one_or_none():
                        template_exists = True

                resolved_template_id = template_id if template_exists else None

                # 3. Create Avatar
                avatar = Avatar(
                    id=new_avatar_id,
                    user_id=owner_id,
                    template_id=resolved_template_id,
                    name=avatar_data.get("name", "Hero"),
                    role=avatar_data.get("role"),
                    description=avatar_data.get("description"),
                    goal=avatar_data.get("goal"),
                    character=avatar_data.get("character"),
                    profile_image=avatar_data.get("profile_image"),
                    hp=avatar_data.get("hp", 200),
                    max_hp=avatar_data.get("max_hp", 200),
                    stamina=avatar_data.get("stamina", 200),
                    max_stamina=avatar_data.get("max_stamina", 200),
                    mana=avatar_data.get("mana", 200),
                    max_mana=avatar_data.get("max_mana", 200),
                    exp=avatar_data.get("exp", 0),
                    strength=avatar_data.get("strength", 10),
                    intelligence=avatar_data.get("intelligence", 10),
                    wisdom=avatar_data.get("wisdom", 10),
                    dexterity=avatar_data.get("dexterity", 10),
                    charisma=avatar_data.get("charisma", 10),
                    armor_class=avatar_data.get("armor_class", 10),
                    stats=avatar_data.get("stats", {}),
                    inventory=avatar_data.get("inventory", []),
                    equipment=avatar_data.get("equipment", {}),
                    status_effects=avatar_data.get("status_effects", []),
                )
                db.add(avatar)

                # 4. Create GameSession
                game_session = GameSession(
                    id=new_session_id,
                    user_id=owner_id,
                    avatar_id=new_avatar_id,
                    template_id=resolved_template_id,
                    adventure_title=game_session_data.get("adventure_title"),
                    adventure_image_url=game_session_data.get("adventure_image_url"),
                    status=game_session_data.get("status", "active"),
                    status_note=game_session_data.get("status_note"),
                )
                db.add(game_session)

                # 5. Create SessionState
                session_state = SessionState(
                    session_id=new_session_id,
                    user_id=owner_id,
                    template_id=resolved_template_id,
                    avatar_id=new_avatar_id,
                    current_scene_id=session_state_data.get("current_scene_id", "START"),
                    in_game_time=session_state_data.get("in_game_time", 0),
                    time_system=session_state_data.get("time_system", "calendar"),
                    time_config=session_state_data.get("time_config"),
                    inventory=session_state_data.get("inventory", []),
                    entity_states=session_state_data.get("entity_states", {}),
                    exit_states=session_state_data.get("exit_states", {}),
                    discovered_scenes=session_state_data.get("discovered_scenes", []),
                    quests=session_state_data.get("quests", []),
                    start_datetime=session_state_data.get("start_datetime"),
                    plot=session_state_data.get("plot"),
                    rules=session_state_data.get("rules"),
                    walkthrough=session_state_data.get("walkthrough"),
                    completed_condition=session_state_data.get("completed_condition"),
                    gameover_condition=session_state_data.get("gameover_condition"),
                    tts_director_notes=session_state_data.get("tts_director_notes"),
                    selected_image_styles=session_state_data.get("selected_image_styles"),
                    selected_tone=session_state_data.get("selected_tone"),
                    is_completed=session_state_data.get("is_completed", False),
                    is_debug_enabled=session_state_data.get("is_debug_enabled", False),
                    is_walkthrough_revealed=session_state_data.get("is_walkthrough_revealed", False),
                    allow_dynamic_items=session_state_data.get("allow_dynamic_items", True),
                )
                db.add(session_state)

                # 6. Create ChatMessages
                for msg in chat_messages_data:
                    chat_msg = ChatMessage(
                        id=str(uuid6.uuid7()),
                        session_id=new_session_id,
                        role=msg.get("role"),
                        content=msg.get("content"),
                    )
                    # Restore timestamps if they exist
                    if msg.get("created_at"):
                        try:
                            chat_msg.created_at = datetime.fromisoformat(msg.get("created_at"))
                        except ValueError:
                            pass
                    db.add(chat_msg)

                # 7. Create WorldScenes
                for sc in world_scenes_data:
                    world_sc = WorldScene(
                        id=sc.get("id"),
                        template_id=resolved_template_id,
                        session_id=new_session_id,
                        label=sc.get("label"),
                        description=sc.get("description"),
                        image_url=sc.get("image_url"),
                    )
                    db.add(world_sc)

                # 8. Create WorldExits
                for ex in world_exits_data:
                    world_ex = WorldExit(
                        id=str(uuid6.uuid7()),
                        template_id=resolved_template_id,
                        session_id=new_session_id,
                        from_scene_id=ex.get("from_scene_id"),
                        to_scene_id=ex.get("to_scene_id"),
                        label=ex.get("label"),
                        is_locked=ex.get("is_locked", False),
                        lock_description=ex.get("lock_description"),
                    )
                    db.add(world_ex)

                # 9. Create WorldEntities
                for ent in world_entities_data:
                    world_ent = WorldEntity(
                        id=ent.get("id"),
                        template_id=resolved_template_id,
                        session_id=new_session_id,
                        entity_type=ent.get("entity_type"),
                        name=ent.get("name"),
                        description=ent.get("description"),
                        current_scene_id=ent.get("current_scene_id"),
                        spatial_position=ent.get("spatial_position"),
                        image_url=ent.get("image_url"),
                        item_type=ent.get("item_type"),
                        wearable_slots=ent.get("wearable_slots"),
                        is_in_inventory=ent.get("is_in_inventory", False),
                        is_hidden=ent.get("is_hidden", False),
                        reveal_rule=ent.get("reveal_rule"),
                        unlock_rule=ent.get("unlock_rule"),
                        is_portable=ent.get("is_portable", True),
                        combination_ingredients=ent.get("combination_ingredients"),
                        reveals_item_id=ent.get("reveals_item_id"),
                        is_final_state=ent.get("is_final_state", False),
                        state_comment=ent.get("state_comment"),
                        npc_type=ent.get("npc_type"),
                        movement_type=ent.get("movement_type"),
                        goal=ent.get("goal"),
                        character=ent.get("character"),
                        hp=ent.get("hp"),
                        max_hp=ent.get("max_hp"),
                        mana=ent.get("mana"),
                        max_mana=ent.get("max_mana"),
                        stamina=ent.get("stamina"),
                        max_stamina=ent.get("max_stamina"),
                        voice=ent.get("voice"),
                        stat_modifier_strength=ent.get("stat_modifier_strength"),
                        stat_modifier_dexterity=ent.get("stat_modifier_dexterity"),
                        stat_modifier_intelligence=ent.get("stat_modifier_intelligence"),
                        stat_modifier_wisdom=ent.get("stat_modifier_wisdom"),
                        stat_modifier_charisma=ent.get("stat_modifier_charisma"),
                        stat_modifier_armor_class=ent.get("stat_modifier_armor_class"),
                        is_attackable=ent.get("is_attackable", True),
                        is_killable=ent.get("is_killable", True),
                        inventory=ent.get("inventory", []),
                        metadata_json=ent.get("metadata_json", {}),
                    )
                    db.add(world_ent)

                # 10. Create WorldMap
                if world_map_data:
                    world_map = WorldMap(
                        id=str(uuid6.uuid7()),
                        template_id=resolved_template_id,
                        session_id=new_session_id,
                        nodes=world_map_data.get("nodes", {}),
                        edges=world_map_data.get("edges", []),
                        current_scene_id=world_map_data.get("current_scene_id"),
                    )
                    db.add(world_map)

                # 11. Extract local session files
                new_session_dir = _safe_data_path("adventures", "sessions", new_session_id)
                os.makedirs(new_session_dir, exist_ok=True)

                for zip_info in zip_file.infolist():
                    if zip_info.filename.startswith("assets/") and not zip_info.is_dir():
                        # Relativize destination path within the session directory
                        rel_path = zip_info.filename.replace("assets/", "", 1)
                        dest_path = os.path.join(new_session_dir, rel_path)
                        safe_dest_path = _ensure_within_data_dir(dest_path)

                        os.makedirs(os.path.dirname(safe_dest_path), exist_ok=True)
                        with open(safe_dest_path, "wb") as f:
                            f.write(zip_file.read(zip_info.filename))

            await db.commit()
            return new_session_id

        except Exception as e:
            logger.exception("Import of ADS session failed")
            await db.rollback()
            return None
