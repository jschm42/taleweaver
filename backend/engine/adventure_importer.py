import io
import json
import logging
import os
import uuid
import zipfile
from copy import deepcopy
from typing import Any, Optional, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.adventure_format import validate_manifest_version
from backend.core.auth import get_password_hash
from backend.core.config import settings
from backend.engine.world_generator import WorldGenerator
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.utils.text_utils import generate_adventure_id, generate_session_id
from backend.engine.media_engine import MediaEngine

logger = logging.getLogger(__name__)


class AdventureConflictError(Exception):
    """Raised when an adventure being imported already exists."""
    def __init__(self, title: str, existing_version: Optional[str], new_version: Optional[str], template_id: str):
        self.title = title
        self.existing_version = existing_version
        self.new_version = new_version
        self.template_id = template_id
        super().__init__(f"Adventure '{title}' already exists.")


def _build_local_default_user() -> User:
    # Import-only fallback user; password is intentionally random and unknown.
    return User(
        username="local_default_user",
        hashed_password=get_password_hash(uuid.uuid4().hex),
        role="user",
    )

class AdventureTemplateImporter:
    @staticmethod
    async def import_from_directory(db: AsyncSession, directory: str, owner_id: Optional[str] = None, delete_after: bool = False, allow_session: bool = False):
        """Scans a directory for .adv or .adz files and imports them."""
        if not os.path.exists(directory):
            logger.warning(f"Import directory {directory} does not exist.")
            return

        files = [f for f in os.listdir(directory) if f.endswith(".adv") or f.endswith(".adz")]
        if not files:
            return

        logger.info(f"Found {len(files)} potential adventures to import in {directory}")
        
        for filename in files:
            file_path = os.path.join(directory, filename)
            try:
                success = await AdventureTemplateImporter.import_file(db, file_path, owner_id=owner_id, allow_session=allow_session)
                if success and delete_after:
                    os.remove(file_path)
                    logger.info(f"Successfully imported and deleted {filename}")
                elif success:
                    logger.info(f"Successfully imported {filename}")
            except Exception as e:
                logger.error(f"Error during import of {file_path}: {e}")

    @staticmethod
    async def delete_template_for_overwrite(db: AsyncSession, template_id: str):
        """Helper to cleanly delete a template and its assets before an overwrite import."""
        # 1. Delete assets from disk
        await MediaEngine.cleanup_adventure_assets(template_id)
        
        # 2. Delete from DB (cascades should handle the rest if configured, 
        # but for safety we use the existing delete logic if available)
        # Assuming a simple delete for now, or calling a shared delete method.
        # For now, let's just delete the template and assume cascades.
        template = await db.get(AdventureTemplate, template_id)
        if template:
            await db.delete(template)
            await db.flush()

    @staticmethod
    async def import_file(db: AsyncSession, file_path: str, owner_id: Optional[str] = None, allow_session: bool = True, overwrite: bool = False) -> bool:
        """Imports a single file (.adv or .adz)."""
        if file_path.endswith(".adz"):
            with open(file_path, "rb") as f:
                return await AdventureTemplateImporter.import_adz(db, f.read(), owner_id=owner_id, overwrite=overwrite)
        elif file_path.endswith(".adv"):
            with open(file_path, encoding="utf-8") as f:
                payload = json.load(f)
                return await AdventureTemplateImporter.import_adv_manifest(db, payload, owner_id=owner_id, allow_session=allow_session, overwrite=overwrite)
        return False

    @staticmethod
    async def import_adz(db: AsyncSession, adz_data: bytes, owner_id: Optional[str] = None, overwrite: bool = False) -> bool:
        """Logic for ADZ (ZIP) import, including assets."""
        try:
            zip_buffer = io.BytesIO(adz_data)
            
            with zipfile.ZipFile(zip_buffer, "r") as zip_file:
                if "adventure.adv" not in zip_file.namelist():
                    logger.error("Invalid ADZ: Missing adventure.adv")
                    return False
                
                manifest_data = json.loads(zip_file.read("adventure.adv").decode("utf-8"))
                try:
                    validate_manifest_version(manifest_data, require_format=True)
                except ValueError as exc:
                    logger.error("Invalid ADZ format: %s", exc)
                    return False

                adv_data = manifest_data.get("adventure")
                if not adv_data:
                    logger.error("Invalid ADZ: Missing adventure section in manifest")
                    return False

                # Check if template with this title or origin_id already exists for this owner
                origin_id = adv_data.get("origin_id") or manifest_data.get("origin_id")
                
                query = select(AdventureTemplate).where(
                    (AdventureTemplate.owner_id == owner_id) if owner_id else (AdventureTemplate.owner_id == None)
                )
                if origin_id:
                    query = query.where((AdventureTemplate.title == adv_data["title"]) | (AdventureTemplate.origin_id == origin_id))
                else:
                    query = query.where(AdventureTemplate.title == adv_data["title"])
                
                existing_res = await db.execute(query)
                existing = existing_res.scalars().first()
                if existing:
                    if not overwrite:
                        raise AdventureConflictError(
                            title=adv_data["title"],
                            existing_version=existing.version,
                            new_version=adv_data.get("version"),
                            template_id=existing.id
                        )
                    else:
                        logger.info(f"Overwriting existing adventure '{adv_data['title']}'...")
                        await AdventureTemplateImporter.delete_template_for_overwrite(db, existing.id)


                # Create new template ID
                new_template_id = generate_adventure_id(adv_data["title"])
                
                enforcement_mode = adv_data.get("rule_enforcement_mode", "rpg")
                is_strict = adv_data.get("strict_rules") if "strict_rules" in adv_data else (enforcement_mode != "chat")
                
                # Create AdventureTemplate record
                new_template = AdventureTemplate(
                    id=new_template_id,
                    owner_id=owner_id,
                    title=adv_data["title"],
                    version=adv_data.get("version"),
                    original_prompt=adv_data.get("original_prompt") or adv_data.get("context"),
                    strict_rules=is_strict,
                    rule_enforcement_mode=enforcement_mode,
                    time_per_turn=adv_data.get("time_per_turn", 5),
                    pacing_minutes=adv_data.get("pacing_minutes", 5),
                    clock_enabled=adv_data.get("clock_enabled", False),
                    generate_scene_images=adv_data.get("generate_scene_images", False),
                    generate_npc_images=adv_data.get("generate_npc_images", False),
                    generate_item_images=adv_data.get("generate_item_images", False),
                    selected_image_styles=adv_data.get("selected_image_styles") or manifest_data.get("selected_image_styles", []),
                    selected_tone=adv_data.get("selected_tone") or manifest_data.get("selected_tone"),
                    quests=adv_data.get("quests") or manifest_data.get("quests", []),
                    awards=adv_data.get("awards") or manifest_data.get("awards", []),
                    min_scenes=adv_data.get("min_scenes") or manifest_data.get("min_scenes", 1),
                    max_scenes=adv_data.get("max_scenes") or manifest_data.get("max_scenes", 5),
                    container_generation_enabled=(
                        adv_data.get("container_generation_enabled", True)
                        if "container_generation_enabled" in adv_data
                        else manifest_data.get("container_generation_enabled", True)
                    ),
                    max_containers=(
                        int(adv_data.get("max_containers", 8))
                        if "max_containers" in adv_data
                        else int(manifest_data.get("max_containers", 8))
                    ),
                    min_awards=adv_data.get("min_awards") or manifest_data.get("min_awards", 3),
                    max_awards=adv_data.get("max_awards") or manifest_data.get("max_awards", 8),
                    award_generation_enabled=adv_data.get("award_generation_enabled") or manifest_data.get("award_generation_enabled", False),
                    plot=adv_data.get("plot") or manifest_data.get("plot"),
                    rules=adv_data.get("rules") or manifest_data.get("rules"),
                    intro_text=adv_data.get("intro_text") or manifest_data.get("intro_text"),
                    walkthrough=adv_data.get("walkthrough") or manifest_data.get("walkthrough"),
                    completed_condition=adv_data.get("completed_condition") or manifest_data.get("completed_condition"),
                    gameover_condition=adv_data.get("gameover_condition") or manifest_data.get("gameover_condition"),
                    tts_director_notes=adv_data.get("tts_director_notes") or manifest_data.get("tts_director_notes"),
                    starting_timestamp=adv_data.get("starting_timestamp") or manifest_data.get("starting_timestamp", 0),
                    time_system=adv_data.get("time_system") or manifest_data.get("time_system", "calendar"),
                    time_config=adv_data.get("time_config") or manifest_data.get("time_config"),
                    game_over_rules=adv_data.get("game_over_rules") or manifest_data.get("game_over_rules"),
                    allow_dynamic_items=adv_data.get("allow_dynamic_items", True) if "allow_dynamic_items" in adv_data else (manifest_data.get("allow_dynamic_items", True)),
                    can_damage_npcs=adv_data.get("can_damage_npcs", True) if "can_damage_npcs" in adv_data else (manifest_data.get("can_damage_npcs", True)),
                    npcs_can_damage_protagonist=adv_data.get("npcs_can_damage_protagonist", True) if "npcs_can_damage_protagonist" in adv_data else (manifest_data.get("npcs_can_damage_protagonist", True)),
                    cover_source_adventure_id=adv_data.get("cover_source_adventure_id") or manifest_data.get("cover_source_adventure_id"),
                    cover_source_adventure_name=adv_data.get("cover_source_adventure_name") or manifest_data.get("cover_source_adventure_name"),
                    cover_similarity_percent=(
                        adv_data.get("cover_similarity_percent")
                        if "cover_similarity_percent" in adv_data
                        else manifest_data.get("cover_similarity_percent", 50)
                    ),
                    allow_reuse_source_assets=adv_data.get("allow_reuse_source_assets", True) if "allow_reuse_source_assets" in adv_data else manifest_data.get("allow_reuse_source_assets", True),
                    is_adventure_generator=adv_data.get("is_adventure_generator", False) or manifest_data.get("is_adventure_generator", False),
                    is_ready=True,
                    creation_status="Ready",
                    original_manifest=manifest_data,
                    language=adv_data.get("language") or manifest_data.get("language"),
                    origin_id=origin_id
                )

                db.add(new_template)
                
                target_base_dir = os.path.join(settings.DATA_DIR, "adventures", "library", new_template_id)
                os.makedirs(target_base_dir, exist_ok=True)
                
                existing_images_mapping = {} # zip_path -> local_url
                for zip_path in zip_file.namelist():
                    if zip_path.startswith("assets/"):
                        filename = os.path.basename(zip_path)
                        if not filename: continue
                        target_path = os.path.join(target_base_dir, filename)
                        with open(target_path, "wb") as f:
                            f.write(zip_file.read(zip_path))
                        
                        rel_path = os.path.relpath(target_path, settings.DATA_DIR).replace("\\", "/")
                        existing_images_mapping[zip_path] = f"/data/{rel_path}"

                # Reconstruct world
                prot = manifest_data.get("protagonist")
                world_manifest = {
                    "protagonist": {
                        "name": prot.get("name", "You") if prot else "You",
                        "role": prot.get("role", "Hero") if prot else "Hero",
                        "description": prot.get("description", "") if prot else "",
                        "profile_image": prot.get("profile_image") if prot else None,
                        "hp": prot.get("hp", 200) if prot else 200,
                        "max_hp": prot.get("max_hp", prot.get("hp", 200)) if prot else 200,
                        "stamina": prot.get("stamina", 200) if prot else 200,
                        "max_stamina": prot.get("max_stamina", prot.get("stamina", 200)) if prot else 200,
                        "mana": prot.get("mana", 200) if prot else 200,
                        "max_mana": prot.get("max_mana", prot.get("mana", 200)) if prot else 200,
                        "strength": prot.get("strength", 10) if prot else 10,
                        "dexterity": prot.get("dexterity", 10) if prot else 10,
                        "intelligence": prot.get("intelligence", 10) if prot else 10,
                        "wisdom": prot.get("wisdom", 10) if prot else 10,
                        "charisma": prot.get("charisma", 10) if prot else 10,
                        "armor_class": prot.get("armor_class", 10) if prot else 10,
                        "exp": prot.get("exp", 0) if prot else 0,
                        "goal": prot.get("goal", "") if prot else "",
                        "character": prot.get("character", "") if prot else "",
                        "status_effects": prot.get("status_effects", []) if prot else [],
                        "stats": prot.get("stats", {}) if prot else {},
                        "starting_inventory": prot.get("starting_inventory", prot.get("inventory", [])) if prot else [],
                        "starting_equipment": prot.get("starting_equipment", prot.get("equipment", {})) if prot else {}
                    },
                    "scenes": manifest_data.get("scenes", []),
                    "exits": manifest_data.get("exits", []),
                    "npcs": manifest_data.get("npcs", []),
                    "objects": manifest_data.get("objects", []),
                    "quests": manifest_data.get("quests") or adv_data.get("quests", []),
                    "awards": manifest_data.get("awards") or adv_data.get("awards", []),
                    "teaser": manifest_data.get("teaser") or adv_data.get("teaser"),
                    "intro_text": manifest_data.get("intro_text") or adv_data.get("intro_text"),
                    "plot": manifest_data.get("plot") or adv_data.get("plot"),
                    "rules": manifest_data.get("rules") or adv_data.get("rules"),
                    "walkthrough": manifest_data.get("walkthrough") or adv_data.get("walkthrough"),
                    "completed_condition": manifest_data.get("completed_condition") or adv_data.get("completed_condition"),
                    "gameover_condition": manifest_data.get("gameover_condition") or adv_data.get("gameover_condition"),
                    "tts_director_notes": manifest_data.get("tts_director_notes") or adv_data.get("tts_director_notes"),
                }

                default_scene_id = manifest_data["scenes"][0]["id"] if manifest_data.get("scenes") else "START"
                for n in world_manifest["npcs"]:
                    if "start_scene_id" not in n: n["start_scene_id"] = n.get("current_scene_id") or default_scene_id
                for o in world_manifest["objects"]:
                    if "start_scene_id" not in o: o["start_scene_id"] = o.get("current_scene_id") or default_scene_id
                
                image_urls = {}
                if prot and prot.get("profile_image") in existing_images_mapping:
                    image_urls["PROTAGONIST"] = existing_images_mapping[prot["profile_image"]]
                for s in manifest_data.get("scenes", []):
                    if s.get("image_url") in existing_images_mapping: image_urls[s["id"]] = existing_images_mapping[s["image_url"]]
                for n in manifest_data.get("npcs", []):
                    if n.get("image_url") in existing_images_mapping: image_urls[n["id"]] = existing_images_mapping[n["image_url"]]
                for o in manifest_data.get("objects", []):
                    if o.get("image_url") in existing_images_mapping: image_urls[o["id"]] = existing_images_mapping[o["image_url"]]

                user = None
                if owner_id:
                    user_res = await db.execute(select(User).where(User.id == owner_id))
                    user = user_res.scalars().first()

                await WorldGenerator.apply_manifest(
                    db=db,
                    template_id=new_template_id,
                    manifest_dict=world_manifest,
                    user=user,
                    existing_images=image_urls
                )

                # apply_manifest toggles readiness during persistence; imports must remain ready.
                new_template.is_ready = True
                new_template.creation_status = "Ready"
                new_template.creation_error = None
                
                if adv_data.get("image_url") in existing_images_mapping:
                    new_template.image_url = existing_images_mapping[adv_data["image_url"]]
                else:
                    from backend.engine.media_engine import MediaEngine
                    new_template.image_url = await MediaEngine.generate_placeholder(
                        new_template_id, new_template.title, os.path.join(settings.DATA_DIR, "adventures", "library", new_template_id),
                        category="COVER"
                    )
                

                await db.commit()
                # Ensure thumbnails are generated for imported assets
                from backend.engine.media_engine import MediaEngine
                await MediaEngine.ensure_thumbnails(new_template_id)
                return True
        except AdventureConflictError:
            raise
        except Exception:
            logger.exception("ADZ Import failed")
            await db.rollback()
            return False

    @staticmethod
    async def import_adv_manifest(db: AsyncSession, payload: dict[str, Any], owner_id: Optional[str] = None, allow_session: bool = True, overwrite: bool = False) -> bool:
        """Logic for pure .adv (JSON) import."""
        try:
            try:
                validate_manifest_version(payload, require_format=True)
            except ValueError as exc:
                logger.error("Invalid ADV format: %s", exc)
                return False
            
            is_session = payload.get("type") == "SESSION_BUNDLE"
            title = payload.get("adventure", {}).get("title") if is_session else payload.get("title", "Imported AdventureTemplate")
            origin_id = payload.get("adventure", {}).get("origin_id") if is_session else payload.get("origin_id")

            query = select(AdventureTemplate).where(
                (AdventureTemplate.owner_id == owner_id) if owner_id else (AdventureTemplate.owner_id == None)
            )
            if origin_id:
                query = query.where((AdventureTemplate.title == title) | (AdventureTemplate.origin_id == origin_id))
            else:
                query = query.where(AdventureTemplate.title == title)
            
            existing_res = await db.execute(query)
            existing = existing_res.scalars().first()
            if existing:
                if not overwrite:
                    raise AdventureConflictError(
                        title=title,
                        existing_version=existing.version,
                        new_version=payload.get("version") or (payload.get("adventure", {}).get("version") if is_session else None),
                        template_id=existing.id
                    )
                else:
                    logger.info(f"Overwriting existing adventure '{title}'...")
                    await AdventureTemplateImporter.delete_template_for_overwrite(db, existing.id)

            user = None
            if owner_id:
                user_res = await db.execute(select(User).where(User.id == owner_id))
                user = user_res.scalars().first()
            else:
                res = await db.execute(select(User).limit(1))
                user = res.scalars().first()
            
            if not user:
                user = _build_local_default_user()
                db.add(user)
                await db.flush()


            if is_session and allow_session:
                data = payload
                old_adv = data["adventure"]
                
                new_template = AdventureTemplate(
                    id=generate_adventure_id(old_adv['title']),
                    owner_id=user.id,
                    title=old_adv['title'],
                    teaser=old_adv.get("teaser"),
                    version=old_adv.get("version"),
                    original_prompt=old_adv.get("original_prompt") or old_adv.get("context"),
                    image_url=old_adv.get("image_url"),
                    strict_rules=old_adv.get("strict_rules", True),
                    rule_enforcement_mode=old_adv.get("rule_enforcement_mode") or data.get("rule_enforcement_mode") or "rpg",
                    time_per_turn=old_adv.get("time_per_turn", 10),
                    pacing_minutes=old_adv.get("pacing_minutes", 5),
                    clock_enabled=old_adv.get("clock_enabled", False),
                    game_over_rules=old_adv.get("game_over_rules"),
                    quests=old_adv.get("quests", []),
                    awards=old_adv.get("awards", []),
                    original_manifest=old_adv.get("original_manifest"),
                    plot=old_adv.get("plot"),
                    rules=old_adv.get("rules"),
                    intro_text=old_adv.get("intro_text"),
                    walkthrough=old_adv.get("walkthrough"),
                    completed_condition=old_adv.get("completed_condition"),
                    gameover_condition=old_adv.get("gameover_condition"),
                    tts_director_notes=old_adv.get("tts_director_notes"),
                    starting_timestamp=old_adv.get("starting_timestamp", 0),
                    time_system=old_adv.get("time_system", "calendar"),
                    time_config=old_adv.get("time_config"),
                    allow_dynamic_items=old_adv.get("allow_dynamic_items", True),
                    can_damage_npcs=old_adv.get("can_damage_npcs", True),
                    npcs_can_damage_protagonist=old_adv.get("npcs_can_damage_protagonist", True),
                    cover_source_adventure_id=old_adv.get("cover_source_adventure_id"),
                    cover_source_adventure_name=old_adv.get("cover_source_adventure_name"),
                    cover_similarity_percent=old_adv.get("cover_similarity_percent", 50),
                    allow_reuse_source_assets=old_adv.get("allow_reuse_source_assets", True),
                    language=old_adv.get("language") or data.get("language"),
                    origin_id=origin_id,
                    is_adventure_generator=old_adv.get("is_adventure_generator", False),
                    is_ready=True,
                    creation_status="Ready"
                )

                db.add(new_template)
                await db.flush()
                
                await WorldGenerator.apply_manifest(db, new_template.id, data, user=user)

                # Imported session bundles should not enter generation polling state.
                new_template.is_ready = True
                new_template.creation_status = "Ready"
                new_template.creation_error = None
                
                old_state = data.get("game_state") or data.get("session_state")
                old_avatar = data.get("avatar")
                if old_state and old_avatar:
                    new_avatar = Avatar(
                        user_id=user.id, 
                        template_id=new_template.id, 
                        name=old_avatar["name"],
                        role=old_avatar.get("role"),
                        description=old_avatar.get("description"),
                        profile_image=old_avatar.get("profile_image"),
                        hp=old_avatar["hp"], 
                        max_hp=old_avatar.get("max_hp", old_avatar["hp"]),
                        stamina=old_avatar["stamina"], 
                        max_stamina=old_avatar.get("max_stamina", old_avatar["stamina"]),
                        mana=old_avatar["mana"],
                        max_mana=old_avatar.get("max_mana", old_avatar["mana"]),
                        strength=old_avatar.get("strength", 10),
                        dexterity=old_avatar.get("dexterity", 10),
                        intelligence=old_avatar.get("intelligence", 10),
                        wisdom=old_avatar.get("wisdom", 10),
                        charisma=old_avatar.get("charisma", 10),
                        armor_class=old_avatar.get("armor_class", 10),
                        exp=old_avatar.get("exp", 0),
                        goal=old_avatar.get("goal", ""),
                        character=old_avatar.get("character", ""),
                        stats=old_avatar["stats"], 
                        inventory=old_avatar["inventory"],
                        equipment=old_avatar["equipment"], 
                        status_effects=old_avatar.get("status_effects", [])
                    )
                    db.add(new_avatar)
                    await db.flush()
                    
                    new_sess = GameSession(
                        id=generate_session_id(new_template.title or old_adv.get('title') or 'session'),
                        user_id=user.id,
                        avatar_id=new_avatar.id,
                        template_id=new_template.id,
                        adventure_title=new_template.title,
                        adventure_image_url=new_template.image_url
                    )
                    db.add(new_sess)
                    await db.flush()

                    restored_entity_states = old_state.get("entity_states", {})
                    if not isinstance(restored_entity_states, dict):
                        restored_entity_states = {}
                    restored_entity_states = deepcopy(restored_entity_states)
                    restored_entity_states.setdefault(
                        "__manifest_snapshot__",
                        {
                            "adventure": {
                                "id": new_template.id,
                                "title": new_template.title,
                                "version": new_template.version,
                                "image_url": new_template.image_url,
                                "strict_rules": new_template.strict_rules,
                                "rule_enforcement_mode": new_template.rule_enforcement_mode,
                                "time_per_turn": new_template.time_per_turn,
                                "clock_enabled": new_template.clock_enabled,
                                "time_system": new_template.time_system,
                                "time_config": deepcopy(new_template.time_config or {}),
                                "selected_tone": deepcopy(new_template.selected_tone or {}),
                                "selected_image_styles": deepcopy(new_template.selected_image_styles or []),
                                "quests": deepcopy(new_template.quests or []),
                                "awards": deepcopy(new_template.awards or []),
                                "plot": new_template.plot,
                                "rules": new_template.rules,
                                "intro_text": new_template.intro_text,
                                "walkthrough": new_template.walkthrough,
                                "completed_condition": new_template.completed_condition,
                                "gameover_condition": new_template.gameover_condition,
                                "tts_director_notes": new_template.tts_director_notes,
                                "original_prompt": new_template.original_prompt,
                                "allow_dynamic_items": new_template.allow_dynamic_items,
                                "is_adventure_generator": new_template.is_adventure_generator,
                            },
                            "original_manifest": deepcopy(new_template.original_manifest or {}),
                        },
                    )

                    db.add(SessionState(
                        session_id=new_sess.id,
                        current_scene_id=old_state.get("scene_id") or old_state.get("current_scene_id") or "START",
                        in_game_time=old_state.get("in_game_time", 0),
                        inventory=old_state.get("inventory", []),
                        entity_states=restored_entity_states,
                        exit_states=old_state.get("exit_states", {}),
                        discovered_scenes=old_state.get("discovered_scenes", [])
                    ))
                
                await db.commit()
                # Ensure thumbnails are generated for imported assets
                from backend.engine.media_engine import MediaEngine
                await MediaEngine.ensure_thumbnails(new_template.id)
                return True
            else:
                manifest = payload.get("original_manifest") or payload.get("manifest") or payload
                adv_meta = payload.get("adventure") or payload
                
                enforcement_mode = adv_meta.get("rule_enforcement_mode") or manifest.get("rule_enforcement_mode") or "rpg"
                is_strict = adv_meta.get("strict_rules") if "strict_rules" in adv_meta else (manifest.get("strict_rules") if "strict_rules" in manifest else (enforcement_mode != "chat"))
                
                new_template = AdventureTemplate(
                    id=generate_adventure_id(adv_meta.get("title") or manifest.get("title") or "Imported Blueprint"),
                    owner_id=owner_id,
                    title=adv_meta.get("title") or manifest.get("title") or "Imported Blueprint",
                    teaser=adv_meta.get("teaser") or manifest.get("teaser"),
                    version=adv_meta.get("version") or manifest.get("version"),
                    original_prompt=adv_meta.get("original_prompt") or adv_meta.get("context") or manifest.get("description") or "Restored from blueprint.",
                    image_url=adv_meta.get("image_url") or manifest.get("image_url"),
                    strict_rules=is_strict,
                    rule_enforcement_mode=enforcement_mode,
                    time_per_turn=adv_meta.get("time_per_turn", 5),
                    pacing_minutes=adv_meta.get("pacing_minutes", 5),
                    clock_enabled=adv_meta.get("clock_enabled", False),
                    selected_image_styles=adv_meta.get("selected_image_styles") or manifest.get("selected_image_styles", []),
                    selected_tone=adv_meta.get("selected_tone") or manifest.get("selected_tone"),
                    quests=adv_meta.get("quests") or manifest.get("quests") or [],
                    awards=adv_meta.get("awards") or manifest.get("awards") or [],
                    original_manifest=manifest,
                    plot=adv_meta.get("plot") or manifest.get("plot"),
                    rules=adv_meta.get("rules") or manifest.get("rules"),
                    intro_text=adv_meta.get("intro_text") or manifest.get("intro_text"),
                    walkthrough=adv_meta.get("walkthrough") or manifest.get("walkthrough"),
                    completed_condition=adv_meta.get("completed_condition") or manifest.get("completed_condition"),
                    gameover_condition=adv_meta.get("gameover_condition") or manifest.get("gameover_condition"),
                    tts_director_notes=adv_meta.get("tts_director_notes") or manifest.get("tts_director_notes"),
                    starting_timestamp=adv_meta.get("starting_timestamp") or manifest.get("starting_timestamp", 0),
                    time_system=adv_meta.get("time_system") or manifest.get("time_system", "calendar"),
                    time_config=adv_meta.get("time_config") or manifest.get("time_config"),
                    allow_dynamic_items=adv_meta.get("allow_dynamic_items", True) if "allow_dynamic_items" in adv_meta else (manifest.get("allow_dynamic_items", True)),
                    can_damage_npcs=adv_meta.get("can_damage_npcs", True) if "can_damage_npcs" in adv_meta else (manifest.get("can_damage_npcs", True)),
                    npcs_can_damage_protagonist=adv_meta.get("npcs_can_damage_protagonist", True) if "npcs_can_damage_protagonist" in adv_meta else (manifest.get("npcs_can_damage_protagonist", True)),
                    cover_source_adventure_id=adv_meta.get("cover_source_adventure_id") or manifest.get("cover_source_adventure_id"),
                    cover_source_adventure_name=adv_meta.get("cover_source_adventure_name") or manifest.get("cover_source_adventure_name"),
                    cover_similarity_percent=(
                        adv_meta.get("cover_similarity_percent")
                        if "cover_similarity_percent" in adv_meta
                        else manifest.get("cover_similarity_percent", 50)
                    ),
                    allow_reuse_source_assets=adv_meta.get("allow_reuse_source_assets", True) if "allow_reuse_source_assets" in adv_meta else manifest.get("allow_reuse_source_assets", True),
                    language=adv_meta.get("language") or manifest.get("language"),
                    origin_id=origin_id,
                    is_adventure_generator=adv_meta.get("is_adventure_generator", False),
                    is_ready=True,
                    creation_status="Ready"
                )

                db.add(new_template)
                await db.flush()
                
                if not new_template.image_url:
                    from backend.engine.media_engine import MediaEngine
                    new_template.image_url = await MediaEngine.generate_placeholder(
                        new_template.id, new_template.title, os.path.join(settings.DATA_DIR, "adventures", "library", new_template.id),
                        category="COVER"
                    )
                    await db.flush()
                

                # Prepare manifest for apply_manifest to ensure protagonist has starting items
                if "protagonist" in manifest:
                    p = manifest["protagonist"]
                    if "starting_inventory" not in p:
                        p["starting_inventory"] = p.get("inventory", [])
                    if "starting_equipment" not in p:
                        p["starting_equipment"] = p.get("equipment", {})

                default_scene_id = manifest.get("scenes", [{}])[0].get("id") if manifest.get("scenes") else "START"
                for n in manifest.get("npcs", []):
                    if "start_scene_id" not in n:
                        n["start_scene_id"] = n.get("current_scene_id") or n.get("scene_id") or default_scene_id
                for o in manifest.get("objects", []):
                    if "start_scene_id" not in o:
                        o["start_scene_id"] = o.get("current_scene_id") or o.get("scene_id") or default_scene_id

                await WorldGenerator.apply_manifest(db, new_template.id, manifest, user=user)

                # Imports populate world data directly; mark template as fully ready.
                new_template.is_ready = True
                new_template.creation_status = "Ready"
                new_template.creation_error = None
                await db.commit()
                # Ensure thumbnails are generated for imported assets
                from backend.engine.media_engine import MediaEngine
                await MediaEngine.ensure_thumbnails(new_template.id)
                return True
        except AdventureConflictError:
            raise
        except Exception:
            logger.exception("ADV Import failed")
            await db.rollback()
            return False


