"""
World generation orchestrator (facade).

This module is the public entry point for world generation. The actual
implementation is split across focused sub-modules:

- ``backend.engine.world_schemas``      — Pydantic schemas for LLM output.
- ``backend.engine.world_prompt_builder`` — Builds the LLM system/user prompts.
- ``backend.engine.world_manifest_applier`` — Persists the manifest to the DB.

All previously public symbols are re-exported here so existing imports remain
unaffected.
"""
import datetime
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any, Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import prompts
from backend.core.config import settings
from backend.core.llm_logger import log_structured_event
from backend.core.llm_router import GameMasterLLM
from backend.models.adventure_template import AdventureTemplate, GenerationCancelled
from backend.models.user import User
from backend.utils.text_utils import slugify

# --- Re-exports so existing imports stay valid ---
from backend.engine.world_schemas import (  # noqa: F401
    AwardTemplateSchema,
    EquipmentSchema,
    ProtagonistSchema,
    QuestSchema,
    WorldExitSchema,
    WorldManifesto,
    WorldNPCSchema,
    WorldObjectSchema,
    WorldSceneSchema,
)

logger = logging.getLogger(__name__)

IMAGE_MODERATION_MARKERS = (
    "safety filter",
    "content moderated",
    "moderated",
    "content policy",
    "policy violation",
    "blocked by safety",
    "responsible ai",
    "prompt blocked",
)


# ---------------------------------------------------------------------------
# Module-level utilities (kept here: used by tests & other modules directly)
# ---------------------------------------------------------------------------

def is_image_moderation_error(error: Union[Exception, str, None]) -> bool:
    if error is None:
        return False
    message = str(error).lower()
    return any(marker in message for marker in IMAGE_MODERATION_MARKERS)


def _build_voice_assignment_requirement(
    enabled: bool,
    available_voice_list: Optional[list[str]] = None,
) -> str:
    return ""


def _image_generation_timeout_seconds() -> float:
    raw_timeout = getattr(settings, "IMAGE_GENERATION_TIMEOUT_SECONDS", 600)
    try:
        timeout = float(raw_timeout)
    except (TypeError, ValueError):
        timeout = 120.0
    return max(10.0, timeout)


def _validate_t2i_prerequisites(
    user: Optional[User],
    *,
    need_scene_images: bool,
    need_npc_images: bool,
    need_item_images: bool,
    need_protagonist_image: bool,
) -> None:
    if not user:
        return
    needs_any_images = need_scene_images or need_npc_images or need_item_images or need_protagonist_image
    if not needs_any_images:
        return

    t2i_settings = user.t2i_settings or {}
    if not t2i_settings:
        raise ValueError(
            "Image generation is enabled, but no image settings are configured. "
            "Open Settings and configure Text-to-Image provider and models."
        )

    if need_scene_images:
        model = (t2i_settings.get("advanced_model") or "").strip()
        if not model:
            raise ValueError("Image generation is enabled for scenes, but advanced_model is missing.")
        provider = (t2i_settings.get("advanced_model_provider") or t2i_settings.get("provider", "openai")).lower()
        if provider not in ("ollama", "stable_diffusion"):
            if not settings.get_env_api_key(provider):
                encrypted_api_keys = user.encrypted_api_keys or {}
                if provider not in encrypted_api_keys:
                    raise ValueError(f"API key missing for advanced image provider '{provider}'.")

    if need_npc_images or need_item_images or need_protagonist_image:
        model = (t2i_settings.get("simple_model") or "").strip()
        if not model:
            raise ValueError("Image generation is enabled for portraits/items, but simple_model is missing.")
        provider = (t2i_settings.get("simple_model_provider") or t2i_settings.get("provider", "openai")).lower()
        if provider not in ("ollama", "stable_diffusion"):
            if not settings.get_env_api_key(provider):
                encrypted_api_keys = user.encrypted_api_keys or {}
                if provider not in encrypted_api_keys:
                    raise ValueError(f"API key missing for simple image provider '{provider}'.")


