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
from backend.models.adventure import Adventure
from backend.models.avatar import Avatar
from backend.models.game_state import GameState
from backend.models.world_entity import WorldScene, WorldExit, WorldEntity
from backend.engine.world_generator import WorldGenerator

logger = logging.getLogger(__name__)

class AdventureImporter:
    @staticmethod
    async def import_from_directory(db: AsyncSession, directory: str, delete_after: bool = False):
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
                # Check if already imported (basic check by title/filename)
                # We'll use the filename as a hint if title is not easily available before parsing
                success = await AdventureImporter.import_file(db, file_path)
                if success and delete_after:
                    os.remove(file_path)
                    logger.info(f"Successfully imported and deleted {filename}")
                elif success:
                    logger.info(f"Successfully imported {filename}")
            except Exception as e:
                logger.error(f"Error during import of {file_path}: {e}")

    @staticmethod
    async def import_file(db: AsyncSession, file_path: str) -> bool:
        """Imports a single file (.adv or .adz)."""
        if file_path.endswith(".adz"):
            return await AdventureImporter._import_adz(db, file_path)
        elif file_path.endswith(".adv"):
            return await AdventureImporter._import_adv(db, file_path)
        return False

    @staticmethod
    async def _import_adz(db: AsyncSession, file_path: str) -> bool:
        """Logic for ADZ (ZIP) import, including assets."""
        try:
            with open(file_path, "rb") as f:
                zip_content = f.read()
            
            zip_buffer = io.BytesIO(zip_content)
            
            with zipfile.ZipFile(zip_buffer, "r") as zip_file:
                if "adventure.adv" not in zip_file.namelist():
                    logger.error(f"Invalid ADZ {file_path}: Missing adventure.adv")
                    return False
                
                manifest_data = json.loads(zip_file.read("adventure.adv").decode("utf-8"))
                adv_data = manifest_data.get("adventure")
                if not adv_data:
                    logger.error(f"Invalid ADZ {file_path}: Missing adventure section in manifest")
                    return False

                # Check if adventure with this title already exists
                existing_res = await db.execute(select(Adventure).where(Adventure.title == adv_data["title"]))
                if existing_res.scalars().first():
                    logger.info(f"Adventure '{adv_data['title']}' already exists. Skipping.")
                    return False

                # Create new adventure ID
                new_adv_id = str(uuid.uuid4())
                
                # Create Adventure record
                new_adv = Adventure(
                    id=new_adv_id,
                    title=adv_data["title"],
                    context=adv_data.get("context"),
                    strict_rules=adv_data.get("strict_rules", True),
                    rule_enforcement_mode=adv_data.get("rule_enforcement_mode", "rpg"),
                    time_per_turn=adv_data.get("time_per_turn", 5),
                    pacing_minutes=adv_data.get("pacing_minutes", 5),
                    clock_enabled=adv_data.get("clock_enabled", False),
                    heartbeat_enabled=adv_data.get("heartbeat_enabled", False),
                    generate_scene_images=adv_data.get("generate_scene_images", False),
                    generate_npc_images=adv_data.get("generate_npc_images", False),
                    generate_item_images=adv_data.get("generate_item_images", False),
                    selected_image_styles=adv_data.get("selected_image_styles", []),
                    selected_tone=adv_data.get("selected_tone"),
                    is_ready=True,
                    creation_status="Ready",
                )
                db.add(new_adv)
                
                target_base_dir = os.path.join(settings.DATA_DIR, "adventures", new_adv_id)
                os.makedirs(target_base_dir, exist_ok=True)
                
                existing_images_mapping = {} # zip_path -> local_url
                for zip_path in zip_file.namelist():
                    if zip_path.startswith("assets/"):
                        filename = os.path.basename(zip_path)
                        if not filename: continue # skip directory entries
                        target_path = os.path.join(target_base_dir, filename)
                        with open(target_path, "wb") as f:
                            f.write(zip_file.read(zip_path))
                        
                        rel_path = os.path.relpath(target_path, settings.DATA_DIR).replace("\\", "/")
                        existing_images_mapping[zip_path] = f"/data/{rel_path}"

                # Create Avatar
                prot = manifest_data.get("protagonist")
                if prot:
                    result = await db.execute(select(User).limit(1))
                    user = result.scalars().first()
                    if not user:
                        user = User(username="local_default_user")
                        db.add(user)
                        await db.flush()
                    
                    profile_image = existing_images_mapping.get(prot.get("profile_image")) if prot.get("profile_image") else None
                    
                    new_avatar = Avatar(
                        user_id=user.id,
                        adventure_id=new_adv_id,
                        name=prot["name"],
                        role=prot.get("role"),
                        description=prot.get("description"),
                        profile_image=profile_image,
                        hp=prot.get("hp", 200),
                        stamina=prot.get("stamina", 200),
                        mana=prot.get("mana", 200),
                        inventory=prot.get("inventory", []),
                        equipment=prot.get("equipment", {}),
                        stats=prot.get("stats", {}),
                    )
                    db.add(new_avatar)
                    await db.flush()

                    db.add(GameState(
                        id=new_adv_id,
                        user_id=user.id,
                        adventure_id=new_adv_id,
                        avatar_id=new_avatar.id,
                        scene_id="START",
                        in_game_time=0
                    ))

                # Reconstruct world using apply_manifest
                world_manifest = {
                    "protagonist": {
                        "name": prot["name"] if prot else "You",
                        "role": prot.get("role") if prot else "Adventurer",
                        "description": prot.get("description") if prot else "",
                        "starting_inventory": [],
                        "starting_equipment": {}
                    },
                    "scenes": manifest_data.get("scenes", []),
                    "exits": manifest_data.get("exits", []),
                    "npcs": manifest_data.get("npcs", []),
                    "objects": manifest_data.get("objects", []),
                    "quests": manifest_data.get("quests", [])
                }

                # Resolve start scenes if missing (fallback)
                default_scene_id = manifest_data["scenes"][0]["id"] if manifest_data.get("scenes") else "START"
                for n in world_manifest["npcs"]:
                    if "start_scene_id" not in n and "current_scene_id" in n:
                        n["start_scene_id"] = n["current_scene_id"]
                    if "start_scene_id" not in n:
                        n["start_scene_id"] = default_scene_id

                for o in world_manifest["objects"]:
                    if "start_scene_id" not in o and "current_scene_id" in o:
                        o["start_scene_id"] = o["current_scene_id"]
                    if "start_scene_id" not in o:
                        o["start_scene_id"] = default_scene_id
                
                image_urls = {}
                if prot and prot.get("profile_image") in existing_images_mapping:
                    image_urls["PROTAGONIST"] = existing_images_mapping[prot["profile_image"]]
                
                for s in manifest_data.get("scenes", []):
                    if s.get("image_url") in existing_images_mapping:
                        image_urls[s["id"]] = existing_images_mapping[s["image_url"]]
                
                for n in manifest_data.get("npcs", []):
                    if n.get("image_url") in existing_images_mapping:
                        image_urls[n["id"]] = existing_images_mapping[n["image_url"]]

                for o in manifest_data.get("objects", []):
                    if o.get("image_url") in existing_images_mapping:
                        image_urls[o["id"]] = existing_images_mapping[o["image_url"]]

                await WorldGenerator.apply_manifest(
                    db=db,
                    adventure_id=new_adv_id,
                    manifest_dict=world_manifest,
                    user=None,
                    existing_images=image_urls
                )
                
                if adv_data.get("image_url") in existing_images_mapping:
                    new_adv.image_url = existing_images_mapping[adv_data["image_url"]]

                await db.commit()
                return True
        except Exception as e:
            logger.exception(f"ADZ Import failed for {file_path}")
            await db.rollback()
            return False

    @staticmethod
    async def _import_adv(db: AsyncSession, file_path: str) -> bool:
        """Logic for pure .adv (JSON) import."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            
            # Check if this is a session bundle or a raw manifest
            # For auto-import, we mostly expect raw manifests or session exports
            is_session = payload.get("type") == "SESSION_BUNDLE"
            
            # Use title as unique check
            title = payload.get("adventure", {}).get("title") if is_session else payload.get("title", "Imported Adventure")
            
            existing_res = await db.execute(select(Adventure).where(Adventure.title == title))
            if existing_res.scalars().first():
                logger.info(f"Adventure '{title}' already exists. Skipping.")
                return False

            res = await db.execute(select(User).limit(1))
            user = res.scalars().first()
            if not user:
                user = User(username="local_default_user")
                db.add(user)
                await db.flush()

            if is_session:
                # Replicate Session Bundle logic from adventures.py
                data = payload
                old_adv = data["adventure"]
                
                new_adv = Adventure(
                    title=old_adv['title'],
                    context=old_adv.get("context"),
                    image_url=old_adv.get("image_url"),
                    strict_rules=old_adv.get("strict_rules", True),
                    time_per_turn=old_adv.get("time_per_turn", 10),
                    game_over_rules=old_adv.get("game_over_rules"),
                    original_manifest=old_adv.get("original_manifest"),
                    is_ready=True,
                    creation_status="Ready"
                )
                db.add(new_adv)
                await db.flush()
                
                for s in data.get("scenes", []):
                    db.add(WorldScene(
                        id=s["id"], 
                        adventure_id=new_adv.id, 
                        label=s["label"], 
                        description=s["description"],
                        image_url=s.get("image_url")
                    ))
                    
                for ent in data.get("entities", []):
                    db.add(WorldEntity(
                        id=ent["id"], 
                        adventure_id=new_adv.id, 
                        entity_type=ent["entity_type"],
                        name=ent["name"], 
                        description=ent["description"],
                        current_scene_id=ent["current_scene_id"], 
                        spatial_position=ent.get("spatial_position"),
                        image_url=ent.get("image_url"),
                        hp=ent.get("hp"),
                        mana=ent.get("mana"),
                        stamina=ent.get("stamina"),
                        item_type=ent.get("item_type"),
                        wearable_slots=ent.get("wearable_slots"),
                        is_hidden=ent.get("is_hidden", False),
                        is_in_inventory=ent.get("is_in_inventory", False),
                        is_portable=ent.get("is_portable", True),
                        npc_type=ent.get("npc_type"),
                        movement_type=ent.get("movement_type"),
                        inventory=ent.get("inventory", []), 
                        stats=ent.get("stats", {})
                    ))
                    
                for ex in data.get("exits", []):
                    db.add(WorldExit(
                        adventure_id=new_adv.id, from_scene_id=ex["from_scene_id"], to_scene_id=ex["to_scene_id"],
                        label=ex["label"], is_locked=ex.get("is_locked", False), lock_description=ex.get("lock_description")
                    ))
                    
                old_state = data.get("game_state")
                old_avatar = data.get("avatar")
                if old_state and old_avatar:
                    new_avatar = Avatar(
                        user_id=user.id, 
                        adventure_id=new_adv.id, 
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
                        status_effects=old_avatar["status_effects"]
                    )
                    db.add(new_avatar)
                    await db.flush()
                    
                    db.add(GameState(
                        id=new_adv.id, user_id=user.id, adventure_id=new_adv.id,
                        avatar_id=new_avatar.id, scene_id=old_state["scene_id"],
                        in_game_time=old_state.get("in_game_time", 0)
                    ))
                
                await db.commit()
                return True
            else:
                # Pure Manifest Import (handles raw blueprints or session exports)
                manifest = payload.get("original_manifest") or payload.get("manifest") or payload
                adv_meta = payload.get("adventure") or payload
                
                new_adv = Adventure(
                    title=adv_meta.get("title") or manifest.get("title") or "Imported Blueprint",
                    context=adv_meta.get("context") or manifest.get("description") or "Restored from blueprint.",
                    image_url=adv_meta.get("image_url") or manifest.get("image_url"),
                    original_manifest=manifest,
                    is_ready=True,
                    creation_status="Ready"
                )
                db.add(new_adv)
                await db.flush()
                
                # Identify the starting scene (default to the first scene defined)
                start_scene_id = "START"
                if manifest.get("scenes"):
                    start_scene_id = manifest["scenes"][0]["id"]

                # Extract protagonist info for the initial avatar
                prot = manifest.get("protagonist", {})
                avatar = Avatar(
                    user_id=user.id, 
                    adventure_id=new_adv.id, 
                    name=prot.get("name", "Hero"),
                    role=prot.get("role"),
                    description=prot.get("description"),
                    profile_image=prot.get("profile_image"),
                    hp=prot.get("hp", 200), 
                    stamina=prot.get("stamina", 200), 
                    mana=prot.get("mana", 200), 
                    stats=prot.get("stats", {}), 
                    inventory=prot.get("inventory", []), 
                    equipment=prot.get("equipment", {})
                )
                db.add(avatar)
                await db.flush()

                db.add(GameState(
                    id=new_adv.id, 
                    user_id=user.id, 
                    adventure_id=new_adv.id,
                    avatar_id=avatar.id, 
                    scene_id=start_scene_id, 
                    in_game_time=0
                ))

                await WorldGenerator.apply_manifest(db, new_adv.id, manifest)
                await db.commit()
                return True
        except Exception as e:
            logger.exception(f"ADV Import failed for {file_path}")
            await db.rollback()
            return False
