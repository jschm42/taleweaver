"""
Manifest applier for the world generation pipeline.

Takes a validated manifest dictionary and persists all world entities (scenes,
exits, NPCs, objects, protagonist/avatar) to the database, optionally generating
images for each entity along the way.
"""
import asyncio
import logging
import os
import re
import shutil
from collections.abc import Awaitable, Callable
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import prompts
from backend.core.config import settings
from backend.core.style_catalog import resolve_style_instruction
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from backend.utils.path_security import (
    data_url_to_local_path,
    ensure_within_base_dir,
    ensure_within_data_dir,
    local_path_to_data_url,
    sanitize_relative_segment,
)
from backend.utils.text_utils import slugify

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_base_slug(entity_id: str) -> str:
    return re.sub(r"(_COPY)?(_\d+)?$", "", entity_id, flags=re.IGNORECASE)


def _public_data_url_to_local_path(url: Optional[str]) -> Optional[str]:
    return data_url_to_local_path(url)


def _local_path_to_public_data_url(local_path: str) -> Optional[str]:
    try:
        return local_path_to_data_url(local_path)
    except ValueError:
        return None


def _is_usable_image_url(url: Optional[str]) -> bool:
    value = str(url or "").strip()
    if not value:
        return False
    if not value.startswith("/data/"):
        return True
    local_path = _public_data_url_to_local_path(value)
    if not local_path:
        return False
    try:
        safe_local_path = ensure_within_data_dir(local_path)
    except ValueError:
        return False
    return os.path.isfile(safe_local_path)


def _copy_source_asset_to_current_adventure(
    source_url: Optional[str],
    *,
    template_id: str,
    entity_type: str,
    source_asset_id: Optional[str],
) -> Optional[str]:
    source_local = _public_data_url_to_local_path(source_url)
    if not source_local:
        return None
    try:
        safe_source_local = ensure_within_data_dir(source_local)
    except ValueError:
        return None
    if not os.path.isfile(safe_source_local):
        return None

    target_root = ensure_within_data_dir(
        os.path.join(settings.DATA_DIR, "adventures", "library", str(template_id))
    )
    try:
        if os.path.commonpath([safe_source_local, target_root]) == target_root:
            return source_url
    except ValueError:
        return None

    safe_prefix = slugify(str(source_asset_id or entity_type)) or "source"
    source_basename = os.path.basename(safe_source_local)
    safe_source_basename = sanitize_relative_segment(source_basename)
    if not safe_source_basename:
        return None
    if not re.match(r"^[A-Za-z0-9._-]+$", safe_source_basename):
        return None
    if not re.match(r"^[A-Za-z0-9_-]+$", safe_prefix):
        return None

    try:
        target_dir = ensure_within_data_dir(
            os.path.join(target_root, "visuals", "reused", str(entity_type))
        )
    except ValueError:
        return None

    safe_target_dir = ensure_within_data_dir(target_dir)
    os.makedirs(safe_target_dir, exist_ok=True)

    try:
        target_local = ensure_within_data_dir(
            os.path.join(safe_target_dir, f"{safe_prefix}_{safe_source_basename}")
        )
    except ValueError:
        return None

    try:
        target_local = ensure_within_base_dir(target_local, safe_target_dir)
    except ValueError:
        return None

    target_root_real = os.path.realpath(safe_target_dir)
    if os.path.commonpath([os.path.realpath(target_local), target_root_real]) != target_root_real:
        return None

    if not os.path.isfile(target_local):
        try:
            shutil.copy2(safe_source_local, target_local)
        except Exception as exc:
            logger.warning(
                "Failed to localize reused source asset for %s/%s from %s: %s",
                template_id,
                entity_type,
                source_url,
                exc,
            )
            return None

    return _local_path_to_public_data_url(target_local)


def _resolve_source_asset_image(
    source_assets: Optional[dict[str, Any]],
    template_id: str,
    entity_type: str,
    source_asset_id: Optional[str] = None,
) -> Optional[str]:
    """Return the localized URL for a reused source asset, or None."""
    if not source_assets or not source_asset_id:
        return None

    if entity_type == "cover":
        return _copy_source_asset_to_current_adventure(
            source_assets.get("cover"),
            template_id=template_id,
            entity_type=entity_type,
            source_asset_id=source_asset_id,
        )

    if entity_type == "protagonist":
        protagonist_asset = source_assets.get("protagonist") or {}
        if source_asset_id == "PROTAGONIST" and protagonist_asset.get("image_url"):
            return _copy_source_asset_to_current_adventure(
                protagonist_asset.get("image_url"),
                template_id=template_id,
                entity_type=entity_type,
                source_asset_id=source_asset_id,
            )
        return None

    bucket_key = {"scene": "scenes", "npc": "npcs", "object": "objects"}.get(entity_type)
    if not bucket_key:
        return None
    bucket = source_assets.get(bucket_key) or []
    if not isinstance(bucket, list):
        return None
    for asset in bucket:
        if asset.get("id") == source_asset_id and asset.get("image_url"):
            return _copy_source_asset_to_current_adventure(
                asset.get("image_url"),
                template_id=template_id,
                entity_type=entity_type,
                source_asset_id=source_asset_id,
            )
    return None