async def _publish_generation_status(
    db: AsyncSession,
    adventure: Optional[AdventureTemplate],
    status: str,
) -> None:
    """Persist live status text; raise GenerationCancelled if user cancelled."""
    if not adventure:
        return
    await db.refresh(adventure)
    if adventure.creation_status == "Cancelled":
        raise GenerationCancelled("Generation was cancelled by the user.")
    adventure.creation_status = status  # type: ignore[assignment]
    logs = list(adventure.generation_logs or [])
    logs.append({
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "type": "status",
        "content": status,
    })
    adventure.generation_logs = logs  # type: ignore[assignment]
    await db.commit()
    await db.refresh(adventure)


async def _log_image_generation(
    db: AsyncSession,
    adventure: Optional[AdventureTemplate],
    prompt: str,
    image_url: str,
) -> None:
    """Log AI-generated image prompt and URL."""
    if not adventure or not image_url or image_url.startswith("assets/"):
        return
    logs = list(adventure.generation_logs or [])
    logs.append({
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "type": "image_generation",
        "content": prompt,
        "image_url": image_url,
    })
    adventure.generation_logs = logs  # type: ignore[assignment]
    await db.commit()
    await db.refresh(adventure)


async def _log_reused_asset(
    db: AsyncSession,
    adventure: Optional[AdventureTemplate],
    entity_name: str,
    image_url: str,
) -> None:
    """Log reused/copied visual asset."""
    if not adventure or not image_url or image_url.startswith("assets/"):
        return
    logs = list(adventure.generation_logs or [])
    logs.append({
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "type": "image_generation",
        "content": f"Reused source asset: {entity_name}",
        "image_url": image_url,
    })
    adventure.generation_logs = logs  # type: ignore[assignment]
    await db.commit()
    await db.refresh(adventure)


async def _publish_generation_status_with_callback(
    db: AsyncSession,
    adventure: Optional[AdventureTemplate],
    status: str,
    status_callback: Optional[Callable[[str], Awaitable[None]]] = None,
) -> None:
    """Persist generation status and optionally forward it to an external observer."""
    await _publish_generation_status(db, adventure, status)
    if status_callback:
        try:
            await status_callback(status)
        except Exception as exc:
            logger.warning("Generation status callback failed for %s: %s", status, exc)


def _uses_ollama_t2i(user: Optional[User]) -> bool:
    if not user:
        return False
    t2i_settings = user.t2i_settings or {}
    return (t2i_settings.get("provider") or "").lower() == "ollama"


def _normalize_text_log_content(
    raw_content: Any,
    description_fallback: Any = "",
    name_fallback: Any = "",
) -> str:
    """Normalize readable text while preserving paragraph breaks and enforcing length."""
    content = str(raw_content or "")
    if not content.strip():
        content = str(description_fallback or "")
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    normalized_lines = [line.rstrip() for line in content.split("\n")]
    normalized = "\n".join(normalized_lines).strip()
    if not normalized:
        safe_name = str(name_fallback or "This note").strip() or "This note"
        normalized = f"{safe_name} contains faded but readable notes."
    return normalized[:500]


def _normalize_unlock_requirements(
    raw_code: Any,
    raw_item: Any,
    raw_rule: Any,
) -> tuple[str, str, str]:
    """Normalize unlock requirements and enforce mutual exclusivity (code > item > rule)."""
    code_to_unlock = str(raw_code or "").strip()
    item_to_unlock = str(raw_item or "").strip().upper()
    rule_to_unlock = str(raw_rule or "").strip()

    if code_to_unlock:
        code_to_unlock = code_to_unlock[:32]
        item_to_unlock = ""
        rule_to_unlock = ""
    elif item_to_unlock:
        item_to_unlock = slugify(item_to_unlock).upper().replace("-", "_")[:64]
        code_to_unlock = ""
        rule_to_unlock = ""
    elif rule_to_unlock:
        rule_to_unlock = rule_to_unlock[:500]
        code_to_unlock = ""
        item_to_unlock = ""
    else:
        code_to_unlock = ""
        item_to_unlock = ""
        rule_to_unlock = ""

    return code_to_unlock, item_to_unlock, rule_to_unlock


