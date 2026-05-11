import io
import json
import logging
import os
import zipfile
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

logger = logging.getLogger(__name__)

class AdventureExporter:
    @staticmethod
    async def build_full_manifest(db: AsyncSession, template_id: str) -> dict[str, Any]:
        """
        Gathers all database entities for an adventure and builds a single JSON manifest.
        This follows the standard TaleWeaver .adv format.
        """
        adv = await db.get(AdventureTemplate, template_id)
        if not adv:
            raise ValueError("Adventure not found")

        # 1. Fetch World State
        scene_res = await db.execute(select(WorldScene).where(WorldScene.template_id == template_id))
        scenes = scene_res.scalars().all()
        
        exit_res = await db.execute(select(WorldExit).where(WorldExit.template_id == template_id))
        exits = exit_res.scalars().all()
        
        entity_res = await db.execute(select(WorldEntity).where(WorldEntity.template_id == template_id))
        entities = entity_res.scalars().all()

        avatar_res = await db.execute(select(Avatar).where(Avatar.template_id == template_id))
        avatar = avatar_res.scalars().first()

        # 2. Serialize to Dictionary
        def to_dict(obj):
            if not obj: return None
            return {c.name: getattr(obj, c.name) for c in obj.__table__.columns if c.name != "template_id"}

        # Build standard manifest structure according to docs/specs/adventure_format.md
        manifest = {
            "format": "TaleWeaver",
            "version": "1.2",
            
            "adventure": {
                "title": adv.title,
                "teaser": adv.teaser,
                "version": adv.version,
                "language": adv.language,
                "original_prompt": adv.original_prompt,
                "image_url": adv.image_url,
                "rule_enforcement_mode": adv.rule_enforcement_mode,
                "time_per_turn": adv.time_per_turn,
                "pacing_minutes": adv.pacing_minutes,
                "clock_enabled": adv.clock_enabled,
                "selected_tone": adv.selected_tone,
                "selected_image_styles": adv.selected_image_styles,
                "generate_scene_images": adv.generate_scene_images,
                "generate_npc_images": adv.generate_npc_images,
                "generate_item_images": adv.generate_item_images,
                "min_scenes": adv.min_scenes,
                "max_scenes": adv.max_scenes,
                "award_generation_enabled": adv.award_generation_enabled,
                "min_awards": adv.min_awards,
                "max_awards": adv.max_awards,
                "plot": adv.plot,
                "rules": adv.rules,
                "intro_text": adv.intro_text,
                "walkthrough": adv.walkthrough,
                "completed_condition": adv.completed_condition,
                "gameover_condition": adv.gameover_condition,
                "tts_director_notes": adv.tts_director_notes,
                "original_prompt": adv.original_prompt,
                "starting_timestamp": adv.starting_timestamp,
                "is_adventure_generator": adv.is_adventure_generator,
            },

            
            "protagonist": {
                "name": avatar.name if avatar else "Hero",
                "role": avatar.role if avatar else "Protagonist",
                "description": avatar.description if avatar else "",
                "profile_image": avatar.profile_image if avatar else None,
                "hp": avatar.hp if avatar else 200,
                "max_hp": avatar.max_hp if avatar else 200,
                "stamina": avatar.stamina if avatar else 200,
                "max_stamina": avatar.max_stamina if avatar else 200,
                "mana": avatar.mana if avatar else 200,
                "max_mana": avatar.max_mana if avatar else 200,
                "stats": avatar.stats if avatar else {},
                "starting_inventory": avatar.inventory if avatar else [],
                "starting_equipment": avatar.equipment if avatar else {},
            },
            
            "scenes": [to_dict(s) for s in scenes],
            "exits": [to_dict(e) for e in exits],
            "npcs": [to_dict(ent) for ent in entities if ent.entity_type == "NPC"],
            "objects": [to_dict(ent) for ent in entities if ent.entity_type == "OBJECT"],
            "quests": adv.quests or [],
            "awards": adv.awards or [],
        }
        
        return manifest

    @staticmethod
    async def export_adz(db: AsyncSession, template_id: str) -> bytes:
        """
        Creates an ADZ (Adventure Zip) bundle containing the manifest and all local images.
        """
        manifest = await AdventureExporter.build_full_manifest(db, template_id)
        
        # Gather local assets
        adventure_dir = os.path.join(settings.DATA_DIR, "adventures", "library", template_id)
        if not os.path.exists(adventure_dir):
            # Legacy fallback for pre-migration adventures.
            adventure_dir = os.path.join(settings.DATA_DIR, "adventures", template_id)
        asset_mapping = {} # local_path -> zip_path
        
        # Update manifest to point to relative paths in the zip
        def localize_path(path):
            if not path or not path.startswith("/data/"): return path
            
            # Convert URL to local path relative to DATA_DIR
            # URL format is /data/path/to/file.ext
            rel_path = path.replace("/data/", "", 1).lstrip("/")
            local_full = os.path.join(settings.DATA_DIR, rel_path)
            
            if os.path.exists(local_full):
                fname = os.path.basename(local_full)
                zip_rel = f"assets/{fname}"
                asset_mapping[local_full] = zip_rel
                return zip_rel
            
            # Fallback: search in adventure_dir if not found directly 
            # (handles cases where path might be different but file exists there)
            fname = os.path.basename(path)
            for root, dirs, files in os.walk(adventure_dir):
                if fname in files:
                    local_full = os.path.join(root, fname)
                    zip_rel = f"assets/{fname}"
                    asset_mapping[local_full] = zip_rel
                    return zip_rel
            
            return path

        # Localize all image fields
        manifest["adventure"]["image_url"] = localize_path(manifest["adventure"]["image_url"])
        if manifest["protagonist"]:
            manifest["protagonist"]["profile_image"] = localize_path(manifest["protagonist"]["profile_image"])
        for s in manifest["scenes"]:
            s["image_url"] = localize_path(s["image_url"])
        for n in manifest["npcs"]:
            n["image_url"] = localize_path(n["image_url"])
        for o in manifest["objects"]:
            o["image_url"] = localize_path(o["image_url"])

        # Create the ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # 1. Add Manifest
            # Use jsonable_encoder to handle datetime and other non-serializable objects
            encoded_manifest = jsonable_encoder(manifest)
            zip_file.writestr("adventure.adv", json.dumps(encoded_manifest, indent=2))
            
            # 2. Add Assets
            for local_full, zip_rel in asset_mapping.items():
                if os.path.exists(local_full):
                    zip_file.write(local_full, zip_rel)
                    
        return zip_buffer.getvalue()

