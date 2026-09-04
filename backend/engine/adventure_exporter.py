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
from backend.utils.path_security import data_url_to_local_path

logger = logging.getLogger(__name__)

_ENTITY_BASE_KEYS = {
    "id",
    "entity_type",
    "name",
    "description",
    "current_scene_id",
    "spatial_position",
    "image_url",
}

_OBJECT_ENTITY_KEYS = {
    "item_type",
    "wearable_slots",
    "is_in_inventory",
    "is_hidden",
    "reveal_rule",
    "unlock_rule",
    "is_portable",
    "combination_ingredients",
    "reveals_item_id",
    "is_final_state",
    "state_comment",
    "stat_modifier_strength",
    "stat_modifier_dexterity",
    "stat_modifier_intelligence",
    "stat_modifier_wisdom",
    "stat_modifier_charisma",
    "stat_modifier_armor_class",
    "inventory",
    "metadata_json",
    "hp_change",
    "stamina_change",
    "mana_change",
    "text_log_content",
    "text_log_format",
    "code_to_unlock",
    "item_to_unlock",
    "rule_to_unlock",
    "switch_states",
    "switch_initial_state",
    "switch_transitions",
    "switch_outcomes",
}

_NPC_ENTITY_KEYS = {
    "is_hidden",
    "reveal_rule",
    "npc_type",
    "movement_type",
    "goal",
    "character",
    "hp",
    "max_hp",
    "mana",
    "max_mana",
    "stamina",
    "max_stamina",
    "voice",
    "is_attackable",
    "is_killable",
    "inventory",
    "metadata_json",
}

_SYSTEM_ENTITY_KEYS = {"pk", "session_id", "created_at", "updated_at", "template_id"}

_STAT_MODIFIER_KEYS = {
    "stat_modifier_strength",
    "stat_modifier_dexterity",
    "stat_modifier_intelligence",
    "stat_modifier_wisdom",
    "stat_modifier_charisma",
    "stat_modifier_armor_class",
}


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


def _safe_zip_asset_name(path: str) -> str:
    """Return a flattened safe asset name for zip entries."""
    base = os.path.basename(path or "")
    return base or "asset"


def _prune_none(value: Any) -> Any:
    """Recursively drop None values while preserving falsy values like 0 and False."""
    if isinstance(value, dict):
        return {k: _prune_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_prune_none(v) for v in value if v is not None]
    return value