def _extract_item_id(entry: Any) -> Optional[str]:
    if isinstance(entry, str):
        normalized = entry.strip()
        return normalized or None
    if isinstance(entry, dict):
        for key in ("id", "item_id", "object_id"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _ensure_containers_have_minimum_inventory(objects: list[dict[str, Any]]) -> None:
    """Ensure every generated CONTAINER references at least one item ID in inventory.

    Only reuses existing valid item IDs; never fabricates new items.
    """
    if not isinstance(objects, list) or not objects:
        return

    container_objs: list[dict[str, Any]] = []
    object_ids_in_order: list[str] = []
    seen_ids: set[str] = set()

    for obj in objects:
        if not isinstance(obj, dict):
            continue
        obj_id = str(obj.get("id") or "").strip()
        if obj_id and obj_id not in seen_ids:
            seen_ids.add(obj_id)
            object_ids_in_order.append(obj_id)
        if str(obj.get("item_type") or "").upper() == "CONTAINER":
            container_objs.append(obj)

    if not container_objs:
        return

    object_ids_set = set(object_ids_in_order)
    candidate_item_ids = [
        str(obj.get("id") or "").strip()
        for obj in objects
        if isinstance(obj, dict)
        and str(obj.get("id") or "").strip()
        and str(obj.get("item_type") or "").upper() != "CONTAINER"
    ]

    assigned_ids: set[str] = set()
    for container in container_objs:
        container_id = str(container.get("id") or "").strip()
        raw_inventory = container.get("inventory")
        normalized_inventory: list[str] = []
        if isinstance(raw_inventory, list):
            for entry in raw_inventory:
                item_id = _extract_item_id(entry)
                if not item_id or item_id not in object_ids_set or item_id == container_id:
                    continue
                if item_id in normalized_inventory:
                    continue
                normalized_inventory.append(item_id)
        container["inventory"] = normalized_inventory
        assigned_ids.update(normalized_inventory)

    unassigned_candidates = [iid for iid in candidate_item_ids if iid not in assigned_ids]
    for container in container_objs:
        if container.get("inventory"):
            continue
        if unassigned_candidates:
            chosen_item_id = unassigned_candidates.pop(0)
            container["inventory"] = [chosen_item_id]
            assigned_ids.add(chosen_item_id)


# ---------------------------------------------------------------------------
# WorldGenerator (public API facade)
# ---------------------------------------------------------------------------

class WorldGenerator:
    @staticmethod
    def preprocess_manifest_object_ids(manifest_dict: dict) -> None:
        """Replace bare object-ID references in narrative text with ##OBJECTID tokens.

        Finds all object IDs in the manifest and annotates references to them
        in all narrative text fields so the GM can resolve them deterministically.
        """
        if not isinstance(manifest_dict, dict):
            return
        objects = manifest_dict.get("objects", [])
        if not isinstance(objects, list):
            return

        object_ids = [
            obj.get("id").strip()
            for obj in objects
            if isinstance(obj, dict) and isinstance(obj.get("id"), str) and obj.get("id").strip()
        ]
        if not object_ids:
            return

        object_ids.sort(key=len, reverse=True)

        def replace_ids_in_text(text: Any) -> Any:
            if not isinstance(text, str) or not text:
                return text
            for obj_id in object_ids:
                pattern = rf"(?<!##)\b{re.escape(obj_id)}\b"
                text = re.sub(pattern, f"##{obj_id}", text, flags=re.IGNORECASE)
            return text

        for field in ("teaser", "plot", "rules", "intro_text", "walkthrough", "completed_condition", "gameover_condition", "tts_director_notes"):
            if field in manifest_dict:
                manifest_dict[field] = replace_ids_in_text(manifest_dict[field])

        protagonist = manifest_dict.get("protagonist")
        if isinstance(protagonist, dict):
            for field in ("description", "goal", "character"):
                if field in protagonist:
                    protagonist[field] = replace_ids_in_text(protagonist[field])

        for scene in (manifest_dict.get("scenes") or []):
            if isinstance(scene, dict) and "description" in scene:
                scene["description"] = replace_ids_in_text(scene["description"])

        for exit_val in (manifest_dict.get("exits") or []):
            if isinstance(exit_val, dict):
                for field in ("label", "lock_description", "rule_to_unlock"):
                    if field in exit_val:
                        exit_val[field] = replace_ids_in_text(exit_val[field])

        for npc in (manifest_dict.get("npcs") or []):
            if isinstance(npc, dict):
                for field in ("description", "goal", "character", "spatial_position", "reveal_rule"):
                    if field in npc:
                        npc[field] = replace_ids_in_text(npc[field])

        for obj in objects:
            if isinstance(obj, dict):
                for field in ("description", "spatial_position", "reveal_rule", "text_log_content", "rule_to_unlock"):
                    if field in obj:
                        obj[field] = replace_ids_in_text(obj[field])

        for quest in (manifest_dict.get("quests") or []):
            if isinstance(quest, dict):
                for field in ("title", "description", "goal", "impact"):
                    if field in quest:
                        quest[field] = replace_ids_in_text(quest[field])

        for award in (manifest_dict.get("awards") or []):
            if isinstance(award, dict):
                for field in ("title", "description", "requirement"):
                    if field in award:
                        award[field] = replace_ids_in_text(award[field])

    @staticmethod
    async def generate_world(
        db: AsyncSession,
        user: User,
        template_id: str,
        title: str,
        original_prompt: str,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        generate_scene_images: bool = False,
        generate_npc_images: bool = False,
        generate_item_images: bool = False,
        automatic_npc_voice_assignment: bool = True,
        min_scenes: Optional[int] = None,
        max_scenes: Optional[int] = None,
        container_generation_enabled: bool = True,
        min_containers: Optional[int] = None,
        max_containers: Optional[int] = None,
        text_log_generation_enabled: bool = True,
        min_text_logs: Optional[int] = None,
        max_text_logs: Optional[int] = None,
        quest_generation_enabled: bool = True,
        min_quests: Optional[int] = None,
        max_quests: Optional[int] = None,
        min_items: Optional[int] = None,
        max_items: Optional[int] = None,
        award_generation_enabled: bool = True,
        min_awards: Optional[int] = None,
        max_awards: Optional[int] = None,
        can_damage_npcs: bool = True,
        npcs_can_damage_protagonist: bool = True,
        selected_image_styles: Optional[list[str]] = None,
        selected_tone: Optional[str] = None,
        language: Optional[str] = None,
        cover_source_manifest: Optional[dict[str, Any]] = None,
        cover_source_adventure_id: Optional[str] = None,
        cover_source_adventure_name: Optional[str] = None,
        cover_similarity_percent: int = 50,
        allow_reuse_source_assets: bool = True,
        status_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> None:
        """Call the LLM to generate a coherent world and persist it to the DB.

        Persists the result to the WorldScene, WorldExit, and WorldEntity tables.
        """
        from backend.engine.world_manifest_applier import apply_manifest  # noqa: PLC0415
        from backend.engine.world_prompt_builder import build_world_generation_prompts  # noqa: PLC0415
        from sqlalchemy import select  # noqa: PLC0415
        from backend.models.avatar import Avatar  # noqa: PLC0415

        if not re.match(r"^[a-zA-Z0-9_-]{1,128}$", template_id):
            raise ValueError("Invalid template_id")
        if cover_source_adventure_id and not re.match(r"^[a-zA-Z0-9_-]{1,128}$", cover_source_adventure_id):
            raise ValueError("Invalid cover_source_adventure_id")

        # Resolve provider and model from user settings if not provided
        llm_settings = user.llm_settings or {}
        if not provider:
            provider = (
                llm_settings.get("generator_model_provider")
                or llm_settings.get("complex_model_provider")
                or llm_settings.get("small_model_provider")
                or llm_settings.get("preferred_provider")
            )
        if not model:
            model = (
                llm_settings.get("generator_model")
                or llm_settings.get("complex_model")
                or llm_settings.get("small_model")
                or "gpt-4o"
            )

        tts_settings = user.tts_settings or {}
        available_voice_list = tts_settings.get("voice_list") if isinstance(tts_settings, dict) else None

        if not provider:
            raise ValueError(
                "No adventure generator LLM provider configured for this user. "
                "Open Settings -> Intelligence and set Generator Model Provider."
            )

        llm = GameMasterLLM(user, provider=provider, model_category="generator")

        log_structured_event(
            "adventure.generation.start",
            template_id=template_id,
            title=title,
            provider=provider,
            model=model,
            generate_scene_images=generate_scene_images,
            generate_npc_images=generate_npc_images,
            generate_item_images=generate_item_images,
            context_length=len(original_prompt or ""),
            has_cover_source=bool(cover_source_adventure_id),
            cover_similarity_percent=max(0, min(100, int(cover_similarity_percent or 0))),
            allow_reuse_source_assets=bool(allow_reuse_source_assets),
        )

        system_prompt, user_prompt = build_world_generation_prompts(
            title=title,
            original_prompt=original_prompt,
            language=language,
            selected_tone=selected_tone,
            automatic_npc_voice_assignment=automatic_npc_voice_assignment,
            available_voice_list=available_voice_list,
            can_damage_npcs=can_damage_npcs,
            npcs_can_damage_protagonist=npcs_can_damage_protagonist,
            quest_generation_enabled=quest_generation_enabled,
            min_scenes=min_scenes,
            max_scenes=max_scenes,
            min_quests=min_quests,
            max_quests=max_quests,
            award_generation_enabled=award_generation_enabled,
            min_awards=min_awards,
            max_awards=max_awards,
            container_generation_enabled=container_generation_enabled,
            min_containers=min_containers,
            max_containers=max_containers,
            text_log_generation_enabled=text_log_generation_enabled,
            min_text_logs=min_text_logs,
            max_text_logs=max_text_logs,
            min_items=min_items,
            max_items=max_items,
            cover_source_manifest=cover_source_manifest,
            cover_source_adventure_name=cover_source_adventure_name,
            cover_similarity_percent=cover_similarity_percent,
            allow_reuse_source_assets=allow_reuse_source_assets,
        )

        # 1. Update Status
        adventure = await db.get(AdventureTemplate, template_id)
        if adventure:
            adventure.generation_logs = []  # type: ignore[assignment]
            await db.commit()
            await _publish_generation_status_with_callback(
                db, adventure, "Analyzing Story Idea...", status_callback=status_callback
            )
            log_structured_event(
                "adventure.generation.status",
                template_id=template_id,
                status=adventure.creation_status,
                phase="analysis",
            )
            await db.commit()

        manifesto: WorldManifesto = await llm.aexecute_complex_task(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=WorldManifesto,
            model=model,
            adventure_id=template_id,
            operation="generate_world",
            phase="analysis",
            metadata={
                "generate_scene_images": generate_scene_images,
                "generate_npc_images": generate_npc_images,
                "generate_item_images": generate_item_images,
                "automatic_npc_voice_assignment": automatic_npc_voice_assignment,
                "min_scenes": min_scenes,
                "max_scenes": max_scenes,
                "min_items": min_items,
                "max_items": max_items,
                "container_generation_enabled": container_generation_enabled,
                "min_containers": min_containers,
                "max_containers": max_containers,
                "text_log_generation_enabled": text_log_generation_enabled,
                "min_text_logs": min_text_logs,
                "max_text_logs": max_text_logs,
                "quest_generation_enabled": quest_generation_enabled,
                "min_quests": min_quests,
                "max_quests": max_quests,
            },
        )

        manifest_dict = manifesto.model_dump()
        WorldGenerator.preprocess_manifest_object_ids(manifest_dict)

        log_structured_event(
            "adventure.generation.manifest_received",
            template_id=template_id,
            scene_count=len(manifesto.scenes),
            exit_count=len(manifesto.exits),
            npc_count=len(manifesto.npcs),
            object_count=len(manifesto.objects),
        )

        # 2. Update Status + persist narrative fields
        if adventure:
            await db.refresh(adventure)
            await _publish_generation_status_with_callback(
                db, adventure, "Building Scenes & Plot...", status_callback=status_callback
            )
            log_structured_event(
                "adventure.generation.status",
                template_id=template_id,
                status=adventure.creation_status,
                phase="apply_manifest",
            )
            adventure.teaser = manifest_dict.get("teaser") or ""  # type: ignore[assignment]
            adventure.original_prompt = original_prompt  # type: ignore[assignment]
            if language:
                adventure.language = language  # type: ignore[assignment]
            if not adventure.origin_id:
                adventure.origin_id = manifest_dict.get("origin_id") or template_id  # type: ignore[assignment]
            if not adventure.original_manifest:
                adventure.original_manifest = manifest_dict  # type: ignore[assignment]
            await db.commit()

        # Load source assets for cover-mode image reuse
        cover_source_assets = None
        if allow_reuse_source_assets and cover_source_adventure_id:
            from backend.models.world_entity import WorldScene, WorldEntity  # noqa: PLC0415
            from backend.models.avatar import Avatar  # noqa: PLC0415

            src_adv = await db.get(AdventureTemplate, cover_source_adventure_id)
            if src_adv:
                src_avatar_res = await db.execute(
                    select(Avatar)
                    .where(Avatar.template_id == cover_source_adventure_id)
                    .order_by(Avatar.created_at.asc(), Avatar.id.asc())
                    .limit(1)
                )
                src_avatar = src_avatar_res.scalars().first()
                src_scene_res = await db.execute(
                    select(WorldScene).where(WorldScene.template_id == cover_source_adventure_id)
                )
                src_scenes = [s for s in src_scene_res.scalars().all() if getattr(s, "session_id", None) is None]
                src_entity_res = await db.execute(
                    select(WorldEntity).where(WorldEntity.template_id == cover_source_adventure_id)
                )
                src_entities = [e for e in src_entity_res.scalars().all() if getattr(e, "session_id", None) is None]
                cover_source_assets = {
                    "cover": src_adv.image_url,
                    "protagonist": {
                        "id": "PROTAGONIST",
                        "name": (src_avatar.name if src_avatar else ""),
                        "image_url": (src_avatar.profile_image if src_avatar else None),
                    },
                    "scenes": [{"id": s.id, "name": s.label, "image_url": s.image_url} for s in src_scenes],
                    "npcs": [{"id": e.id, "name": e.name, "image_url": e.image_url} for e in src_entities if e.entity_type == "NPC"],
                    "objects": [{"id": e.id, "name": e.name, "image_url": e.image_url} for e in src_entities if e.entity_type == "OBJECT"],
                }

        # Post-processing: clamp container and text-log counts
        clamped_max_containers = max(0, min(30, int(max_containers))) if max_containers is not None else 9999
        clamped_max_text_logs = max(0, min(30, int(max_text_logs))) if max_text_logs is not None else 9999

        objects = manifest_dict.get("objects") or []
        container_indices = [
            idx for idx, obj in enumerate(objects)
            if isinstance(obj, dict) and str(obj.get("item_type", "")).upper() == "CONTAINER"
        ]
        if not container_generation_enabled:
            for idx in container_indices:
                obj = objects[idx]
                obj["item_type"] = "PICKABLE"
                obj["inventory"] = []
                obj["code_to_unlock"] = ""
                obj["item_to_unlock"] = ""
                obj["rule_to_unlock"] = ""
        elif len(container_indices) > clamped_max_containers:
            for idx in container_indices[clamped_max_containers:]:
                obj = objects[idx]
                obj["item_type"] = "PICKABLE"
                obj["inventory"] = []
                obj["code_to_unlock"] = ""
                obj["item_to_unlock"] = ""
                obj["rule_to_unlock"] = ""

        for idx in container_indices[:clamped_max_containers]:
            obj = objects[idx]
            code, item, rule = _normalize_unlock_requirements(
                obj.get("code_to_unlock"), obj.get("item_to_unlock"), obj.get("rule_to_unlock")
            )
            obj["code_to_unlock"] = code
            obj["item_to_unlock"] = item
            obj["rule_to_unlock"] = rule

        _ensure_containers_have_minimum_inventory(objects)

        readable_indices = [
            idx for idx, obj in enumerate(objects)
            if isinstance(obj, dict) and str(obj.get("item_type", "")).upper() == "READABLE"
        ]
        if not text_log_generation_enabled:
            for idx in readable_indices:
                obj = objects[idx]
                obj["item_type"] = "PICKABLE"
                obj["text_log_content"] = ""
                obj["text_log_format"] = ""
        else:
            if len(readable_indices) > clamped_max_text_logs:
                for idx in readable_indices[clamped_max_text_logs:]:
                    obj = objects[idx]
                    obj["item_type"] = "PICKABLE"
                    obj["text_log_content"] = ""
                    obj["text_log_format"] = ""
            for idx in readable_indices[:clamped_max_text_logs]:
                obj = objects[idx]
                _obj_meta = obj.get("metadata_json") or {}
                obj["text_log_content"] = _normalize_text_log_content(
                    obj.get("text_log_content") or _obj_meta.get("text_log_content"),
                    obj.get("description"),
                    obj.get("name"),
                )
                text_log_format = str(
                    obj.get("text_log_format") or _obj_meta.get("text_log_format") or "DOCUMENT"
                ).strip().upper()
                if text_log_format not in {"DOCUMENT", "SCROLL", "BOOK", "SIGN"}:
                    text_log_format = "DOCUMENT"
                obj["text_log_format"] = text_log_format

        manifest_dict["cover_source_adventure_id"] = cover_source_adventure_id
        manifest_dict["cover_source_adventure_name"] = cover_source_adventure_name
        manifest_dict["cover_similarity_percent"] = max(0, min(100, int(cover_similarity_percent or 0)))
        manifest_dict["allow_reuse_source_assets"] = bool(allow_reuse_source_assets)

        await apply_manifest(
            db,
            template_id,
            manifest_dict,
            user=user if (generate_npc_images or generate_item_images or generate_scene_images) else None,
            gen_npc=generate_npc_images,
            gen_items=generate_item_images,
            gen_scenes=generate_scene_images,
            gen_protagonist_image=generate_scene_images,
            selected_image_styles=selected_image_styles,
            source_assets=cover_source_assets,
            status_callback=status_callback,
        )

        log_structured_event(
            "adventure.generation.world_applied",
            template_id=template_id,
            scene_count=len(manifesto.scenes),
            exit_count=len(manifesto.exits),
            npc_count=len(manifesto.npcs),
            object_count=len(manifesto.objects),
        )
        await db.flush()

    @staticmethod
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
        """Populate (or re-populate) world entities based on a manifest dictionary.

        Delegates to ``world_manifest_applier.apply_manifest``.
        """
        from backend.engine.world_manifest_applier import apply_manifest  # noqa: PLC0415

        await apply_manifest(
            db=db,
            template_id=template_id,
            manifest_dict=manifest_dict,
            user=user,
            gen_npc=gen_npc,
            gen_items=gen_items,
            gen_scenes=gen_scenes,
            gen_protagonist_image=gen_protagonist_image,
            existing_images=existing_images,
            source_assets=source_assets,
            selected_image_styles=selected_image_styles,
            status_callback=status_callback,
        )


# Convenience alias so module-level attribute access (world_generator.WorldManifesto etc.) works.
preprocess_manifest_object_ids = WorldGenerator.preprocess_manifest_object_ids