def _inventory_item_id(entry: Any) -> Optional[str]:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        for key in ("id", "item_id", "object_id"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return None


def _extract_numeric_stat(obj: dict[str, Any], source_item: dict[str, Any], *keys: str) -> Optional[int]:
    for key in keys:
        value = obj.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    for key in keys:
        value = source_item.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    metadata = obj.get("metadata_json") if isinstance(obj.get("metadata_json"), dict) else {}
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    stat_modifiers = metadata.get("stat_modifiers") if isinstance(metadata.get("stat_modifiers"), dict) else {}
    for key in keys:
        value = stat_modifiers.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    return None


def _extract_numeric_effect(obj: dict[str, Any], source_item: dict[str, Any], *keys: str) -> Optional[int]:
    for key in keys:
        value = obj.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    for key in keys:
        value = source_item.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    metadata = obj.get("metadata_json") if isinstance(obj.get("metadata_json"), dict) else {}
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    effects = metadata.get("effects") if isinstance(metadata.get("effects"), dict) else {}
    for key in keys:
        value = effects.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    source_effects = source_item.get("effects") if isinstance(source_item.get("effects"), dict) else {}
    for key in keys:
        value = source_effects.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    return None


def _find_duplicate_image_url(
    entity: dict[str, Any],
    processed: list[dict],
    image_cache: dict[str, str],
) -> Optional[str]:
    """Return a cached image URL if the entity is considered a visual duplicate of a previously processed entity."""
    for prev in processed:
        if _get_base_slug(prev["id"]) == _get_base_slug(entity["id"]):
            return image_cache.get(prev["id"])
        if (
            prev["name"].lower().strip(),
            prev["description"].lower().strip(),
        ) == (entity["name"].lower().strip(), entity["description"].lower().strip()):
            return image_cache.get(prev["id"])
        if entity.get("source_asset_id") and prev.get("source_asset_id") == entity.get("source_asset_id"):
            return image_cache.get(prev["id"])
    return None


# ---------------------------------------------------------------------------
# Imports re-used from world_generator (avoid circular by deferring)
# ---------------------------------------------------------------------------

def _get_generation_helpers():
    """Lazily import helpers from world_generator to avoid circular imports."""
    from backend.engine.world_generator import (  # noqa: PLC0415
        _image_generation_timeout_seconds,
        _log_image_generation,
        _log_reused_asset,
        _normalize_text_log_content,
        _normalize_unlock_requirements,
        _publish_generation_status_with_callback,
        is_image_moderation_error,
    )
    return (
        _image_generation_timeout_seconds,
        _log_image_generation,
        _log_reused_asset,
        _normalize_text_log_content,
        _normalize_unlock_requirements,
        _publish_generation_status_with_callback,
        is_image_moderation_error,
    )


# ---------------------------------------------------------------------------
# Persist helpers
# ---------------------------------------------------------------------------

async def _persist_avatar(
    db: AsyncSession,
    adventure: AdventureTemplate,
    template_id: str,
    prot: dict[str, Any],
    manifest_dict: dict[str, Any],
    user: Optional[User],
    gen_protagonist_image: bool,
    existing_images: dict[str, str],
    source_assets: Optional[dict[str, Any]],
    style_instruction: str,
    status_callback: Optional[Callable[[str], Awaitable[None]]],
    image_counters: dict[str, int],
) -> Any:
    """Sync protagonist data to Avatar model, generate portrait if required.

    Returns the avatar ORM object.
    """
    from backend.engine.media_engine import MediaEngine  # noqa: PLC0415
    from backend.models.avatar import Avatar  # noqa: PLC0415

    (
        _image_generation_timeout_seconds,
        _log_image_generation,
        _log_reused_asset,
        _normalize_text_log_content,
        _normalize_unlock_requirements,
        _publish_generation_status_with_callback,
        is_image_moderation_error,
    ) = _get_generation_helpers()

    av_res = await db.execute(
        select(Avatar)
        .where(Avatar.template_id == template_id)
        .order_by(Avatar.created_at.asc(), Avatar.id.asc())
        .limit(1)
    )
    avatar = av_res.scalars().first()

    # Map starting equipment slot -> item_id
    raw_equip = prot.get("starting_equipment") or {}
    starting_equipped_ids: dict[str, str] = {}
    protagonist_item_defs: dict[str, dict[str, Any]] = {}
    for slot, val in raw_equip.items():
        item_id = val.get("id") if isinstance(val, dict) else val
        if item_id:
            starting_equipped_ids[item_id] = slot
            if isinstance(val, dict):
                protagonist_item_defs[item_id] = val

    raw_inv = prot.get("starting_inventory") or []
    starting_inv_ids: set[str] = set()
    for item in raw_inv:
        item_id = item.get("id") if isinstance(item, dict) else item
        if item_id:
            starting_inv_ids.add(item_id)
            if isinstance(item, dict):
                protagonist_item_defs[item_id] = item

    if not avatar:
        avatar = Avatar(
            template_id=template_id,
            user_id=adventure.owner_id,
            name=prot.get("name", "Hero"),
            role=prot.get("role", "Protagonist"),
            description=prot.get("description", ""),
            goal=prot.get("goal", ""),
            character=prot.get("character", ""),
            hp=prot.get("hp", 200),
            max_hp=prot.get("hp", 200),
            stamina=prot.get("stamina", 200),
            max_stamina=prot.get("stamina", 200),
            mana=prot.get("mana", 200),
            max_mana=prot.get("mana", 200),
            strength=prot.get("strength", 10),
            dexterity=prot.get("dexterity", 10),
            intelligence=prot.get("intelligence", 10),
            wisdom=prot.get("wisdom", 10),
            charisma=prot.get("charisma", 10),
            armor_class=prot.get("armor_class", 10),
            exp=prot.get("exp", 0),
            status_effects=prot.get("status_effects", []),
            stats=prot.get("stats", {}),
            inventory=[],
            equipment={
                "Head": None, "Chest": None, "Arms": None, "Legs": None,
                "Hands": None, "Feet": None, "Ring_1": None, "Ring_2": None,
                "Neck": None, "MainHand": None, "OffHand": None,
            },
        )
        db.add(avatar)
    else:
        avatar.name = prot.get("name", avatar.name)
        avatar.role = prot.get("role", avatar.role)
        avatar.description = prot.get("description", avatar.description)
        avatar.goal = prot.get("goal", avatar.goal)
        avatar.character = prot.get("character", avatar.character)
        avatar.hp = prot.get("hp", avatar.hp)
        avatar.max_hp = prot.get("hp", avatar.max_hp)
        avatar.stamina = prot.get("stamina", avatar.stamina)
        avatar.max_stamina = prot.get("stamina", avatar.max_stamina)
        avatar.mana = prot.get("mana", avatar.mana)
        avatar.max_mana = prot.get("mana", avatar.max_mana)
        avatar.strength = prot.get("strength", avatar.strength)
        avatar.dexterity = prot.get("dexterity", avatar.dexterity)
        avatar.intelligence = prot.get("intelligence", avatar.intelligence)
        avatar.wisdom = prot.get("wisdom", avatar.wisdom)
        avatar.charisma = prot.get("charisma", avatar.charisma)
        avatar.armor_class = prot.get("armor_class", avatar.armor_class)
        avatar.exp = prot.get("exp", avatar.exp)
        avatar.status_effects = prot.get("status_effects") or avatar.status_effects
        avatar.stats = prot.get("stats") or avatar.stats
        avatar.inventory = []  # type: ignore[assignment]
        avatar.equipment = {  # type: ignore[assignment]
            "head": None, "neck": None, "chest": None, "back": None,
            "arms": None, "hands": None, "waist": None, "legs": None, "feet": None,
            "main_hand": None, "off_hand": None, "ring_1": None, "ring_2": None,
        }

    # Portrait
    reused_protagonist_url = _resolve_source_asset_image(source_assets, template_id, "protagonist", prot.get("source_asset_id"))
    image_url = (
        existing_images.get("PROTAGONIST")
        or reused_protagonist_url
        or prot.get("profile_image")
    )
    if not _is_usable_image_url(image_url):
        image_url = None
    if image_url and image_url == reused_protagonist_url:
        await _log_reused_asset(db, adventure, f"Protagonist ({avatar.name})", image_url)

    if not image_url or image_url.startswith("assets/"):
        if user and gen_protagonist_image:
            await _publish_generation_status_with_callback(
                db, adventure,
                f"Envisioning Portrait for {avatar.name}...",
                status_callback=status_callback,
            )
            prompt = prompts.PROTAGONIST_IMAGE_PROMPT_TEMPLATE.format(
                name=avatar.name, role=avatar.role, description=avatar.description
            )
            generated_plot = (manifest_dict.get("plot") or "").strip()
            if generated_plot:
                prompt = f"{prompt} Narrative context: {generated_plot[:1200]}"
            image_counters["attempts"] += 1
            try:
                image_url = await asyncio.wait_for(
                    MediaEngine.generate_entity_image(
                        prompt, template_id, "PROTAGONIST", "NPC",
                        {"t2i_settings": user.t2i_settings},
                        dict(user.encrypted_api_keys or {}),  # type: ignore[arg-type]
                        style_instruction=style_instruction,
                        use_advanced_model=((user.t2i_settings or {}).get("protagonist_model_quality", "advanced") == "advanced"),
                    ),
                    timeout=float(settings.VISUAL_TIMEOUT),
                )
            except asyncio.TimeoutError:
                logger.warning("Protagonist image generation timed out after %ss for %s", settings.VISUAL_TIMEOUT, template_id)
                image_url = None
            except Exception as exc:
                if is_image_moderation_error(exc):
                    image_counters["moderation"] += 1
                logger.warning("Protagonist image generation failed for %s: %s", template_id, exc)
                image_url = None
            if image_url:
                image_counters["successes"] += 1
                await _log_image_generation(db, adventure, prompt, image_url)

        if not image_url or image_url.startswith("assets/"):
            if not avatar.profile_image or not avatar.profile_image.startswith("/data/"):
                image_url = await MediaEngine.generate_placeholder(
                    template_id, "PROTAGONIST",
                    os.path.join(settings.DATA_DIR, "adventures", "library", template_id),
                    category="SCENE",
                )
            else:
                image_url = avatar.profile_image

    avatar.profile_image = image_url
    return avatar, starting_equipped_ids, starting_inv_ids, protagonist_item_defs


async def _persist_scenes(
    db: AsyncSession,
    adventure: AdventureTemplate,
    template_id: str,
    scenes: list[dict[str, Any]],
    existing_images: dict[str, str],
    source_assets: Optional[dict[str, Any]],
    user: Optional[User],
    gen_scenes: bool,
    style_instruction: str,
    status_callback: Optional[Callable[[str], Awaitable[None]]],
    image_counters: dict[str, int],
    seen_scene_ids: set[str],
) -> None:
    from backend.engine.media_engine import MediaEngine  # noqa: PLC0415

    (
        _image_generation_timeout_seconds,
        _log_image_generation,
        _log_reused_asset,
        _,
        _normalize_unlock_requirements,
        _publish_generation_status_with_callback,
        is_image_moderation_error,
    ) = _get_generation_helpers()

    total = len(scenes)
    for idx, s in enumerate(scenes, start=1):
        if s["id"] in seen_scene_ids:
            continue
        seen_scene_ids.add(s["id"])

        reused_url = _resolve_source_asset_image(source_assets, template_id, "scene", s.get("source_asset_id"))
        image_url = existing_images.get(s["id"]) or reused_url or s.get("image_url")
        if not _is_usable_image_url(image_url):
            image_url = None
        if image_url and image_url == reused_url:
            await _log_reused_asset(db, adventure, f"Scene: {s.get('name')}", image_url)

        if not image_url or image_url.startswith("assets/"):
            if user and gen_scenes:
                await _publish_generation_status_with_callback(
                    db, adventure,
                    f"Envisioning Scene {idx}/{total}: {s['name']}...",
                    status_callback=status_callback,
                )
                prompt = prompts.SCENE_IMAGE_PROMPT_TEMPLATE.format(
                    name=s["name"], description=s["description"]
                )
                image_counters["attempts"] += 1
                try:
                    image_url = await asyncio.wait_for(
                        MediaEngine.generate_scene_image(
                            prompt, template_id,
                            {"t2i_settings": user.t2i_settings},
                            dict(user.encrypted_api_keys or {}),  # type: ignore[arg-type]
                            style_instruction=style_instruction,
                        ),
                        timeout=_image_generation_timeout_seconds(),
                    )
                except asyncio.TimeoutError as exc:
                    logger.warning("Scene image generation timed out for %s/%s: %s", template_id, s["id"], exc)
                    image_url = None
                except Exception as exc:
                    if is_image_moderation_error(exc):
                        image_counters["moderation"] += 1
                    logger.warning("Scene image generation failed for %s/%s: %s", template_id, s["id"], exc)
                    image_url = None
                if image_url:
                    image_counters["successes"] += 1
                    await _log_image_generation(db, adventure, prompt, image_url)

            if not image_url or image_url.startswith("assets/"):
                image_url = await MediaEngine.generate_placeholder(
                    template_id, s["id"],
                    os.path.join(settings.DATA_DIR, "adventures", "library", template_id, "scenes"),
                    category="SCENE",
                )

        description = s.get("description") or ""
        decorative = s.get("decorative_objects") or []
        clean_decor: list[str] = []
        if isinstance(decorative, list):
            for d in decorative:
                if not isinstance(d, str):
                    continue
                stripped = d.strip()
                if stripped:
                    clean_decor.append(stripped[:100])
            clean_decor = clean_decor[:7]

        db.add(WorldScene(
            id=s["id"],
            template_id=template_id,
            label=s.get("name") or s.get("label") or "Unknown Scene",
            description=description,
            image_url=image_url,
            decorative_objects=clean_decor or None,
        ))


def _persist_exits(
    db: AsyncSession,
    template_id: str,
    exits: list[dict[str, Any]],
) -> None:
    from backend.engine.world_generator import _normalize_unlock_requirements  # noqa: PLC0415

    seen_directed: set[tuple[str, str]] = set()
    seen_bidirectional: set[tuple[str, str]] = set()

    for e in exits:
        from_id = e["from_scene_id"]
        to_id = e["to_scene_id"]
        is_bidirectional = bool(e.get("is_bidirectional", False))

        code_to_unlock, item_to_unlock, rule_to_unlock = _normalize_unlock_requirements(
            e.get("code_to_unlock"), e.get("item_to_unlock"), e.get("rule_to_unlock")
        )

        if is_bidirectional:
            pair_key = tuple(sorted((from_id, to_id)))
            if pair_key in seen_bidirectional:
                continue
            seen_bidirectional.add(pair_key)
        else:
            directed_key = (from_id, to_id)
            if directed_key in seen_directed:
                continue
            seen_directed.add(directed_key)

        db.add(WorldExit(
            template_id=template_id,
            from_scene_id=from_id,
            to_scene_id=to_id,
            label=e["label"],
            exit_type="bidirectional" if is_bidirectional else "one_way",
            is_locked=e["is_locked"],
            lock_description=e.get("lock_description"),
            code_to_unlock=code_to_unlock,
            item_to_unlock=item_to_unlock,
            rule_to_unlock=rule_to_unlock,
        ))


async def _persist_npcs(
    db: AsyncSession,
    adventure: AdventureTemplate,
    template_id: str,
    npcs: list[dict[str, Any]],
    default_scene_id: str,
    existing_images: dict[str, str],
    source_assets: Optional[dict[str, Any]],
    user: Optional[User],
    gen_npc: bool,
    style_instruction: str,
    status_callback: Optional[Callable[[str], Awaitable[None]]],
    image_counters: dict[str, int],
    seen_entity_ids: set[str],
) -> tuple[list[dict], dict[str, str], dict[str, list[str]]]:
    """Persist NPCs and generate portraits. Returns (processed_npcs, npc_image_cache, npc_inventories)."""
    from backend.engine.media_engine import MediaEngine  # noqa: PLC0415

    (
        _image_generation_timeout_seconds,
        _log_image_generation,
        _log_reused_asset,
        _,
        _normalize_unlock_requirements,
        _publish_generation_status_with_callback,
        is_image_moderation_error,
    ) = _get_generation_helpers()

    processed_npcs: list[dict] = []
    npc_image_cache: dict[str, str] = {}
    total = len(npcs)

    for idx, n in enumerate(npcs, start=1):
        if n["id"] in seen_entity_ids:
            continue
        seen_entity_ids.add(n["id"])

        duplicate_url = _find_duplicate_image_url(n, processed_npcs, npc_image_cache)
        reused_url = _resolve_source_asset_image(source_assets, template_id, "npc", n.get("source_asset_id"))
        image_url = duplicate_url or existing_images.get(n["id"]) or reused_url or n.get("image_url")
        if not _is_usable_image_url(image_url):
            image_url = None
        if image_url and image_url == reused_url:
            await _log_reused_asset(db, adventure, f"NPC: {n.get('name')}", image_url)

        if not image_url or image_url.startswith("assets/"):
            if user and gen_npc:
                await _publish_generation_status_with_callback(
                    db, adventure,
                    f"Envisioning Portrait {idx}/{total}: {n['name']}...",
                    status_callback=status_callback,
                )
                prompt = prompts.NPC_IMAGE_PROMPT_TEMPLATE.format(
                    name=n["name"], description=n["description"]
                )
                image_counters["attempts"] += 1
                try:
                    image_url = await asyncio.wait_for(
                        MediaEngine.generate_entity_image(
                            prompt, template_id, n["id"], "NPC",
                            {"t2i_settings": user.t2i_settings},
                            dict(user.encrypted_api_keys or {}),  # type: ignore[arg-type]
                            style_instruction=style_instruction,
                            use_advanced_model=((user.t2i_settings or {}).get("profile_model_quality", "advanced") == "advanced"),
                        ),
                        timeout=float(settings.VISUAL_TIMEOUT),
                    )
                except asyncio.TimeoutError:
                    logger.warning("NPC image generation timed out after %ss for %s/%s", settings.VISUAL_TIMEOUT, template_id, n["id"])
                    image_url = None
                except Exception as exc:
                    if is_image_moderation_error(exc):
                        image_counters["moderation"] += 1
                    logger.warning("NPC image generation failed for %s/%s: %s", template_id, n["id"], exc)
                    image_url = None
                if image_url:
                    image_counters["successes"] += 1
                    await _log_image_generation(db, adventure, prompt, image_url)

            if not image_url or image_url.startswith("assets/"):
                image_url = await MediaEngine.generate_placeholder(
                    template_id, n["id"],
                    os.path.join(settings.DATA_DIR, "adventures", "library", template_id, "entities"),
                    category="NPC",
                )

        if image_url:
            npc_image_cache[n["id"]] = image_url
        processed_npcs.append(n)

        db.add(WorldEntity(
            id=n["id"],
            template_id=template_id,
            entity_type="NPC",
            name=n["name"],
            description=n["description"],
            goal=n.get("goal"),
            character=n.get("character"),
            current_scene_id=n.get("start_scene_id") or n.get("current_scene_id") or default_scene_id,
            spatial_position=n.get("spatial_position"),
            image_url=image_url,
            npc_type=n.get("npc_type"),
            movement_type=n.get("movement_type"),
            hp=n.get("hp"),
            max_hp=n.get("hp"),
            mana=n.get("mana"),
            max_mana=n.get("mana"),
            stamina=n.get("stamina"),
            max_stamina=n.get("stamina"),
            is_hidden=n.get("is_hidden", False),
            reveal_rule=n.get("reveal_rule") or None,
            is_attackable=n.get("is_attackable", True),
            is_killable=n.get("is_killable", True),
        ))

        await db.commit()
        adventure = await db.get(AdventureTemplate, template_id)
        if user:
            user = await db.get(User, user.id)

    npc_inventories: dict[str, list[str]] = {
        n["id"]: [
            item_id
            for item_id in (_inventory_item_id(e) for e in (n.get("inventory") or []))
            if item_id
        ]
        for n in npcs
    }
    return processed_npcs, npc_image_cache, npc_inventories


async def _persist_objects(
    db: AsyncSession,
    adventure: AdventureTemplate,
    template_id: str,
    objects: list[dict[str, Any]],
    default_scene_id: str,
    existing_images: dict[str, str],
    source_assets: Optional[dict[str, Any]],
    user: Optional[User],
    gen_items: bool,
    style_instruction: str,
    status_callback: Optional[Callable[[str], Awaitable[None]]],
    image_counters: dict[str, int],
    seen_entity_ids: set[str],
    starting_inv_ids: set[str],
    starting_equipped_ids: dict[str, str],
    protagonist_item_defs: dict[str, dict[str, Any]],
    all_npc_inventory_item_ids: set[str],
    avatar: Any,
) -> dict[str, dict[str, Any]]:
    """Persist world objects and generate item images. Returns resolved_items mapping."""
    from backend.engine.item_logic import get_item_slot  # noqa: PLC0415
    from backend.engine.media_engine import MediaEngine  # noqa: PLC0415

    (
        _image_generation_timeout_seconds,
        _log_image_generation,
        _log_reused_asset,
        _normalize_text_log_content,
        _normalize_unlock_requirements,
        _publish_generation_status_with_callback,
        is_image_moderation_error,
    ) = _get_generation_helpers()

    processed_objects: list[dict] = []
    object_image_cache: dict[str, str] = {}
    resolved_items: dict[str, dict[str, Any]] = {}
    total = len(objects)

    for idx, o in enumerate(objects, start=1):
        if o["id"] in seen_entity_ids:
            continue
        seen_entity_ids.add(o["id"])

        source_item = protagonist_item_defs.get(o["id"], {})
        stat_strength = _extract_numeric_stat(o, source_item, "stat_modifier_strength", "strength")
        stat_dexterity = _extract_numeric_stat(o, source_item, "stat_modifier_dexterity", "stat_modifier_agility", "dexterity", "agility")
        stat_intelligence = _extract_numeric_stat(o, source_item, "stat_modifier_intelligence", "intelligence")
        stat_wisdom = _extract_numeric_stat(o, source_item, "stat_modifier_wisdom", "wisdom")
        stat_charisma = _extract_numeric_stat(o, source_item, "stat_modifier_charisma", "charisma")
        stat_armor_class = _extract_numeric_stat(o, source_item, "stat_modifier_armor_class", "armor_class", "ac")
        hp_change = _extract_numeric_effect(o, source_item, "hp_change", "health_change", "heal", "heal_amount", "restore_hp", "restore_health", "hp")
        stamina_change = _extract_numeric_effect(o, source_item, "stamina_change", "restore_stamina", "stamina_restore", "stamina", "energy")
        mana_change = _extract_numeric_effect(o, source_item, "mana_change", "restore_mana", "mana_restore", "mana")

        duplicate_url = _find_duplicate_image_url(o, processed_objects, object_image_cache)
        reused_url = _resolve_source_asset_image(source_assets, template_id, "object", o.get("source_asset_id"))
        image_url = duplicate_url or existing_images.get(o["id"]) or reused_url or o.get("image_url")
        if not _is_usable_image_url(image_url):
            image_url = None
        if image_url and image_url == reused_url:
            await _log_reused_asset(db, adventure, f"Item: {o.get('name')}", image_url)

        if not image_url or image_url.startswith("assets/"):
            if user and gen_items:
                await _publish_generation_status_with_callback(
                    db, adventure,
                    f"Reifying Artifact {idx}/{total}: {o['name']}...",
                    status_callback=status_callback,
                )
                prompt = prompts.OBJECT_IMAGE_PROMPT_TEMPLATE.format(
                    name=o["name"], description=o["description"]
                )
                image_counters["attempts"] += 1
                try:
                    image_url = await asyncio.wait_for(
                        MediaEngine.generate_entity_image(
                            prompt, template_id, o["id"], "OBJECT",
                            {"t2i_settings": user.t2i_settings},
                            dict(user.encrypted_api_keys or {}),  # type: ignore[arg-type]
                            style_instruction=style_instruction,
                            use_advanced_model=((user.t2i_settings or {}).get("asset_model_quality", "simple") == "advanced"),
                        ),
                        timeout=float(settings.VISUAL_TIMEOUT),
                    )
                except Exception as exc:
                    if is_image_moderation_error(exc):
                        image_counters["moderation"] += 1
                    logger.warning("Object image generation failed for %s/%s: %s", template_id, o["id"], exc)
                    image_url = None
                if image_url:
                    image_counters["successes"] += 1
                    await _log_image_generation(db, adventure, prompt, image_url)

            if not image_url or image_url.startswith("assets/"):
                item_type = str(o.get("item_type") or "PICKABLE").upper()
                safe_entity_id = slugify(str(o.get("id") or "")) or "entity"
                image_url = await MediaEngine.generate_placeholder(
                    template_id, safe_entity_id,
                    os.path.join(settings.DATA_DIR, "adventures", "library", template_id, "entities"),
                    category=f"ITEM_{item_type}",
                )

        is_starting_inv = o["id"] in starting_inv_ids
        starting_slot = starting_equipped_ids.get(o["id"])
        is_in_avatar_inv = is_starting_inv or (starting_slot is not None)
        is_in_npc_inv = o["id"] in all_npc_inventory_item_ids

        guessed_slot = get_item_slot(o["name"], o.get("item_type", "PICKABLE"))
        item_slot = (
            o.get("wearable_slots")[0]
            if (o.get("wearable_slots") and len(o.get("wearable_slots")) > 0)
            else guessed_slot
        )

        resolved_items[o["id"]] = {
            "id": o["id"],
            "name": o["name"],
            "description": o["description"],
            "image_url": image_url,
            "item_type": o.get("item_type", "PICKABLE"),
            "slot": item_slot,
            "text_log_content": _normalize_text_log_content(
                o.get("text_log_content"), o.get("description"), o.get("name")
            ),
            "text_log_format": str(o.get("text_log_format") or "").strip().upper() or None,
            "stat_modifier_strength": stat_strength,
            "stat_modifier_dexterity": stat_dexterity,
            "stat_modifier_intelligence": stat_intelligence,
            "stat_modifier_wisdom": stat_wisdom,
            "stat_modifier_charisma": stat_charisma,
            "stat_modifier_armor_class": stat_armor_class,
            "hp_change": hp_change,
            "stamina_change": stamina_change,
            "mana_change": mana_change,
        }

        metadata_json = dict(o.get("metadata_json") or {})
        if hp_change is not None:
            metadata_json["hp_change"] = hp_change
        if stamina_change is not None:
            metadata_json["stamina_change"] = stamina_change
        if mana_change is not None:
            metadata_json["mana_change"] = mana_change

        if str(o.get("item_type") or "").upper() == "READABLE":
            _meta = o.get("metadata_json") or {}
            text_log_content = _normalize_text_log_content(
                o.get("text_log_content") or _meta.get("text_log_content"),
                o.get("description"),
                o.get("name"),
            )
            text_log_format = str(
                o.get("text_log_format") or _meta.get("text_log_format") or "DOCUMENT"
            ).strip().upper()
            if text_log_format not in {"DOCUMENT", "SCROLL", "BOOK", "SIGN"}:
                text_log_format = "DOCUMENT"
            metadata_json["text_log_content"] = text_log_content
            metadata_json["text_log_format"] = text_log_format

        if str(o.get("item_type") or "").upper() == "CONTAINER":
            code_to_unlock, item_to_unlock, rule_to_unlock = _normalize_unlock_requirements(
                o.get("code_to_unlock"), o.get("item_to_unlock"), o.get("rule_to_unlock")
            )
            metadata_json["code_to_unlock"] = code_to_unlock
            metadata_json["item_to_unlock"] = item_to_unlock
            metadata_json["rule_to_unlock"] = rule_to_unlock
            metadata_json["locked"] = bool(code_to_unlock or item_to_unlock or rule_to_unlock)

        if str(o.get("item_type") or "").upper() == "SWITCH":
            raw_states = o.get("switch_states") or []
            states_normalized: list[str] = []
            for state in raw_states:
                token = str(state or "").strip().upper()
                if token and token not in states_normalized:
                    states_normalized.append(token)
            if len(states_normalized) < 2:
                states_normalized = ["OFF", "ON"]
            initial_state = str(o.get("switch_initial_state") or states_normalized[0]).strip().upper()
            if initial_state not in states_normalized:
                initial_state = states_normalized[0]
            transitions = o.get("switch_transitions")
            if not isinstance(transitions, list):
                transitions = []
            outcomes = o.get("switch_outcomes")
            if not isinstance(outcomes, list):
                outcomes = []
            metadata_json["switch"] = {
                "states": states_normalized,
                "initial_state": initial_state,
                "transitions": transitions,
                "outcomes": outcomes,
            }
            metadata_json.setdefault("discovery_visibility", {
                "mentioned_in_scene": True,
                "listed_in_discoveries": False,
                "lootable": False,
            })

        if avatar and is_in_avatar_inv:
            if is_starting_inv:
                avatar.inventory = list(avatar.inventory) + [o["id"]]  # type: ignore[assignment]
            if starting_slot:
                new_equip = dict(avatar.equipment)
                new_equip[starting_slot] = o["id"]
                avatar.equipment = new_equip  # type: ignore[assignment]

        if image_url:
            object_image_cache[o["id"]] = image_url
        processed_objects.append(o)

        db.add(WorldEntity(
            id=o["id"],
            template_id=template_id,
            entity_type="OBJECT",
            name=o["name"],
            description=o["description"],
            current_scene_id="INVENTORY" if (is_in_avatar_inv or is_in_npc_inv) else (
                o.get("start_scene_id") or o.get("current_scene_id") or default_scene_id
            ),
            spatial_position=o.get("spatial_position"),
            image_url=image_url,
            item_type=o.get("item_type", "PICKABLE"),
            wearable_slots=o.get("wearable_slots"),
            is_hidden=o.get("is_hidden", False),
            reveal_rule=o.get("reveal_rule") or None,
            unlock_rule=None,
            is_in_inventory=is_in_avatar_inv or is_in_npc_inv,
            is_portable=o.get("is_portable", o.get("item_type") != "STATIC"),
            combination_ingredients=o.get("combination_ingredients"),
            reveals_item_id=o.get("reveals_item_id"),
            inventory=o.get("inventory") or [],
            state_comment=o.get("state_comment"),
            stat_modifier_strength=stat_strength,
            stat_modifier_dexterity=stat_dexterity,
            stat_modifier_intelligence=stat_intelligence,
            stat_modifier_wisdom=stat_wisdom,
            stat_modifier_charisma=stat_charisma,
            stat_modifier_armor_class=stat_armor_class,
            metadata_json=metadata_json,
        ))

        await db.commit()
        adventure = await db.get(AdventureTemplate, template_id)
        if user:
            user = await db.get(User, user.id)

    return resolved_items


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def apply_manifest(
    db: AsyncSession,
    template_id: str,
    manifest_dict: dict,
    user: Optional[User] = None,
    gen_npc: bool = False,
    gen_items: bool = False,
    gen_scenes: bool = False,
    gen_protagonist_image: bool = False,
    existing_images: Optional[dict] = None,
    source_assets: Optional[dict[str, Any]] = None,
    selected_image_styles: Optional[list[str]] = None,
    status_callback: Optional[Callable[[str], Awaitable[None]]] = None,
) -> None:
    """Populate (or re-populate) the world entities based on a manifest dictionary.

    If user is provided, attempts to generate entity images based on flags.
    If existing_images is provided, uses them to restore entity visual states.
    """
    from backend.engine.media_engine import MediaEngine  # noqa: PLC0415
    from backend.engine.world_generator import preprocess_manifest_object_ids  # noqa: PLC0415

    (
        _image_generation_timeout_seconds,
        _log_image_generation,
        _log_reused_asset,
        _normalize_text_log_content,
        _normalize_unlock_requirements,
        _publish_generation_status_with_callback,
        is_image_moderation_error,
    ) = _get_generation_helpers()

    preprocess_manifest_object_ids(manifest_dict)
    adventure = await db.get(AdventureTemplate, template_id)

    image_counters = {"attempts": 0, "successes": 0, "moderation": 0}

    if selected_image_styles is None and adventure:
        selected_image_styles = adventure.selected_image_styles

    style_instruction = resolve_style_instruction(
        selected_image_styles,
        (user.image_styles_catalog if user else None),
    )
    logger.info("Applying manifest with style instruction: '%s'", style_instruction)

    from backend.engine.world_generator import _validate_t2i_prerequisites  # noqa: PLC0415
    _validate_t2i_prerequisites(
        user,
        need_scene_images=gen_scenes,
        need_npc_images=gen_npc,
        need_item_images=gen_items,
        need_protagonist_image=gen_protagonist_image,
    )

    from backend.core.llm_logger import log_structured_event  # noqa: PLC0415
    log_structured_event(
        "adventure.generation.apply_manifest.start",
        template_id=template_id,
        scene_count=len(manifest_dict.get("scenes", [])),
        exit_count=len(manifest_dict.get("exits", [])),
        npc_count=len(manifest_dict.get("npcs", [])),
        object_count=len(manifest_dict.get("objects", [])),
    )

    # Preserve any existing images if caller didn't provide them
    if existing_images is None:
        existing_images = {}
        ent_res = await db.execute(select(WorldEntity).where(WorldEntity.template_id == template_id))
        for e in ent_res.scalars().all():
            if e.image_url:
                existing_images[e.id] = e.image_url
        scene_res = await db.execute(select(WorldScene).where(WorldScene.template_id == template_id))
        for s in scene_res.scalars().all():
            if s.image_url:
                existing_images[s.id] = s.image_url

    # Ensure idempotency: clear prior world objects
    await db.execute(delete(WorldScene).where(WorldScene.template_id == template_id))
    await db.execute(delete(WorldExit).where(WorldExit.template_id == template_id))
    await db.execute(delete(WorldEntity).where(WorldEntity.template_id == template_id))

    seen_scene_ids: set[str] = set()
    seen_entity_ids: set[str] = set()
    avatar = None

    # --- 0. Sync Quests and Narrative Meta ---
    if adventure:
        quests = manifest_dict.get("quests") or []
        awards = manifest_dict.get("awards") or []

        if adventure.rule_enforcement_mode == "chat":
            quests = []
            awards = []

        for q in quests:
            if "status" not in q:
                q["status"] = "open"
        adventure.quests = quests  # type: ignore[assignment]

        # In standard ADV manifests, narrative metadata is nested under
        # `adventure`; look there first and fall back to top-level keys.
        adv_block = manifest_dict.get("adventure") if isinstance(manifest_dict.get("adventure"), dict) else {}
        def _adv_field(key):
            if key in adv_block and adv_block[key] is not None:
                return adv_block[key]
            return manifest_dict.get(key)

        teaser = _adv_field("teaser")
        if teaser:
            adventure.teaser = teaser  # type: ignore[assignment]

        adventure.plot = _adv_field("plot") or adventure.plot  # type: ignore[assignment]
        adventure.rules = _adv_field("rules") or adventure.rules  # type: ignore[assignment]
        adventure.intro_text = _adv_field("intro_text") or adventure.intro_text  # type: ignore[assignment]
        adventure.walkthrough = _adv_field("walkthrough") or adventure.walkthrough  # type: ignore[assignment]
        adventure.completed_condition = _adv_field("completed_condition") or adventure.completed_condition  # type: ignore[assignment]
        adventure.gameover_condition = _adv_field("gameover_condition") or adventure.gameover_condition  # type: ignore[assignment]
        adventure.tts_director_notes = _adv_field("tts_director_notes") or adventure.tts_director_notes  # type: ignore[assignment]
        adventure.creator = _adv_field("creator") or adventure.creator  # type: ignore[assignment]
        adventure.copyright = _adv_field("copyright") or adventure.copyright  # type: ignore[assignment]
        adventure.license = _adv_field("license") or adventure.license  # type: ignore[assignment]
        adventure.license_url = _adv_field("license_url") or adventure.license_url  # type: ignore[assignment]

        if manifest_dict.get("time_system"):
            adventure.time_system = manifest_dict["time_system"]  # type: ignore[assignment]
        if manifest_dict.get("time_config"):
            adventure.time_config = manifest_dict["time_config"]  # type: ignore[assignment]
        if manifest_dict.get("starting_timestamp") is not None:
            adventure.starting_timestamp = manifest_dict["starting_timestamp"]  # type: ignore[assignment]
        if manifest_dict.get("allow_dynamic_items") is not None:
            adventure.allow_dynamic_items = manifest_dict["allow_dynamic_items"]  # type: ignore[assignment]
        if manifest_dict.get("can_damage_npcs") is not None:
            adventure.can_damage_npcs = manifest_dict["can_damage_npcs"]  # type: ignore[assignment]
        if manifest_dict.get("npcs_can_damage_protagonist") is not None:
            adventure.npcs_can_damage_protagonist = manifest_dict["npcs_can_damage_protagonist"]  # type: ignore[assignment]
        if manifest_dict.get("game_over_rules") is not None:
            adventure.game_over_rules = manifest_dict["game_over_rules"]  # type: ignore[assignment]
        if manifest_dict.get("awards") is not None:
            adventure.awards = manifest_dict["awards"]  # type: ignore[assignment]

        # Simple start_time heuristic (08:00 -> 480 mins)
        if manifest_dict.get("start_time"):
            try:
                h, m = map(int, manifest_dict["start_time"].split(":"))
                adventure.starting_timestamp = h * 60 + m  # type: ignore[assignment]
            except Exception:
                pass

        for a in awards:
            if "is_earned" not in a:
                a["is_earned"] = False
        adventure.awards = awards  # type: ignore[assignment]

        # Sync to active sessions
        from backend.models.session_state import SessionState  # noqa: PLC0415
        state_res = await db.execute(select(SessionState).where(SessionState.template_id == template_id))
        for state in state_res.scalars().all():
            if not state.quests:
                state.quests = quests
            state.plot = adventure.plot
            state.rules = adventure.rules
            state.walkthrough = adventure.walkthrough
            state.completed_condition = adventure.completed_condition
            state.gameover_condition = adventure.gameover_condition
            state.tts_director_notes = adventure.tts_director_notes
            state.time_system = adventure.time_system
            state.time_config = adventure.time_config

        await db.commit()
        adventure = await db.get(AdventureTemplate, template_id)
        if user:
            user = await db.get(User, user.id)

        # Generate Adventure Cover if missing
        any_image_generation_enabled = bool(gen_scenes or gen_npc or gen_items or gen_protagonist_image)
        existing_cover_url = adventure.image_url if _is_usable_image_url(adventure.image_url) else None
        if adventure and user and not existing_cover_url and any_image_generation_enabled:
            await _publish_generation_status_with_callback(
                db, adventure, "Painting Adventure Cover...", status_callback=status_callback
            )
            try:
                requested_cover_source_id = manifest_dict.get("cover_source_asset_id")
                reused_cover_url = None
                if requested_cover_source_id == "COVER":
                    reused_cover_url = _resolve_source_asset_image(source_assets, template_id, "cover", requested_cover_source_id)
                if reused_cover_url:
                    cover_url = reused_cover_url
                    await _log_reused_asset(db, adventure, "Adventure Cover", cover_url)
                else:
                    image_counters["attempts"] += 1
                    cover_url = await MediaEngine.generate_adventure_cover(
                        title=adventure.title,
                        original_prompt=adventure.teaser or adventure.original_prompt,
                        adventure_id=template_id,
                        user_config={"t2i_settings": user.t2i_settings},
                        api_keys=dict(user.encrypted_api_keys or {}),  # type: ignore[arg-type]
                        style_instruction=style_instruction,
                    )
                if cover_url:
                    image_counters["successes"] += 1
                    adventure.image_url = cover_url  # type: ignore[assignment]
                    if not reused_cover_url:
                        await _log_image_generation(db, adventure, adventure.teaser or adventure.original_prompt, cover_url)
                    await db.commit()
                    adventure = await db.get(AdventureTemplate, template_id)
            except Exception as e:
                if is_image_moderation_error(e):
                    image_counters["moderation"] += 1
                logger.warning("Failed to generate adventure cover for %s: %s", template_id, e)

        await db.flush()

    # --- 0. Sync Protagonist to Avatar ---
    prot = manifest_dict.get("protagonist", {})
    starting_equipped_ids: dict[str, str] = {}
    starting_inv_ids: set[str] = set()
    protagonist_item_defs: dict[str, dict[str, Any]] = {}

    if prot and adventure:
        avatar, starting_equipped_ids, starting_inv_ids, protagonist_item_defs = await _persist_avatar(
            db=db,
            adventure=adventure,
            template_id=template_id,
            prot=prot,
            manifest_dict=manifest_dict,
            user=user,
            gen_protagonist_image=gen_protagonist_image,
            existing_images=existing_images,
            source_assets=source_assets,
            style_instruction=style_instruction,
            status_callback=status_callback,
            image_counters=image_counters,
        )
        await db.commit()
        adventure = await db.get(AdventureTemplate, template_id)

    # --- Persist Scenes ---
    scenes = manifest_dict.get("scenes", [])
    await _persist_scenes(
        db=db,
        adventure=adventure,
        template_id=template_id,
        scenes=scenes,
        existing_images=existing_images,
        source_assets=source_assets,
        user=user,
        gen_scenes=gen_scenes,
        style_instruction=style_instruction,
        status_callback=status_callback,
        image_counters=image_counters,
        seen_scene_ids=seen_scene_ids,
    )

    # --- Persist Exits ---
    _persist_exits(db, template_id, manifest_dict.get("exits", []))

    await db.commit()
    adventure = await db.get(AdventureTemplate, template_id)

    # --- Persist NPCs ---
    npcs = manifest_dict.get("npcs", [])
    default_scene_id = scenes[0]["id"] if scenes else "START"
    processed_npcs, npc_image_cache, npc_inventories = await _persist_npcs(
        db=db,
        adventure=adventure,
        template_id=template_id,
        npcs=npcs,
        default_scene_id=default_scene_id,
        existing_images=existing_images,
        source_assets=source_assets,
        user=user,
        gen_npc=gen_npc,
        style_instruction=style_instruction,
        status_callback=status_callback,
        image_counters=image_counters,
        seen_entity_ids=seen_entity_ids,
    )

    await db.commit()
    adventure = await db.get(AdventureTemplate, template_id)

    # --- Persist Objects ---
    if adventure:
        # In standard ADV manifests, narrative metadata is nested under
        # `adventure` rather than at the top level. Look there first and
        # fall back to the top level for legacy/loose manifests. Without
        # this fallback, importing a freshly-exported ADV would silently
        # wipe out `teaser`, `rules`, `language`, etc. with empty strings.
        adv_block = manifest_dict.get("adventure") if isinstance(manifest_dict.get("adventure"), dict) else {}
        def _adv_field(key, default=""):
            if key in adv_block and adv_block[key] is not None:
                return adv_block[key]
            if key in manifest_dict and manifest_dict[key] is not None:
                return manifest_dict[key]
            return default

        adventure.teaser = _adv_field("teaser", "")  # type: ignore[assignment]
        adventure.original_prompt = _adv_field("original_prompt", adventure.original_prompt or "")  # type: ignore[assignment]
        adventure.rules = _adv_field("rules", "")  # type: ignore[assignment]
        adventure.language = _adv_field("language", "")  # type: ignore[assignment]
        adventure.creator = _adv_field("creator", adventure.creator)  # type: ignore[assignment]
        adventure.copyright = _adv_field("copyright", adventure.copyright)  # type: ignore[assignment]
        adventure.license = _adv_field("license", adventure.license)  # type: ignore[assignment]
        adventure.license_url = _adv_field("license_url", adventure.license_url)  # type: ignore[assignment]
        adventure.is_ready = False  # type: ignore[assignment]
        adventure.origin_id = _adv_field("origin_id", "")  # type: ignore[assignment]
        adventure.is_adventure_generator = _adv_field("is_adventure_generator", False)  # type: ignore[assignment]
        adventure.can_damage_npcs = _adv_field("can_damage_npcs", True)  # type: ignore[assignment]
        adventure.npcs_can_damage_protagonist = _adv_field("npcs_can_damage_protagonist", True)  # type: ignore[assignment]
        adventure.original_manifest = manifest_dict  # type: ignore[assignment]

    objects = list(manifest_dict.get("objects", []))
    seen_object_ids = {o.get("id") for o in objects if isinstance(o, dict) and "id" in o}

    # Merge protagonist inline item definitions into the objects list
    if prot:
        for item in (prot.get("starting_inventory") or []):
            if isinstance(item, dict) and "id" in item and item["id"] not in seen_object_ids:
                objects.append(item)
                seen_object_ids.add(item["id"])
        for slot, item in (prot.get("starting_equipment") or {}).items():
            if isinstance(item, dict) and "id" in item and item["id"] not in seen_object_ids:
                objects.append(item)
                seen_object_ids.add(item["id"])

    all_npc_inventory_item_ids: set[str] = set()
    for inv in npc_inventories.values():
        all_npc_inventory_item_ids.update(inv)

    resolved_items = await _persist_objects(
        db=db,
        adventure=adventure,
        template_id=template_id,
        objects=objects,
        default_scene_id=default_scene_id,
        existing_images=existing_images,
        source_assets=source_assets,
        user=user,
        gen_items=gen_items,
        style_instruction=style_instruction,
        status_callback=status_callback,
        image_counters=image_counters,
        seen_entity_ids=seen_entity_ids,
        starting_inv_ids=starting_inv_ids,
        starting_equipped_ids=starting_equipped_ids,
        protagonist_item_defs=protagonist_item_defs,
        all_npc_inventory_item_ids=all_npc_inventory_item_ids,
        avatar=avatar,
    )

    # --- Final Pass: Update NPC Inventories ---
    npc_objs_res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.entity_type == "NPC",
        )
    )
    all_npcs = {n.id: n for n in npc_objs_res.scalars().all()}
    for npc_id, item_ids in npc_inventories.items():
        if not item_ids or npc_id not in all_npcs:
            continue
        npc_obj = all_npcs[npc_id]
        npc_obj.inventory = [resolved_items[iid] for iid in item_ids if iid in resolved_items]  # type: ignore[assignment]

    await db.commit()

    log_structured_event(
        "adventure.generation.apply_manifest.complete",
        template_id=template_id,
        scene_count=len(manifest_dict.get("scenes", [])),
        exit_count=len(manifest_dict.get("exits", [])),
        npc_count=len(manifest_dict.get("npcs", [])),
        object_count=len(manifest_dict.get("objects", [])),
        image_attempts=image_counters["attempts"],
        image_successes=image_counters["successes"],
    )

    requested_image_generation = bool(user and (gen_scenes or gen_npc or gen_items or gen_protagonist_image))
    warning_messages: list[str] = []

    if image_counters["moderation"] > 0:
        warning_messages.append(
            f"Notice: {image_counters['moderation']} images were blocked by safety filters and replaced with placeholders. "
            "You can regenerate them in the editor with adjusted descriptions."
        )
    if (
        requested_image_generation
        and image_counters["attempts"] > 0
        and image_counters["successes"] == 0
        and image_counters["moderation"] == 0
    ):
        warning_messages.append(
            "Notice: Image generation did not return usable images, so placeholders were used. "
            "You can regenerate visuals later in the editor."
        )

    if warning_messages and adventure:
        adventure.creation_error = " ".join(warning_messages)  # type: ignore[assignment]
        await db.commit()
