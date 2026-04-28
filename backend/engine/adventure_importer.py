import os
import json
import uuid
import zipfile
import io
import shutil
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.models.user import User
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldScene, WorldExit, WorldEntity
from backend.engine.world_generator import WorldGenerator
from backend.core.auth import get_password_hash
from backend.core.adventure_format import validate_manifest_version

logger = logging.getLogger(__name__)


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
    async def import_file(db: AsyncSession, file_path: str, owner_id: Optional[str] = None, allow_session: bool = True) -> bool:
        """Imports a single file (.adv or .adz)."""
        if file_path.endswith(".adz"):
            with open(file_path, "rb") as f:
                return await AdventureTemplateImporter.import_adz(db, f.read(), owner_id=owner_id)
        elif file_path.endswith(".adv"):
            with open(file_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
                return await AdventureTemplateImporter.import_adv_manifest(db, payload, owner_id=owner_id, allow_session=allow_session)
        return False

    @staticmethod
    async def import_adz(db: AsyncSession, adz_data: bytes, owner_id: Optional[str] = None) -> bool:
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

                # Check if template with this title already exists for this owner (if provided)
                query = select(AdventureTemplate).where(AdventureTemplate.title == adv_data["title"])
                if owner_id:
                    query = query.where(AdventureTemplate.owner_id == owner_id)
                
                existing_res = await db.execute(query)
                if existing_res.scalars().first():
                    logger.info(f"AdventureTemplate template '{adv_data['title']}' already exists. Skipping.")
                    return False

                # Create new template ID
                new_template_id = str(uuid.uuid4())
                
                # Create AdventureTemplate record
                new_template = AdventureTemplate(
                    id=new_template_id,
                    owner_id=owner_id,
                    title=adv_data["title"],
                    teaser=adv_data.get("teaser"),
                    context=adv_data.get("context"),
                    strict_rules=adv_data.get("strict_rules", True),
                    rule_enforcement_mode=adv_data.get("rule_enforcement_mode", "rpg"),
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
                    min_awards=adv_data.get("min_awards") or manifest_data.get("min_awards", 3),
                    max_awards=adv_data.get("max_awards") or manifest_data.get("max_awards", 8),
                    award_generation_enabled=adv_data.get("award_generation_enabled") or manifest_data.get("award_generation_enabled", False),
                    is_ready=True,
                    creation_status="Ready",
                    original_manifest=manifest_data
                )
                db.add(new_template)
                
                target_base_dir = os.path.join(settings.DATA_DIR, "adventures", new_template_id)
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
                        "starting_inventory": prot.get("starting_inventory", prot.get("inventory", [])) if prot else [],
                        "starting_equipment": prot.get("starting_equipment", prot.get("equipment", {})) if prot else {}
                    },
                    "scenes": manifest_data.get("scenes", []),
                    "exits": manifest_data.get("exits", []),
                    "npcs": manifest_data.get("npcs", []),
                    "objects": manifest_data.get("objects", []),
                    "quests": manifest_data.get("quests") or adv_data.get("quests", []),
                    "awards": manifest_data.get("awards") or adv_data.get("awards", []),
                    "teaser": manifest_data.get("teaser") or adv_data.get("teaser")
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
                
                if adv_data.get("image_url") in existing_images_mapping:
                    new_template.image_url = existing_images_mapping[adv_data["image_url"]]
                else:
                    from backend.engine.media_engine import MediaEngine
                    new_template.image_url = await MediaEngine.generate_svg_placeholder(
                        new_template_id, new_template.title, os.path.join(settings.DATA_DIR, "adventures", new_template_id), "cover_placeholder.svg"
                    )
                

                await db.commit()
                return True
        except Exception as e:
            logger.exception("ADZ Import failed")
            await db.rollback()
            return False

    @staticmethod
    async def import_adv_manifest(db: AsyncSession, payload: Dict[str, Any], owner_id: Optional[str] = None, allow_session: bool = True) -> bool:
        """Logic for pure .adv (JSON) import."""
        try:
            try:
                validate_manifest_version(payload, require_format=True)
            except ValueError as exc:
                logger.error("Invalid ADV format: %s", exc)
                return False
            
            is_session = payload.get("type") == "SESSION_BUNDLE"
            title = payload.get("adventure", {}).get("title") if is_session else payload.get("title", "Imported AdventureTemplate")
            
            query = select(AdventureTemplate).where(AdventureTemplate.title == title)
            if owner_id:
                query = query.where(AdventureTemplate.owner_id == owner_id)
            
            existing_res = await db.execute(query)
            if existing_res.scalars().first():
                logger.info(f"AdventureTemplate template '{title}' already exists. Skipping.")
                return False

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
                    owner_id=user.id,
                    title=old_adv['title'],
                    teaser=old_adv.get("teaser"),
                    context=old_adv.get("context"),
                    image_url=old_adv.get("image_url"),
                    strict_rules=old_adv.get("strict_rules", True),
                    time_per_turn=old_adv.get("time_per_turn", 10),
                    pacing_minutes=old_adv.get("pacing_minutes", 5),
                    clock_enabled=old_adv.get("clock_enabled", False),
                    game_over_rules=old_adv.get("game_over_rules"),
                    quests=old_adv.get("quests", []),
                    awards=old_adv.get("awards", []),
                    original_manifest=old_adv.get("original_manifest"),
                    is_ready=True,
                    creation_status="Ready"
                )
                db.add(new_template)
                await db.flush()
                
                await WorldGenerator.apply_manifest(db, new_template.id, data, user=user)
                
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
                        stamina=old_avatar["stamina"], 
                        mana=old_avatar["mana"],
                        stats=old_avatar["stats"], 
                        inventory=old_avatar["inventory"],
                        equipment=old_avatar["equipment"], 
                        status_effects=old_avatar.get("status_effects", [])
                    )
                    db.add(new_avatar)
                    await db.flush()
                    
                    new_sess = GameSession(
                        user_id=user.id,
                        avatar_id=new_avatar.id,
                        template_id=new_template.id,
                        adventure_title=new_template.title,
                        adventure_image_url=new_template.image_url
                    )
                    db.add(new_sess)
                    await db.flush()

                    db.add(SessionState(
                        session_id=new_sess.id,
                        current_scene_id=old_state.get("scene_id") or old_state.get("current_scene_id") or "START",
                        in_game_time=old_state.get("in_game_time", 0),
                        inventory=old_state.get("inventory", []),
                        entity_states=old_state.get("entity_states", {}),
                        exit_states=old_state.get("exit_states", {}),
                        discovered_scenes=old_state.get("discovered_scenes", [])
                    ))
                
                await db.commit()
                return True
            else:
                manifest = payload.get("original_manifest") or payload.get("manifest") or payload
                adv_meta = payload.get("adventure") or payload
                
                new_template = AdventureTemplate(
                    owner_id=owner_id,
                    title=adv_meta.get("title") or manifest.get("title") or "Imported Blueprint",
                    teaser=adv_meta.get("teaser") or manifest.get("teaser"),
                    context=adv_meta.get("context") or manifest.get("description") or "Restored from blueprint.",
                    image_url=adv_meta.get("image_url") or manifest.get("image_url"),
                    strict_rules=adv_meta.get("strict_rules", True),
                    time_per_turn=adv_meta.get("time_per_turn", 5),
                    pacing_minutes=adv_meta.get("pacing_minutes", 5),
                    clock_enabled=adv_meta.get("clock_enabled", False),
                    selected_image_styles=adv_meta.get("selected_image_styles") or manifest.get("selected_image_styles", []),
                    selected_tone=adv_meta.get("selected_tone") or manifest.get("selected_tone"),
                    quests=adv_meta.get("quests") or manifest.get("quests") or [],
                    awards=adv_meta.get("awards") or manifest.get("awards") or [],
                    original_manifest=manifest,
                    is_ready=True,
                    creation_status="Ready"
                )
                db.add(new_template)
                await db.flush()
                
                if not new_template.image_url:
                    from backend.engine.media_engine import MediaEngine
                    new_template.image_url = await MediaEngine.generate_svg_placeholder(
                        new_template.id, new_template.title, os.path.join(settings.DATA_DIR, "adventures", new_template.id), "cover_placeholder.svg"
                    )
                    await db.flush()
                

                # Prepare manifest for apply_manifest to ensure protagonist has starting items
                if "protagonist" in manifest:
                    p = manifest["protagonist"]
                    if "starting_inventory" not in p:
                        p["starting_inventory"] = p.get("inventory", [])
                    if "starting_equipment" not in p:
                        p["starting_equipment"] = p.get("equipment", {})

                await WorldGenerator.apply_manifest(db, new_template.id, manifest, user=user)
                await db.commit()
                return True
        except Exception as e:
            logger.exception("ADV Import failed")
            await db.rollback()
            return False