def _serialize_world_entity(entity: WorldEntity) -> dict[str, Any]:
    """Serialize a world entity with type-specific keys and no None values."""
    raw = {
        c.name: getattr(entity, c.name)
        for c in entity.__table__.columns
        if c.name not in _SYSTEM_ENTITY_KEYS
    }

    entity_type = str(raw.get("entity_type") or "").upper()
    if entity_type == "OBJECT":
        allowed_keys = _ENTITY_BASE_KEYS | _OBJECT_ENTITY_KEYS
    elif entity_type == "NPC":
        allowed_keys = _ENTITY_BASE_KEYS | _NPC_ENTITY_KEYS
    else:
        allowed_keys = set(raw.keys())

    filtered = {
        key: _prune_none(value)
        for key, value in raw.items()
        if key in allowed_keys and value is not None
    }

    # Keep stat modifiers canonical at top level for objects to avoid duplicated ADV fields.
    if entity_type == "OBJECT" and isinstance(filtered.get("metadata_json"), dict):
        metadata = dict(filtered["metadata_json"])
        for stat_key in _STAT_MODIFIER_KEYS:
            if stat_key in metadata and metadata.get(stat_key) == filtered.get(stat_key):
                metadata.pop(stat_key, None)

        item_type = str(filtered.get("item_type") or "").upper()

        # 1. Consumption fields
        hp_change = metadata.pop("hp_change", None)
        stamina_change = metadata.pop("stamina_change", None)
        mana_change = metadata.pop("mana_change", None)
        filtered["hp_change"] = hp_change if hp_change is not None else 0
        filtered["stamina_change"] = stamina_change if stamina_change is not None else 0
        filtered["mana_change"] = mana_change if mana_change is not None else 0

        # 2. Readable fields
        if item_type == "READABLE":
            filtered["text_log_content"] = metadata.pop("text_log_content", "")
            filtered["text_log_format"] = metadata.pop("text_log_format", "DOCUMENT")
        else:
            metadata.pop("text_log_content", None)
            metadata.pop("text_log_format", None)

        # 3. Container lock fields
        if item_type == "CONTAINER":
            filtered["code_to_unlock"] = metadata.pop("code_to_unlock", "")
            filtered["item_to_unlock"] = metadata.pop("item_to_unlock", "")
            filtered["rule_to_unlock"] = metadata.pop("rule_to_unlock", "")
            metadata.pop("locked", None)
        else:
            metadata.pop("code_to_unlock", None)
            metadata.pop("item_to_unlock", None)
            metadata.pop("rule_to_unlock", None)
            metadata.pop("locked", None)

        # 4. Switch fields
        if item_type == "SWITCH":
            switch_config = metadata.pop("switch", {})
            if not isinstance(switch_config, dict):
                switch_config = {}
            filtered["switch_states"] = switch_config.get("states") or metadata.pop("switch_states", []) or []
            filtered["switch_initial_state"] = switch_config.get("initial_state") or metadata.pop("switch_initial_state", "") or ""
            filtered["switch_transitions"] = switch_config.get("transitions") or metadata.pop("switch_transitions", []) or []
            filtered["switch_outcomes"] = switch_config.get("outcomes") or []
        else:
            metadata.pop("switch", None)
            metadata.pop("switch_states", None)
            metadata.pop("switch_initial_state", None)
            metadata.pop("switch_transitions", None)

        # Clean up flat consumable effects
        metadata.pop("effects", None)

        if metadata:
            filtered["metadata_json"] = metadata
        else:
            filtered.pop("metadata_json", None)

    return filtered

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

        avatar_res = await db.execute(
            select(Avatar)
            .where(Avatar.template_id == template_id)
            .order_by(Avatar.created_at.asc(), Avatar.id.asc())
            .limit(1)
        )
        avatar = avatar_res.scalars().first()

        # Normalize legacy avatar inventory/equipment to ID references for the manifest.
        # NOTE: This must NOT mutate the database — exporting is a read-only operation.
        # Mutating during export causes "database is locked" errors on SQLite when
        # background tasks (e.g. world generation) hold a write lock. We compute
        # the cleaned values locally and use them when building the manifest below.
        local_final_inventory: list[str] = []
        local_final_equipment: dict[str, str] = {}
        if avatar:
            def _normalize_item(item: Any) -> str | None:
                if isinstance(item, dict):
                    return item.get("id")
                return item

            cleaned_inventory: list[str] = []
            for item in (avatar.inventory or []):
                item_id = _normalize_item(item)
                if item_id:
                    cleaned_inventory.append(item_id)

            cleaned_equipment: dict[str, str] = {}
            for slot, item in (avatar.equipment or {}).items():
                item_id = _normalize_item(item)
                if item_id:
                    cleaned_equipment[slot] = item_id

            # Priority deduplication: Scene > Inventory > Equipped
            items_in_scene = set()
            for ent in entities:
                if (
                    ent.entity_type == "OBJECT"
                    and ent.current_scene_id
                    and ent.current_scene_id != "INVENTORY"
                ):
                    items_in_scene.add(ent.id)

            for item_id in cleaned_inventory:
                if item_id in items_in_scene:
                    continue
                if item_id not in local_final_inventory:
                    local_final_inventory.append(item_id)

            for slot, item_id in cleaned_equipment.items():
                if item_id in items_in_scene:
                    continue
                if item_id in local_final_inventory:
                    continue
                if item_id in local_final_equipment.values():
                    continue
                local_final_equipment[slot] = item_id

        # 2. Serialize to Dictionary
        def to_dict(obj):
            if not obj: return None
            data = {c.name: getattr(obj, c.name) for c in obj.__table__.columns if c.name not in _SYSTEM_ENTITY_KEYS}
            if isinstance(obj, WorldScene):
                decor = data.get("decorative_objects")
                if not isinstance(decor, list):
                    decor = []
                data["decorative_objects"] = [str(d) for d in decor if isinstance(d, (str, int, float))]
            if isinstance(obj, WorldExit):
                exit_type = str(getattr(obj, "exit_type", "one_way") or "one_way").strip().lower()
                data["exit_type"] = exit_type
                data["is_bidirectional"] = (exit_type == "bidirectional")
            return data

        # Build standard manifest structure according to docs/specs/adventure_format.md
        manifest = {
            "format": "TaleWeaver",
            "version": "1.2",
            
            "adventure": {
                "title": adv.title,
                "teaser": adv.teaser,
                "version": adv.version,
                "creator": adv.creator,
                "copyright": adv.copyright,
                "license": adv.license,
                "license_url": adv.license_url,
                "language": adv.language,
                "original_prompt": adv.original_prompt,

                "image_url": adv.image_url,
                "rule_enforcement_mode": adv.rule_enforcement_mode,
                "time_per_turn": adv.time_per_turn,
                "pacing_minutes": adv.pacing_minutes,
                "max_time_per_turn": adv.max_time_per_turn,
                "max_memory_turns": getattr(adv, "max_memory_turns", 10) or 10,
                "clock_enabled": adv.clock_enabled,
                "selected_tone": adv.selected_tone,
                "selected_image_styles": adv.selected_image_styles,
                "generate_scene_images": adv.generate_scene_images,
                "generate_npc_images": adv.generate_npc_images,
                "generate_item_images": adv.generate_item_images,
                "min_scenes": adv.min_scenes,
                "max_scenes": adv.max_scenes,
                "min_items": adv.min_items,
                "max_items": adv.max_items,
                "container_generation_enabled": adv.container_generation_enabled,
                "min_containers": adv.min_containers,
                "max_containers": adv.max_containers,
                "text_log_generation_enabled": adv.text_log_generation_enabled,
                "min_text_logs": adv.min_text_logs,
                "max_text_logs": adv.max_text_logs,
                "quest_generation_enabled": adv.quest_generation_enabled,
                "min_quests": adv.min_quests,
                "max_quests": adv.max_quests,
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
                "starting_timestamp": adv.starting_timestamp,
                "is_adventure_generator": adv.is_adventure_generator,
                "time_system": adv.time_system,
                "time_config": adv.time_config,
                "game_over_rules": adv.game_over_rules,
                "allow_dynamic_items": adv.allow_dynamic_items,
                "can_damage_npcs": adv.can_damage_npcs,
                "npcs_can_damage_protagonist": adv.npcs_can_damage_protagonist,
                "cover_source_adventure_id": adv.cover_source_adventure_id,
                "cover_source_adventure_name": adv.cover_source_adventure_name,
                "cover_similarity_percent": adv.cover_similarity_percent,
                "allow_reuse_source_assets": adv.allow_reuse_source_assets,
            },

            
            "protagonist": {
                "name": avatar.name if avatar else "Hero",
                "role": avatar.role if avatar else "Protagonist",
                "description": avatar.description if avatar else "",
                "goal": avatar.goal if avatar else "",
                "character": avatar.character if avatar else "",
                "profile_image": avatar.profile_image if avatar else None,
                "hp": avatar.hp if avatar else 200,
                "max_hp": avatar.max_hp if avatar else 200,
                "stamina": avatar.stamina if avatar else 200,
                "max_stamina": avatar.max_stamina if avatar else 200,
                "mana": avatar.mana if avatar else 200,
                "max_mana": avatar.max_mana if avatar else 200,
                "exp": avatar.exp if avatar else 0,
                "strength": avatar.strength if avatar else 10,
                "dexterity": avatar.dexterity if avatar else 10,
                "intelligence": avatar.intelligence if avatar else 10,
                "wisdom": avatar.wisdom if avatar else 10,
                "charisma": avatar.charisma if avatar else 10,
                "armor_class": avatar.armor_class if avatar else 10,
                "stats": avatar.stats if avatar else {},
                "status_effects": avatar.status_effects if avatar else [],
                "starting_inventory": list(local_final_inventory) if avatar else [],
                "starting_equipment": dict(local_final_equipment) if avatar else {},
            },
            
            "scenes": [to_dict(s) for s in scenes],
            "exits": [to_dict(e) for e in exits],
            "npcs": [_serialize_world_entity(ent) for ent in entities if ent.entity_type == "NPC"],
            "objects": [_serialize_world_entity(ent) for ent in entities if ent.entity_type == "OBJECT"],
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
        adventure_dir = _safe_data_path("adventures", "library", template_id)
        if not os.path.exists(adventure_dir):
            # Legacy fallback for pre-migration adventures.
            adventure_dir = _safe_data_path("adventures", template_id)
        asset_mapping = {} # local_path -> zip_path
        
        # Update manifest to point to relative paths in the zip
        def localize_path(path):
            if not path or not path.startswith("/data/"): return path

            local_full = data_url_to_local_path(path)
            if not local_full:
                logger.warning("Skipping unsafe asset path during ADZ export: %s", path)
                return path
            
            if os.path.exists(local_full):
                fname = _safe_zip_asset_name(local_full)
                zip_rel = f"assets/{fname}"
                asset_mapping[local_full] = zip_rel
                return zip_rel
            
            # Fallback: search in adventure_dir if not found directly 
            # (handles cases where path might be different but file exists there)
            fname = _safe_zip_asset_name(path)
            for root, _dirs, files in os.walk(adventure_dir):
                if fname in files:
                    local_full = _ensure_within_data_dir(os.path.join(root, fname))
                    zip_rel = f"assets/{fname}"
                    asset_mapping[local_full] = zip_rel
                    return zip_rel
            
            return path

        # Localize all image fields
        manifest["adventure"]["image_url"] = localize_path(manifest["adventure"].get("image_url"))
        if manifest["protagonist"]:
            manifest["protagonist"]["profile_image"] = localize_path(manifest["protagonist"].get("profile_image"))
        for s in manifest["scenes"]:
            s["image_url"] = localize_path(s.get("image_url"))
        for n in manifest["npcs"]:
            n["image_url"] = localize_path(n.get("image_url"))
        for o in manifest["objects"]:
            o["image_url"] = localize_path(o.get("image_url"))

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
                    safe_local_full = _ensure_within_data_dir(local_full)
                    zip_file.write(safe_local_full, zip_rel)
                    
        return zip_buffer.getvalue()

