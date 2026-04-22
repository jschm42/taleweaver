import logging
import os
import shutil
import json
import re
import uuid
import zipfile
import io
from copy import deepcopy
from datetime import datetime
from typing import Optional, Dict, Any, List, Literal
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, File, Form, UploadFile, Query
from fastapi.responses import StreamingResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from sqlalchemy.orm.attributes import flag_modified
from pydantic import BaseModel, Field, model_validator
from PIL import Image

from backend.core.database import get_db
from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.models.user import User
from backend.models.adventure import Adventure
from backend.models.avatar import Avatar
from backend.models.game_state import GameState
from backend.models.chat import ChatMessage
from backend.models.world_entity import WorldScene, WorldExit, WorldEntity
from backend.models.world_map import WorldMap
from backend.schemas.adventure import AdventureUpdate, AdventureDebugResponse
from backend.schemas.avatar import AvatarUpdate
from backend.schemas.game_state import GameStateUpdate
from backend.schemas.adventure_import import AdventureImportPayload
from backend.engine.world_generator import WorldGenerator
from backend.engine.command_parser import CommandParser
from backend.engine.rule_engine import RuleEngine, GameEvent, GameOverException, SkillCheckResult
from backend.engine.skill_check import roll_skill_check
from backend.engine.map_engine import MapEngine
from backend.engine.media_engine import MediaEngine
from backend.engine.memory_manager import MemoryManager
from backend.engine.debug_engine import DebugEngine
from backend.core.llm_router import GameMasterLLM
from backend.core import prompts
from backend.core.llm_logger import log_structured_event
from backend.core.adventure_format import FORMAT_NAME, CURRENT_VERSION, validate_manifest_version
from backend.utils.svg_generator import SVGPlaceholderGenerator

router = APIRouter(prefix="/adventures", tags=["Adventures"])
logger = logging.getLogger(__name__)

WALKTHROUGH_REVEAL_COST = 200
WALKTHROUGH_HINT_COST = 50
WALKTHROUGH_ITEM_TOKEN_PATTERN = re.compile(r"\[\[ITEM:([A-Z0-9_]+)\|([^\]]+)\]\]")


def _sanitize_narrative_response(text: str, *, fallback: Optional[str] = None) -> str:
    """Remove leaked technical JSON blocks from player-visible narration."""
    cleaned = (text or "").strip()

    if not cleaned:
        return (fallback or "").strip()

    # If model returned only a raw JSON object, prefer a narrative fallback.
    if cleaned.startswith("{") and cleaned.endswith("}"):
        try:
            json.loads(cleaned)
            return (fallback or "").strip()
        except json.JSONDecodeError:
            pass

    # If model appended structured metadata as a trailing JSON object, strip it.
    json_start = cleaned.rfind("\n{")
    if json_start != -1:
        candidate = cleaned[json_start + 1 :].strip()
        try:
            json.loads(candidate)
            cleaned = cleaned[:json_start].rstrip()
        except json.JSONDecodeError:
            pass

    if not cleaned:
        return (fallback or "").strip()

    return cleaned


def _resolve_start_datetime(manifest: dict[str, Any] | None) -> Optional[str]:
    """Returns a usable ISO datetime string from manifest fields.

    Accepts either explicit `start_datetime` or fallback `start_date` + `start_time`.
    """
    if not manifest:
        return None

    start_datetime = manifest.get("start_datetime")
    if isinstance(start_datetime, str) and start_datetime.strip():
        return start_datetime

    start_date = manifest.get("start_date")
    start_time = manifest.get("start_time")
    if not (isinstance(start_date, str) and start_date.strip() and isinstance(start_time, str) and start_time.strip()):
        return None

    try:
        dt = datetime.fromisoformat(f"{start_date.strip()}T{start_time.strip()}")
        return dt.isoformat()
    except ValueError:
        return None


def _normalize_manifest_for_world_generator(manifest: dict[str, Any] | None) -> Optional[dict[str, Any]]:
    """Normalize ADV import schema to the structure expected by WorldGenerator.apply_manifest."""
    if not isinstance(manifest, dict):
        return None

    raw_scenes = manifest.get("scenes") or []
    if not isinstance(raw_scenes, list) or not raw_scenes:
        return None

    scenes: list[dict[str, Any]] = []
    for idx, scene in enumerate(raw_scenes):
        if not isinstance(scene, dict):
            continue
        scene_id = scene.get("id")
        if not scene_id:
            continue
        scenes.append(
            {
                "id": scene_id,
                "name": scene.get("name") or scene.get("title") or f"Scene {idx + 1}",
                "description": scene.get("description") or "",
                "is_hidden": bool(scene.get("is_hidden", False)),
            }
        )

    if not scenes:
        return None

    default_scene_id = scenes[0]["id"]

    raw_npcs: list[dict[str, Any]] = []
    for key in ("npcs", "characters"):
        values = manifest.get(key) or []
        if isinstance(values, list):
            raw_npcs.extend([v for v in values if isinstance(v, dict)])

    npcs: list[dict[str, Any]] = []
    for npc in raw_npcs:
        npc_id = npc.get("id")
        if not npc_id:
            continue
        npcs.append(
            {
                "id": npc_id,
                "name": npc.get("name") or npc_id,
                "description": npc.get("description") or npc.get("role") or "",
                "start_scene_id": npc.get("start_scene_id") or default_scene_id,
                "spatial_position": npc.get("spatial_position") or "standing nearby",
                "is_hidden": bool(npc.get("is_hidden", False)),
            }
        )

    raw_objects: list[dict[str, Any]] = []
    for key in ("objects", "items"):
        values = manifest.get(key) or []
        if isinstance(values, list):
            raw_objects.extend([v for v in values if isinstance(v, dict)])

    objects: list[dict[str, Any]] = []
    for obj in raw_objects:
        obj_id = obj.get("id")
        if not obj_id:
            continue
        objects.append(
            {
                "id": obj_id,
                "name": obj.get("name") or obj_id,
                "description": obj.get("description") or "",
                "start_scene_id": obj.get("start_scene_id") or default_scene_id,
                "spatial_position": obj.get("spatial_position") or "placed in plain sight",
                "item_type": obj.get("item_type") or obj.get("type") or "PICKABLE",
                "wearable_slots": obj.get("wearable_slots"),
                "is_hidden": bool(obj.get("is_hidden", False)),
            }
        )

    raw_exits = manifest.get("exits") or []
    exits: list[dict[str, Any]] = []
    if isinstance(raw_exits, list):
        for ex in raw_exits:
            if not isinstance(ex, dict):
                continue
            from_scene_id = ex.get("from_scene_id")
            to_scene_id = ex.get("to_scene_id")
            if not from_scene_id or not to_scene_id:
                continue
            exits.append(
                {
                    "from_scene_id": from_scene_id,
                    "to_scene_id": to_scene_id,
                    "label": ex.get("label") or "passage",
                    "is_locked": bool(ex.get("is_locked", False)),
                    "lock_description": ex.get("lock_description"),
                }
            )

    normalized: dict[str, Any] = {
        "scenes": scenes,
        "exits": exits,
        "npcs": npcs,
        "objects": objects,
    }

    prot = manifest.get("protagonist")
    if isinstance(prot, dict):
        normalized["protagonist"] = {
            "name": prot.get("name") or "You",
            "role": prot.get("role") or "Adventurer",
            "description": prot.get("description") or "",
        }

    return normalized


def _validate_import_manifest(payload: dict[str, Any], *, require_format: bool) -> None:
    try:
        validate_manifest_version(payload, require_format=require_format)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _serialize_model(instance: Any) -> dict[str, Any]:
    return {column.name: getattr(instance, column.name) for column in instance.__table__.columns}


def _entity_type_key(entity: WorldEntity) -> str:
    return str(getattr(entity, "entity_type", "") or "").strip().upper()


def _is_npc_entity(entity: WorldEntity) -> bool:
    return _entity_type_key(entity) == "NPC"


def _is_object_entity(entity: WorldEntity) -> bool:
    # Legacy imports may store item-like entities as ITEM instead of OBJECT.
    return _entity_type_key(entity) in {"OBJECT", "ITEM"}


def _compact_text(value: Any, limit: int = 220) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."


def _get_walkthrough_source(adventure: Adventure) -> Optional[dict[str, Any]]:
    manifest = adventure.original_manifest or {}
    if not isinstance(manifest, dict):
        return None
    walkthrough = manifest.get("walkthrough")
    if not isinstance(walkthrough, dict):
        return None
    steps = walkthrough.get("steps")
    if not isinstance(steps, list) or not steps:
        return None
    return walkthrough


def _extract_walkthrough_steps(adventure: Adventure) -> list[dict[str, str]]:
    walkthrough = _get_walkthrough_source(adventure)
    if not walkthrough:
        return []
    result: list[dict[str, str]] = []
    for raw in walkthrough.get("steps", []):
        if not isinstance(raw, dict):
            continue
        title = _compact_text(raw.get("title") or raw.get("step") or "Step")
        content = _compact_text(raw.get("content") or raw.get("hint") or raw.get("description"), 480)
        if not title and not content:
            continue
        result.append({"title": title or "Step", "content": content or "Follow the current objective."})
    return result


def _hint_for_step(step: dict[str, str]) -> str:
    return _compact_text(step.get("content") or step.get("title") or "Keep exploring.", 160)


def _safe_item_label(label: str) -> str:
    """Ensure token labels cannot break token syntax."""
    return (label or "Item").replace("|", "/").replace("]", "").strip() or "Item"


def _tokenize_walkthrough_items(content: str, item_names_by_id: dict[str, str]) -> str:
    """Replace raw item IDs in walkthrough prose with stable ITEM tokens."""
    if not content or not item_names_by_id:
        return content

    tokenized = content

    # Skip IDs that are already present as explicit ITEM tokens.
    existing_ids = {match.group(1).upper() for match in WALKTHROUGH_ITEM_TOKEN_PATTERN.finditer(tokenized)}

    for item_id in sorted(item_names_by_id.keys(), key=len, reverse=True):
        upper_id = item_id.upper()
        if upper_id in existing_ids:
            continue

        label = _safe_item_label(item_names_by_id[item_id])
        token = f"[[ITEM:{upper_id}|{label}]]"
        tokenized = re.sub(rf"\b{re.escape(item_id)}\b", token, tokenized)

    return tokenized


def _walkthrough_fallback_payload(current_xp: int) -> dict[str, Any]:
    message = "No walkthrough available for this adventure yet. Keep exploring and use /hint for tactical nudges when available."
    return {
        "available": False,
        "revealed": False,
        "preview": message,
        "steps": [],
        "hints_used": 0,
        "latest_hint": None,
        "next_hint": None,
        "reveal_cost": WALKTHROUGH_REVEAL_COST,
        "hint_cost": WALKTHROUGH_HINT_COST,
        "current_xp": current_xp,
        "message": message,
    }


def _build_walkthrough_payload(adventure: Adventure, avatar: Avatar) -> dict[str, Any]:
    steps = _extract_walkthrough_steps(adventure)
    if not steps:
        return _walkthrough_fallback_payload(avatar.exp)

    stats = dict(avatar.stats or {})
    revealed = bool(stats.get("walkthrough_revealed", False))
    hints_used = max(0, int(stats.get("walkthrough_hint_index", 0)))

    walkthrough = _get_walkthrough_source(adventure) or {}
    preview = _compact_text(
        walkthrough.get("preview")
        or "A hidden strategy exists. Reveal it when you are ready.",
        260,
    )
    latest_hint = _hint_for_step(steps[min(hints_used - 1, len(steps) - 1)]) if hints_used > 0 else None
    next_hint = _hint_for_step(steps[min(hints_used, len(steps) - 1)]) if hints_used < len(steps) else None

    return {
        "available": True,
        "revealed": revealed,
        "preview": preview,
        "steps": steps if revealed else [],
        "hints_used": hints_used,
        "latest_hint": latest_hint,
        "next_hint": next_hint,
        "reveal_cost": WALKTHROUGH_REVEAL_COST,
        "hint_cost": WALKTHROUGH_HINT_COST,
        "current_xp": avatar.exp,
        "message": "Walkthrough ready." if revealed else "Walkthrough is hidden. Reveal it to unlock all steps.",
    }


async def _seed_compact_walkthrough(db: AsyncSession, adventure_id: str) -> None:
    adventure = await db.get(Adventure, adventure_id)
    if not adventure:
        return

    manifest = adventure.original_manifest if isinstance(adventure.original_manifest, dict) else {}
    existing = manifest.get("walkthrough") if isinstance(manifest, dict) else None
    if isinstance(existing, dict) and isinstance(existing.get("steps"), list) and existing.get("steps"):
        return

    item_res = await db.execute(
        select(WorldEntity)
        .where(WorldEntity.adventure_id == adventure_id)
        .where(func.upper(WorldEntity.entity_type) == "OBJECT")
    )
    item_names_by_id: dict[str, str] = {}
    for item in item_res.scalars().all():
        item_id = (item.id or "").strip().upper()
        if not item_id:
            continue
        item_names_by_id[item_id] = item.name or item_id

    steps: list[dict[str, str]] = []

    quests = adventure.quests or []
    if isinstance(quests, list) and quests:
        ordered_quests = sorted(quests, key=lambda q: 0 if q.get("is_main") else 1)
        for index, quest in enumerate(ordered_quests[:8], start=1):
            if not isinstance(quest, dict):
                continue
            title = _compact_text(quest.get("title") or quest.get("id") or f"Objective {index}", 90)
            goal = _compact_text(quest.get("goal") or quest.get("description") or "Advance this objective.", 220)
            impact = _compact_text(quest.get("impact") or "", 180)
            content = goal if not impact else f"{goal} Outcome target: {impact}"
            content = _tokenize_walkthrough_items(content, item_names_by_id)
            steps.append({"title": title or f"Objective {index}", "content": content or "Advance this objective."})

    if not steps:
        scene_res = await db.execute(
            select(WorldScene).where(WorldScene.adventure_id == adventure_id).order_by(WorldScene.created_at.asc())
        )
        for index, scene in enumerate(scene_res.scalars().all()[:8], start=1):
            title = _compact_text(scene.label or f"Scene {index}", 90)
            content = _compact_text(scene.description or "Explore this location and gather clues.", 260)
            content = _tokenize_walkthrough_items(content, item_names_by_id)
            steps.append({"title": title or f"Scene {index}", "content": content or "Explore this location."})

    if not steps:
        return

    summary_title = _compact_text(adventure.title or "this adventure", 80)
    preview = f"Hidden path for {summary_title}: {steps[0]['title']} -> {steps[min(1, len(steps)-1)]['title']}"

    next_manifest = dict(manifest)
    next_manifest["walkthrough"] = {
        "version": "compact-v2",
        "preview": _compact_text(preview, 240),
        "steps": steps,
    }
    adventure.original_manifest = next_manifest
    await db.flush()


async def _set_generation_state(
    db: AsyncSession,
    adventure_id: str,
    *,
    status: Optional[str] = None,
    is_ready: Optional[bool] = None,
    error: Optional[str] = None,
) -> None:
    adventure = await db.get(Adventure, adventure_id)
    if not adventure:
        return

    if status is not None:
        adventure.creation_status = status
    if is_ready is not None:
        adventure.is_ready = is_ready
    adventure.creation_error = error
    await db.commit()


def _normalize_rule_enforcement_mode(mode: Optional[str]) -> str:
    candidate = (mode or "rpg").strip().lower()
    if candidate in {"rpg", "strict", "strikt"}:
        return "rpg"
    if candidate in {"story", "moderate", "moderat", "narrative"}:
        return "story"
    if candidate in {"chat", "loose", "locker"}:
        return "chat"
    return "rpg"


def _derive_strict_rules(mode: str) -> bool:
    return _normalize_rule_enforcement_mode(mode) in ["rpg", "story"]


def _resolve_catalog_instructions(catalog: Any, selected_ids: list[str]) -> list[str]:
    if not isinstance(catalog, list):
        return []

    selected = {item.strip().lower() for item in selected_ids if item and item.strip()}
    if not selected:
        return []

    instructions: list[str] = []
    for raw in catalog:
        if not isinstance(raw, dict):
            continue
        raw_id = str(raw.get("id") or "").strip().lower()
        raw_name = str(raw.get("name") or "").strip().lower()
        if raw_id not in selected and raw_name not in selected:
            continue
        instruction = str(raw.get("instruction") or "").strip()
        if instruction:
            instructions.append(instruction)
    return instructions


def _resolve_generation_instructions(
    user: Optional[User],
    selected_image_styles: Optional[list[str]],
    selected_tone: Optional[str],
) -> tuple[str, str]:
    styles = [value.strip() for value in (selected_image_styles or []) if isinstance(value, str) and value.strip()]
    tone_value = (selected_tone or "").strip()

    style_parts = _resolve_catalog_instructions(
        getattr(user, "image_styles_catalog", None),
        styles,
    )
    if not style_parts:
        style_parts = styles

    tone_parts = _resolve_catalog_instructions(
        getattr(user, "tone_catalog", None),
        [tone_value] if tone_value else [],
    )
    if not tone_parts and tone_value:
        tone_parts = [tone_value]

    return "; ".join(style_parts), " ".join(tone_parts)


def _build_visual_prompt(
    target_type: str,
    target_data: Dict[str, Any],
    custom_prompt: Optional[str],
    *,
    style_instruction: Optional[str] = None,
    tone_instruction: Optional[str] = None,
) -> str:
    prompt_suffix = ""
    if style_instruction:
        prompt_suffix += f" Style constraints: {style_instruction}."
    if tone_instruction:
        prompt_suffix += f" Narrative tone reference: {tone_instruction}."

    if custom_prompt and custom_prompt.strip():
        return f"{custom_prompt.strip()} {prompt_suffix}".strip()


    if target_type == "protagonist":
        name = target_data.get("name") or "The protagonist"
        role = target_data.get("role") or "adventurer"
        description = target_data.get("description") or "A distinctive fantasy hero."
        return f"Portrait of character {name}, {role}. {description}. Game character art style.{prompt_suffix}"

    if target_type == "scene":
        label = target_data.get("label") or target_data.get("name") or "Scene"
        description = target_data.get("description") or ""
        return f"Atmospheric background: {label}. {description}. RPG visual novel style, high detail.{prompt_suffix}"

    if target_type == "npc":
        name = target_data.get("name") or "NPC"
        description = target_data.get("description") or "A distinctive non-player character."
        return f"Portrait of NPC {name}. {description}. Character portrait, high detail.{prompt_suffix}"

    if target_type == "object":
        name = target_data.get("name") or "Object"
        description = target_data.get("description") or "A detailed fantasy object."
        return f"Detailed illustration of object {name}. {description}. Fantasy item concept art, isolated and clearly readable.{prompt_suffix}"

    if target_type == "cover":
        title = target_data.get("title") or "Adventure"
        context = target_data.get("context") or "A cinematic fantasy journey."
        return f"Epic cinematic adventure cover: {title}. {context}. Landscape format, high fantasy art style, immersive atmosphere, detailed concept art.{prompt_suffix}"

    raise HTTPException(status_code=400, detail="Unsupported visual target type.")


VISUAL_UPLOAD_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
VISUAL_UPLOAD_SPECS: Dict[str, Dict[str, Any]] = {
    "cover": {
        "folder": "",
        "max_width": 2048,
        "max_height": 1024,
        "max_bytes": 4 * 1024 * 1024,
        "recommended": "Optimal: cinematic landscape 2:1, max 2048x1024. PNG, JPEG, or WEBP.",
    },
    "protagonist": {
        "folder": "protagonist",
        "max_width": 1024,
        "max_height": 1280,
        "max_bytes": 2 * 1024 * 1024,
        "recommended": "Optimal: portrait 4:5, max 1024x1280. PNG, JPEG, or WEBP.",
    },
    "scene": {
        "folder": "scenes",
        "max_width": 1600,
        "max_height": 900,
        "max_bytes": 3 * 1024 * 1024,
        "recommended": "Optimal: landscape 16:9, max 1600x900. PNG, JPEG, or WEBP.",
    },
    "npc": {
        "folder": "entities",
        "max_width": 1024,
        "max_height": 1280,
        "max_bytes": 2 * 1024 * 1024,
        "recommended": "Optimal: portrait 4:5, max 1024x1280. PNG, JPEG, or WEBP.",
    },
    "object": {
        "folder": "entities",
        "max_width": 1024,
        "max_height": 1024,
        "max_bytes": 2 * 1024 * 1024,
        "recommended": "Optimal: square 1:1, max 1024x1024. PNG, JPEG, or WEBP.",
    },
}


def _get_visual_upload_spec(target_type: str) -> Dict[str, Any]:
    spec = VISUAL_UPLOAD_SPECS.get(target_type)
    if not spec:
        raise HTTPException(status_code=400, detail="Unsupported visual target type.")
    return spec


def _get_extension(filename: str) -> str:
    return filename.split(".")[-1].lower() if "." in filename else ""


async def _resolve_visual_target(
    db: AsyncSession,
    adventure_id: str,
    target_type: str,
    target_id: str,
) -> tuple[Any, Dict[str, Any], str]:
    if target_type == "cover":
        adventure = await db.get(Adventure, adventure_id)
        if not adventure:
            raise HTTPException(status_code=404, detail="Adventure not found.")
        if target_id != adventure_id:
            raise HTTPException(status_code=400, detail="Invalid cover target id.")
        return adventure, _serialize_model(adventure), "image_url"

    if target_type == "protagonist":
        avatar_res = await db.execute(select(Avatar).where(Avatar.adventure_id == adventure_id, Avatar.id == target_id))
        avatar = avatar_res.scalars().first()
        if not avatar:
            raise HTTPException(status_code=404, detail="Protagonist not found.")
        return avatar, _serialize_model(avatar), "profile_image"

    if target_type == "scene":
        scene_res = await db.execute(select(WorldScene).where(WorldScene.adventure_id == adventure_id, WorldScene.id == target_id))
        scene = scene_res.scalars().first()
        if not scene:
            raise HTTPException(status_code=404, detail="Scene not found.")
        return scene, _serialize_model(scene), "image_url"

    entity_res = await db.execute(select(WorldEntity).where(WorldEntity.adventure_id == adventure_id, WorldEntity.id == target_id))
    entity = entity_res.scalars().first()
    if not entity:
        raise HTTPException(status_code=404, detail="Visual target not found.")

    expected_entity_type = "NPC" if target_type == "npc" else "OBJECT"
    if entity.entity_type != expected_entity_type:
        raise HTTPException(status_code=404, detail="Visual target not found.")

    return entity, _serialize_model(entity), "image_url"


class VisualRegenerateRequest(BaseModel):
    target_type: Literal["cover", "protagonist", "scene", "npc", "object"]
    target_id: str
    prompt: Optional[str] = None


async def _resolve_scene_id(db: AsyncSession, adventure_id: str, scene_ref: Optional[str]) -> Optional[str]:
    """Resolve a scene reference by ID, label, or normalized label slug.

    This guards against LLM outputs that sometimes return scene labels instead of IDs.
    """
    if not scene_ref:
        return None

    candidate = scene_ref.strip()
    if not candidate:
        return None

    by_id = await db.execute(
        select(WorldScene.id).where(
            WorldScene.adventure_id == adventure_id,
            WorldScene.id == candidate,
        )
    )
    resolved = by_id.scalar_one_or_none()
    if resolved:
        return resolved

    normalized_slug = candidate.upper().replace(" ", "_")
    if normalized_slug != candidate:
        by_slug = await db.execute(
            select(WorldScene.id).where(
                WorldScene.adventure_id == adventure_id,
                WorldScene.id == normalized_slug,
            )
        )
        resolved = by_slug.scalar_one_or_none()
        if resolved:
            return resolved

    by_label = await db.execute(
        select(WorldScene.id).where(
            WorldScene.adventure_id == adventure_id,
            func.lower(WorldScene.label) == candidate.lower(),
        )
    )
    return by_label.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------------------------

class CreateAdventurePayload(BaseModel):
    """Payload for creating a new adventure. Backwards-compatible with previous tests (avatar_name optional)."""
    id: Optional[str] = None  # Client-side UUID optional; server will generate if missing
    title: str
    avatar_name: Optional[str] = None
    image_url: Optional[str] = None
    context: Optional[str] = None
    strict_rules: bool = True
    rule_enforcement_mode: Optional[Literal["rpg", "story", "chat"]] = "rpg"
    generate_scene_images: bool = False
    generate_npc_images: bool = False
    generate_item_images: bool = False
    time_per_turn: int = 5
    pacing_minutes: Optional[int] = None
    clock_enabled: Optional[bool] = False
    heartbeat_enabled: Optional[bool] = False
    heartbeat_interval: Optional[int] = None
    game_over_rules: Optional[Dict[str, Any]] = None
    selected_image_styles: Optional[List[str]] = None
    selected_tone: Optional[str] = None
    # Advanced/import fields
    original_manifest: Optional[Dict[str, Any]] = None
    automatic_cover_generation: Optional[bool] = False
    pacing: Optional[Dict[str, Any]] = None
    min_scenes: int = 1
    max_scenes: int = 5

    @model_validator(mode='after')
    def validate_scene_range(self) -> 'CreateAdventurePayload':
        if self.max_scenes < self.min_scenes:
            raise ValueError("max_scenes must be greater than or equal to min_scenes")
        return self


class AdventureResponse(BaseModel):
    """Full adventure details returned to the client."""
    id: str
    title: str
    strict_rules: bool
    rule_enforcement_mode: str
    time_per_turn: int
    pacing_minutes: int
    clock_enabled: bool
    heartbeat_enabled: bool
    heartbeat_interval: Optional[int] = None
    game_over_rules: Optional[Dict[str, Any]]
    selected_image_styles: Optional[List[str]] = None
    selected_tone: Optional[str] = None
    context: Optional[str] = None
    quests: Optional[List[Dict[str, Any]]] = None
    is_completed: bool = False

    model_config = {"from_attributes": True}


class GameSessionResponse(BaseModel):
    """Summary of a game session (GameState + linked entities)."""
    game_id: str
    adventure_id: str
    avatar_id: str
    adventure_title: str
    image_url: Optional[str] = None
    scene_id: str
    current_scene_name: Optional[str] = None
    in_game_time: int
    is_paused: bool
    is_ready: bool = True
    creation_status: Optional[str] = None
    creation_error: Optional[str] = None
    progress: int = 0
    quest_count: int = 0
    completed_quest_count: int = 0

class ChatResponse(BaseModel):
    """Unified response for a game turn."""
    messages: List[Dict[str, str]] # [{'role': '...', 'content': '...'}]
    sheet: Dict[str, Any]
    mermaid: Optional[str] = None
    nodes: Optional[Dict[str, Any]] = None # Metadata for nodes
    image_url: Optional[str] = None
    entities: List[Dict[str, Any]] = []
    npc_metadata: Dict[str, Dict[str, Any]] = {} # { "NPC Name": { ...entity_props } }
    discovered_item_ids: List[str] = []
    game_over: bool = False
    game_over_reason: Optional[str] = None
    adventure_image: Optional[str] = None
    quests: Optional[List[Dict[str, Any]]] = None
    is_completed: bool = False
    full_world: Optional[Dict[str, Any]] = None

class ChatRequest(BaseModel):
    content: str
    auto_visualize: bool = False


# ---------------------------------------------------------------------------
# Adventure CRUD
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
async def create_adventure(
    payload: CreateAdventurePayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if payload.time_per_turn < 1 or payload.time_per_turn > 30:
        raise HTTPException(status_code=400, detail="time_per_turn must be between 1 and 30 minutes.")

    if payload.pacing_minutes is not None and (payload.pacing_minutes < 1 or payload.pacing_minutes > 30):
        raise HTTPException(status_code=400, detail="pacing_minutes must be between 1 and 30 minutes.")

    rule_mode = _normalize_rule_enforcement_mode(payload.rule_enforcement_mode)
    strict_rules = _derive_strict_rules(rule_mode)

    log_structured_event(
        "adventure.create.request",
        title=payload.title,
        user_id=current_user.id,
        strict_rules=strict_rules,
        rule_enforcement_mode=rule_mode,
        time_per_turn=payload.time_per_turn,
        pacing_minutes=payload.pacing_minutes,
        clock_enabled=payload.clock_enabled,
        selected_image_styles=payload.selected_image_styles,
        selected_tone=payload.selected_tone,
        generate_scene_images=payload.generate_scene_images,
        generate_npc_images=payload.generate_npc_images,
        generate_item_images=payload.generate_item_images,
        heartbeat_enabled=payload.heartbeat_enabled,
        has_original_manifest=bool(payload.original_manifest),
    )

    # Create placeholder adventure
    # Allow server-side id generation if client didn't provide one
    adv_kwargs = dict(
        id=payload.id if payload.id else None,
        owner_id=current_user.id,
        title=payload.title,
        image_url=payload.image_url,
        context=payload.context,
        strict_rules=strict_rules,
        rule_enforcement_mode=rule_mode,
        time_per_turn=payload.time_per_turn,
        pacing_minutes=payload.pacing_minutes if payload.pacing_minutes is not None else payload.time_per_turn,
        clock_enabled=bool(payload.clock_enabled),
        game_over_rules=payload.game_over_rules,
        is_ready=False,
        creation_status="Initializing Foundations...",
        heartbeat_enabled=bool(payload.heartbeat_enabled),
        generate_scene_images=payload.generate_scene_images,
        generate_npc_images=payload.generate_npc_images,
        generate_item_images=payload.generate_item_images,
        selected_image_styles=payload.selected_image_styles or [],
        selected_tone=(payload.selected_tone.strip() if payload.selected_tone else None),
        min_scenes=payload.min_scenes,
        max_scenes=payload.max_scenes,
    )

    # Generate placeholder if no image is provided
    if not adv_kwargs.get("image_url"):
        adv_id = adv_kwargs.get("id") or str(uuid.uuid4())
        adv_kwargs["id"] = adv_id
        adv_kwargs["image_url"] = await MediaEngine.generate_svg_placeholder(
            adv_id, payload.title, os.path.join(settings.DATA_DIR, "adventures", adv_id), "cover_placeholder.svg"
        )

    if payload.heartbeat_interval is not None:
        adv_kwargs["heartbeat_interval"] = int(payload.heartbeat_interval)

    adv = Adventure(**adv_kwargs)
    db.add(adv)
    await db.flush()
    # Create a minimal placeholder Avatar which will be populated by WorldGenerator
    avatar_name = payload.avatar_name or "You"
    avatar = Avatar(
        user_id=current_user.id,
        adventure_id=adv.id, # Link early for background tasks
        name=avatar_name,
        hp=200,
        stamina=200,
        mana=200,
        stats={},
        inventory=[],
        equipment={
            "Head": None, "Chest": None, "Arms": None, "Legs": None,
            "Hands": None, "Feet": None, "Ring_1": None, "Ring_2": None, "Amulet": None
        },
        status_effects=[],
    )
    db.add(avatar)
    await db.commit()
    log_structured_event(
        "adventure.create.placeholder_ready",
        adventure_id=adv.id,
        avatar_id=avatar.id,
        user_id=current_user.id,
    )
    # Create initial GameState so the session is visible immediately to clients/tests
    db.add(GameState(
        id=adv.id,
        user_id=current_user.id,
        adventure_id=adv.id,
        avatar_id=avatar.id,
        scene_id="START",
        in_game_time=0
    ))
    await db.commit()
    log_structured_event(
        "adventure.create.session_seeded",
        adventure_id=adv.id,
        game_id=adv.id,
        avatar_id=avatar.id,
    )

    # Store original_manifest if provided and dispatch generation with payload
    if getattr(payload, 'original_manifest', None):
        adv.original_manifest = payload.original_manifest

    await db.commit()

    # Prepare payload for background generation; include original_manifest if present
    bg_payload = payload.model_dump()
    log_structured_event(
        "adventure.generation.scheduled",
        adventure_id=adv.id,
        title=payload.title,
        background_task="run_background_generation",
        has_original_manifest=bool(payload.original_manifest),
    )
    background_tasks.add_task(run_background_generation, adv.id, current_user.id, bg_payload)
    
    # Return IDs expected by existing clients/tests
    return {"game_id": adv.id, "adventure_id": adv.id, "avatar_id": avatar.id}

async def run_background_generation(adventure_id: str, user_id: str, payload_dict: dict):
    """Background task for world gen, scene init, and auto-cleanup on failure."""
    from backend.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            log_structured_event(
                "adventure.generation.started",
                adventure_id=adventure_id,
                user_id=user_id,
                title=payload_dict.get("title"),
                generate_scene_images=payload_dict.get("generate_scene_images", False),
                generate_npc_images=payload_dict.get("generate_npc_images", False),
                generate_item_images=payload_dict.get("generate_item_images", False),
            )
            await _set_generation_state(
                db,
                adventure_id,
                status="Generating world structure",
                is_ready=False,
            )
            # Re-fetch user in this session; if DB schema isn't fully migrated, abort gracefully
            try:
                result = await db.execute(select(User).where(User.id == user_id))
                user = result.scalars().first()
                if not user:
                    raise ValueError(f"User context not found for generation (user_id={user_id}).")
            except Exception as e:
                logger.error("Background Gen user fetch failed for %s: %s", user_id, e)
                await _set_generation_state(
                    db,
                    adventure_id,
                    status="Generation Failed",
                    is_ready=False,
                    error=str(e),
                )
                return

            llm_settings = user.llm_settings or {}
            # Use complex model and its provider for world generation
            complex_model = llm_settings.get("complex_model", "gpt-4o")
            provider = llm_settings.get("complex_model_provider") or llm_settings.get("preferred_provider")
            if not provider:
                raise ValueError(
                    "No complex LLM provider configured for this user. "
                    "Open Settings -> LLM and set Complex Model Provider."
                )
            adv_for_context = await db.get(Adventure, adventure_id)
            if not adv_for_context:
                fallback_rule_mode = _normalize_rule_enforcement_mode(payload_dict.get("rule_enforcement_mode"))
                adv_for_context = Adventure(
                    id=adventure_id,
                    title=payload_dict.get("title") or "Adventure",
                    context=payload_dict.get("context"),
                    strict_rules=_derive_strict_rules(fallback_rule_mode),
                    rule_enforcement_mode=fallback_rule_mode,
                    time_per_turn=int(payload_dict.get("time_per_turn") or 5),
                    pacing_minutes=int(payload_dict.get("pacing_minutes") or payload_dict.get("time_per_turn") or 5),
                    clock_enabled=bool(payload_dict.get("clock_enabled")),
                    heartbeat_enabled=False,
                    generate_scene_images=bool(payload_dict.get("generate_scene_images", False)),
                    generate_npc_images=bool(payload_dict.get("generate_npc_images", False)),
                    generate_item_images=bool(payload_dict.get("generate_item_images", False)),
                    selected_image_styles=payload_dict.get("selected_image_styles") or [],
                    selected_tone=payload_dict.get("selected_tone"),
                    is_ready=False,
                    creation_status="Generating world structure",
                )
                db.add(adv_for_context)
                await db.commit()

            style_instruction, tone_instruction = _resolve_generation_instructions(
                user,
                adv_for_context.selected_image_styles if adv_for_context else None,
                adv_for_context.selected_tone if adv_for_context else None,
            )
            source_manifest = (adv_for_context.original_manifest if adv_for_context else None) or payload_dict.get("original_manifest")
            normalized_manifest = _normalize_manifest_for_world_generator(source_manifest)
            initial_scene_id = normalized_manifest["scenes"][0]["id"] if normalized_manifest else None
            
            # 1. World Gen
            adventure_context = payload_dict.get('context')
            if not adventure_context:
                manifest = (adv_for_context.original_manifest or {}) if adv_for_context else {}
                adventure_context = manifest.get('story_idea') or manifest.get('description') or "A standard fantasy world."

            if tone_instruction:
                adventure_context = f"{adventure_context}\n\nTone Guidance: {tone_instruction}"

            log_structured_event(
                "adventure.generation.status",
                adventure_id=adventure_id,
                status="Generating world structure",
                phase="world_generation",
            )

            if normalized_manifest:
                await _set_generation_state(
                    db,
                    adventure_id,
                    status="Applying Imported Manifest...",
                    is_ready=False,
                )
                log_structured_event(
                    "adventure.generation.status",
                    adventure_id=adventure_id,
                    status="Applying Imported Manifest...",
                    phase="apply_manifest",
                )

                await WorldGenerator.apply_manifest(
                    db=db,
                    adventure_id=adventure_id,
                    manifest_dict=normalized_manifest,
                    user=user if (payload_dict.get('generate_npc_images', False) or payload_dict.get('generate_item_images', False) or payload_dict.get('generate_scene_images', False)) else None,
                    gen_npc=payload_dict.get('generate_npc_images', False),
                    gen_items=payload_dict.get('generate_item_images', False),
                    gen_scenes=payload_dict.get('generate_scene_images', False),
                    gen_protagonist_image=True,
                )
            else:
                await WorldGenerator.generate_world(
                    db,
                    user,
                    adventure_id,
                    title=payload_dict['title'],
                    context=adventure_context,
                    model=complex_model,
                    provider=provider,
                    generate_scene_images=payload_dict.get('generate_scene_images', False),
                    generate_npc_images=payload_dict.get('generate_npc_images', False),
                    generate_item_images=payload_dict.get('generate_item_images', False),
                    min_scenes=payload_dict.get('min_scenes', 1),
                    max_scenes=payload_dict.get('max_scenes', 5)
                )
            
            # 2. Initial GameState
            scenes_res = await db.execute(select(WorldScene).where(WorldScene.adventure_id == adventure_id))
            scenes = scenes_res.scalars().all()
            if not scenes: raise ValueError("Engine failed to sprout any locations.")
            
            # Get Avatar ID
            avatar_res = await db.execute(select(Avatar).where(Avatar.adventure_id == adventure_id))
            avatar = avatar_res.scalars().first()
            if not avatar:
                avatar = Avatar(
                    user_id=user.id,
                    adventure_id=adventure_id,
                    name="You",
                    hp=200,
                    stamina=200,
                    mana=200,
                    stats={},
                    inventory=[],
                    equipment={
                        "Head": None,
                        "Chest": None,
                        "Arms": None,
                        "Legs": None,
                        "Hands": None,
                        "Feet": None,
                        "Ring_1": None,
                        "Ring_2": None,
                        "Amulet": None,
                    },
                    status_effects=[],
                )
                db.add(avatar)
                await db.commit()
            
            # create_adventure already seeds a GameState; update it instead of inserting a duplicate
            state_res = await db.execute(select(GameState).where(GameState.adventure_id == adventure_id))
            state = state_res.scalars().first()
            resolved_initial_scene_id = initial_scene_id if initial_scene_id and any(s.id == initial_scene_id for s in scenes) else scenes[0].id
            if state:
                state.avatar_id = avatar.id if avatar else state.avatar_id
                state.scene_id = resolved_initial_scene_id
            else:
                db.add(GameState(
                    id=adventure_id,
                    user_id=user_id,
                    adventure_id=adventure_id,
                    avatar_id=avatar.id if avatar else None,
                    scene_id=resolved_initial_scene_id,
                    in_game_time=0
                ))
            
            # 2.5 Generate Cinematic Cover if requested
            if payload_dict.get('automatic_cover_generation'):
                await _set_generation_state(
                    db,
                    adventure_id,
                    status="Generating Cinematic Cover...",
                    is_ready=False,
                )
                try:
                    cover_context = adventure_context
                    if style_instruction:
                        cover_context = f"{cover_context}\nVisual Style Guidance: {style_instruction}"
                    cover_url = await MediaEngine.generate_adventure_cover(
                        title=adv_for_context.title,
                        context=cover_context,
                        adventure_id=adventure_id,
                        user_config={"t2i_settings": user.t2i_settings},
                        api_keys=user.encrypted_api_keys
                    )
                    if cover_url:
                        adv_for_context.image_url = cover_url
                        await db.commit()
                    else:
                        # Fallback to procedural SVG if cinematic cover fails
                        adv_for_context.image_url = await MediaEngine.generate_svg_placeholder(
                            adventure_id, adv_for_context.title, os.path.join(settings.DATA_DIR, "adventures", adventure_id), "cover_placeholder.svg"
                        )
                        await db.commit()
                except Exception as e:
                    logger.error(f"Cover generation failed: {e}")
                    # Fallback to procedural SVG
                    adv_for_context.image_url = await MediaEngine.generate_svg_placeholder(
                        adventure_id, adv_for_context.title, os.path.join(settings.DATA_DIR, "adventures", adventure_id), "cover_placeholder.svg"
                    )
                    await db.commit()

            # 3. Mark Ready
            await _seed_compact_walkthrough(db, adventure_id)
            await _set_generation_state(
                db,
                adventure_id,
                status="Ready",
                is_ready=True,
                error=None,
            )
            log_structured_event(
                "adventure.generation.completed",
                adventure_id=adventure_id,
                scene_count=len(scenes),
                avatar_id=avatar.id if avatar else None,
            )
        except Exception as e:
            logger.exception("Background Gen Failed for %s", adventure_id)
            error_msg = str(e)
            lowered_error = error_msg.lower()

            if "truncated (token limit)" in lowered_error or "token limit" in lowered_error:
                error_msg = "Generation failed: LLM output was truncated. Increase Complex Max Tokens in Admin settings and retry."
            elif "failed to parse llm response as json" in lowered_error:
                error_msg = "Generation failed: LLM returned invalid JSON for world generation. Please retry."

            if len(error_msg) > 500:
                error_msg = error_msg[:497] + "..."
            # Remove potential JSON fragments or long traces
            if "{" in error_msg and "}" in error_msg:
                error_msg = "Validation failed or invalid model response format."

            log_structured_event(
                "adventure.generation.failed",
                adventure_id=adventure_id,
                error=error_msg,
            )
            try:
                await db.rollback()
                # Do not auto-delete adventures during background failures in tests.
                await _set_generation_state(
                    db,
                    adventure_id,
                    status="Generation Failed",
                    is_ready=False,
                    error=error_msg,
                )
            except Exception:
                pass


@router.get("/{game_id}/walkthrough")
async def get_walkthrough_state(
    game_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    state_res = await db.execute(select(GameState).where(GameState.id == game_id))
    state = state_res.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")

    adv_res = await db.execute(
        select(Adventure).where(
            (Adventure.id == state.adventure_id)
            & (Adventure.owner_id == current_user.id)
        )
    )
    adventure = adv_res.scalars().first()
    if not adventure:
        raise HTTPException(status_code=404, detail="Session not found.")

    if state.user_id != current_user.id:
        state.user_id = current_user.id

    av_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
    avatar = av_res.scalars().first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found.")

    payload = _build_walkthrough_payload(adventure, avatar)
    await db.commit()
    return payload

@router.get("/{game_id}/status")
async def get_adventure_status(game_id: str, db: AsyncSession = Depends(get_db)):
    adv = await db.get(Adventure, game_id)
    if not adv:
        raise HTTPException(status_code=404, detail="Adventure cleaned up due to failure")
    return {
        "is_ready": adv.is_ready,
        "status": adv.creation_status,
        "error": adv.creation_error
    }


def _calculate_quest_progress(quests: Optional[List[Dict[str, Any]]]) -> int:
    if not quests:
        return 0
    total = len(quests)
    if total == 0:
        return 0
    completed = len([q for q in quests if q.get("status") == "completed"])
    return int((completed / total) * 100)


@router.get("", response_model=List[GameSessionResponse])
async def list_adventures(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list:
    """Returns all game sessions for the current user."""
    result = await db.execute(
        select(GameState, Adventure, WorldScene.label)
        .join(Adventure, GameState.adventure_id == Adventure.id)
        .outerjoin(
            WorldScene,
            (WorldScene.adventure_id == GameState.adventure_id) & (WorldScene.id == GameState.scene_id),
        )
        .where(
            (Adventure.owner_id == current_user.id) & 
            (GameState.user_id == current_user.id)
        )
    )
    rows = result.all()
    return [
        GameSessionResponse(
            game_id=s.id,
            adventure_id=s.adventure_id,
            avatar_id=s.avatar_id,
            adventure_title=a.title,
            image_url=a.image_url,
            scene_id=s.scene_id,
            current_scene_name=scene_label or "Unknown",
            in_game_time=s.in_game_time,
            is_paused=s.is_paused,
            is_ready=a.is_ready,
            creation_status=a.creation_status,
            creation_error=a.creation_error,
            progress=_calculate_quest_progress(a.quests),
            quest_count=len(a.quests or []),
            completed_quest_count=len([q for q in (a.quests or []) if q.get("status") == "completed"]),
        )
        for s, a, scene_label in rows
    ]


@router.get("/{adventure_id}", response_model=AdventureResponse)
async def get_adventure(
    adventure_id: str, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Adventure:
    """Returns the details of a single adventure by its ID."""
    result = await db.execute(
        select(Adventure).where(
            (Adventure.id == adventure_id) & 
            (Adventure.owner_id == current_user.id)
        )
    )
    adv = result.scalars().first()
    if not adv:
        raise HTTPException(status_code=404, detail="Adventure not found.")
    return adv


@router.post("/import", status_code=201)
async def import_adventure(
    payload: AdventureImportPayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Import an adventure manifest (versioned .ADV JSON). Opens an adventure scaffold and starts background generation."""
    _validate_import_manifest(payload.model_dump(), require_format=True)

    import_rule_mode = _normalize_rule_enforcement_mode(payload.rule_enforcement_mode)
    import_strict_rules = _derive_strict_rules(import_rule_mode)
    selected_image_styles = payload.image_styles or ([payload.image_style] if payload.image_style else [])

    adv_kwargs = dict(
        owner_id=current_user.id,
        title=payload.title,
        image_url=None,
        context=payload.story_idea or payload.description or payload.subtitle,
        strict_rules=import_strict_rules,
        rule_enforcement_mode=import_rule_mode,
        time_per_turn=payload.time_per_turn or 5,
        pacing_minutes=payload.pacing_minutes or payload.time_per_turn or 5,
        clock_enabled=bool(payload.clock_enabled),
        game_over_rules=None,
        is_ready=False,
        creation_status="Importing Manifest...",
        heartbeat_enabled=False,
        selected_image_styles=selected_image_styles,
        selected_tone=payload.tone,
        original_manifest=payload.model_dump(),
        min_scenes=payload.min_scenes,
        max_scenes=payload.max_scenes,
    )

    adv = Adventure(**adv_kwargs)
    db.add(adv)
    await db.flush()

    # Generate placeholder for imported adventure if no image is provided
    if not adv.image_url:
        adv.image_url = await MediaEngine.generate_svg_placeholder(
            adv.id, adv.title, os.path.join(settings.DATA_DIR, "adventures", adv.id), "cover_placeholder.svg"
        )
        await db.flush()

    avatar_name = None
    if payload.protagonist and payload.protagonist.name:
        avatar_name = payload.protagonist.name
    avatar_name = avatar_name or "You"

    avatar = Avatar(
        user_id=current_user.id,
        adventure_id=adv.id,
        name=avatar_name,
        role=(payload.protagonist.role if payload.protagonist else None),
        description=(payload.protagonist.description if payload.protagonist else None),
        hp=200,
        stamina=200,
        mana=200,
        stats={},
        inventory=[],
        equipment={
            "Head": None, "Chest": None, "Arms": None, "Legs": None,
            "Hands": None, "Feet": None, "Ring_1": None, "Ring_2": None, "Amulet": None
        },
        status_effects=[],
    )
    db.add(avatar)
    await db.commit()

    db.add(GameState(
        id=adv.id,
        user_id=current_user.id,
        adventure_id=adv.id,
        avatar_id=avatar.id,
        scene_id="START",
        in_game_time=0
    ))
    await db.commit()

    # Prepare minimal payload for background gen; world generator will read original_manifest from DB if needed
    payload_dict = {
        "title": payload.title,
        "context": adv.context or "A standard adventure.",
        "time_per_turn": payload.time_per_turn or adv.time_per_turn,
        "generate_npc_images": payload.generate_npc_images,
        "generate_item_images": payload.generate_item_images,
        "automatic_cover_generation": payload.automatic_cover_generation,
        "min_scenes": payload.min_scenes,
        "max_scenes": payload.max_scenes,
        "selected_image_styles": selected_image_styles,
        "selected_tone": payload.tone,
        "rule_enforcement_mode": import_rule_mode,
        "clock_enabled": bool(payload.clock_enabled),
        "pacing_minutes": payload.pacing_minutes or payload.time_per_turn,
        "pacing": payload.pacing.model_dump() if payload.pacing else None,
        "start_date": payload.start_date,
        "start_time": payload.start_time,
        "start_datetime": payload.start_datetime,
        "original_manifest": payload.model_dump(),
    }

    background_tasks.add_task(run_background_generation, adv.id, current_user.id, payload_dict)

    return {"game_id": adv.id, "adventure_id": adv.id, "avatar_id": avatar.id}


@router.patch("/{adventure_id}", response_model=AdventureResponse)
async def update_adventure(
    adventure_id: str,
    payload: AdventureUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Adventure:
    """
    Partially updates an adventure's configuration (title, rules, heartbeat settings).
    Only provided fields are updated.
    """
    result = await db.execute(
        select(Adventure).where(
            (Adventure.id == adventure_id) & 
            (Adventure.owner_id == current_user.id)
        )
    )
    adv = result.scalars().first()
    if not adv:
        raise HTTPException(status_code=404, detail="Adventure not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(adv, field, value)

    await db.commit()
    await db.refresh(adv)
    logger.info("Updated adventure %s for user %s: %s", adventure_id, current_user.id, update_data)
    return adv


@router.delete("/{adventure_id}", status_code=204)
async def delete_adventure(
    adventure_id: str, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Deletes an adventure and its associated game state.
    Returns 204 No Content on success.
    """
    result = await db.execute(
        select(Adventure).where(
            (Adventure.id == adventure_id) & 
            (Adventure.owner_id == current_user.id)
        )
    )
    adv = result.scalars().first()
    if not adv:
        raise HTTPException(status_code=404, detail="Adventure not found.")

    # Remove linked game states first to avoid FK constraint violations
    gs_result = await db.execute(
        select(GameState).where(GameState.adventure_id == adventure_id)
    )
    for gs in gs_result.scalars().all():
        await db.delete(gs)

    await db.delete(adv)
    await db.commit()
    
    # 3. Clean up physical assets
    adventure_assets_path = os.path.join(settings.DATA_DIR, "adventures", adventure_id)
    if os.path.exists(adventure_assets_path):
        try:
            shutil.rmtree(adventure_assets_path)
            logger.info("Deleted assets directory for adventure %s", adventure_id)
        except Exception as e:
            logger.error("Failed to delete assets for adventure %s: %s", adventure_id, e)

    logger.info("Deleted adventure %s", adventure_id)


# ---------------------------------------------------------------------------
# Game-State sub-routes
# ---------------------------------------------------------------------------

@router.get("/{adventure_id}/state", response_model=GameSessionResponse)
async def get_game_state(
    adventure_id: str, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GameSessionResponse:
    """Returns the current game state for a given adventure."""
    result = await db.execute(
        select(GameState).where(
            (GameState.adventure_id == adventure_id) & 
            (GameState.user_id == current_user.id)
        )
    )
    state = result.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="Game state not found.")
    # Fetch linked adventure and scene label for display metadata
    adv = await db.get(Adventure, state.adventure_id)
    scene_res = await db.execute(
        select(WorldScene.label).where(
            WorldScene.adventure_id == state.adventure_id,
            WorldScene.id == state.scene_id,
        )
    )
    scene_label = scene_res.scalar_one_or_none()
    return GameSessionResponse(
        game_id=state.id,
        adventure_id=state.adventure_id,
        avatar_id=state.avatar_id,
        adventure_title=adv.title if adv else "",
        image_url=adv.image_url if adv else None,
        scene_id=state.scene_id,
        current_scene_name=scene_label or "Unknown",
        in_game_time=state.in_game_time,
        is_paused=state.is_paused,
        is_ready=adv.is_ready if adv else True,
        creation_status=adv.creation_status if adv else None,
        creation_error=adv.creation_error if adv else None,
        progress=_calculate_quest_progress(adv.quests if adv else None)
    )


@router.patch("/{adventure_id}/state")
async def update_game_state(
    adventure_id: str,
    payload: GameStateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Updates scene_id or in_game_time for the active game state of an adventure."""
    result = await db.execute(
        select(GameState).where(
            (GameState.adventure_id == adventure_id) & 
            (GameState.user_id == current_user.id)
        )
    )
    state = result.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="Game state not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(state, field, value)

    await db.commit()
    return {"status": "updated", "game_id": state.id}


@router.post("/{adventure_id}/pause")
async def pause_game(
    adventure_id: str, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Pauses the heartbeat processing for a game session."""
    result = await db.execute(
        select(GameState).where(
            (GameState.adventure_id == adventure_id) & 
            (GameState.user_id == current_user.id)
        )
    )
    state = result.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="Game state not found.")
    state.is_paused = True
    await db.commit()
    return {"status": "paused", "game_id": state.id}


@router.post("/{adventure_id}/resume")
async def resume_game(
    adventure_id: str, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Resumes heartbeat processing for a paused game session."""
    result = await db.execute(
        select(GameState).where(
            (GameState.adventure_id == adventure_id) & 
            (GameState.user_id == current_user.id)
        )
    )
    state = result.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="Game state not found.")
    state.is_paused = False
    await db.commit()
    return {"status": "resumed", "game_id": state.id}

async def _build_adventure_editor_assets(adventure_id: str, db: AsyncSession) -> AdventureDebugResponse:
    """Builds full world/editor asset state for a specific adventure."""
    adv_res = await db.execute(select(Adventure).where(Adventure.id == adventure_id))
    adventure = adv_res.scalars().first()
    if not adventure:
        raise HTTPException(status_code=404, detail="Adventure not found")
        
    scene_res = await db.execute(select(WorldScene).where(WorldScene.adventure_id == adventure_id))
    scenes = scene_res.scalars().all()
    
    exit_res = await db.execute(select(WorldExit).where(WorldExit.adventure_id == adventure_id))
    exits = exit_res.scalars().all()
    
    entity_res = await db.execute(select(WorldEntity).where(WorldEntity.adventure_id == adventure_id))
    entities = entity_res.scalars().all()

    avatar_res = await db.execute(select(Avatar).where(Avatar.adventure_id == adventure_id))
    avatar = avatar_res.scalars().first()

    db_scenes = [_serialize_model(s) for s in scenes]
    db_npcs = [_serialize_model(ent) for ent in entities if _is_npc_entity(ent)]
    db_objects = [_serialize_model(ent) for ent in entities if _is_object_entity(ent)]
    db_exits = [_serialize_model(ex) for ex in exits]

    # Fallback: if DB world tables are empty/partial, hydrate debug payload from original manifest.
    manifest_world = _normalize_manifest_for_world_generator(adventure.original_manifest)
    if manifest_world:
        scene_by_id = {str(scene.get("id")): scene for scene in db_scenes if scene.get("id")}
        for scene in manifest_world.get("scenes", []):
            scene_id = str(scene.get("id") or "")
            if not scene_id or scene_id in scene_by_id:
                continue
            db_scenes.append(
                {
                    "id": scene_id,
                    "adventure_id": adventure_id,
                    "label": scene.get("name") or scene_id,
                    "description": scene.get("description") or "",
                    "image_url": scene.get("image_url"),
                }
            )

        npc_by_id = {str(npc.get("id")): npc for npc in db_npcs if npc.get("id")}
        for npc in manifest_world.get("npcs", []):
            npc_id = str(npc.get("id") or "")
            if not npc_id or npc_id in npc_by_id:
                continue
            db_npcs.append(
                {
                    "id": npc_id,
                    "adventure_id": adventure_id,
                    "entity_type": "NPC",
                    "name": npc.get("name") or npc_id,
                    "description": npc.get("description") or "",
                    "current_scene_id": npc.get("start_scene_id"),
                    "spatial_position": npc.get("spatial_position"),
                    "image_url": npc.get("image_url"),
                    "is_hidden": bool(npc.get("is_hidden", False)),
                    "is_in_inventory": bool(npc.get("is_in_inventory", False)),
                }
            )

        object_by_id = {str(obj.get("id")): obj for obj in db_objects if obj.get("id")}
        for obj in manifest_world.get("objects", []):
            obj_id = str(obj.get("id") or "")
            if not obj_id or obj_id in object_by_id:
                continue
            db_objects.append(
                {
                    "id": obj_id,
                    "adventure_id": adventure_id,
                    "entity_type": "OBJECT",
                    "name": obj.get("name") or obj_id,
                    "description": obj.get("description") or "",
                    "current_scene_id": obj.get("start_scene_id"),
                    "spatial_position": obj.get("spatial_position"),
                    "item_type": obj.get("item_type"),
                    "wearable_slots": obj.get("wearable_slots"),
                    "image_url": obj.get("image_url"),
                    "is_hidden": bool(obj.get("is_hidden", False)),
                    "is_in_inventory": bool(obj.get("is_in_inventory", False)),
                }
            )

        exit_keys = {
            (str(ex.get("from_scene_id") or ""), str(ex.get("to_scene_id") or ""), str(ex.get("label") or ""))
            for ex in db_exits
        }
        for ex in manifest_world.get("exits", []):
            key = (str(ex.get("from_scene_id") or ""), str(ex.get("to_scene_id") or ""), str(ex.get("label") or ""))
            if not key[0] or not key[1] or key in exit_keys:
                continue
            db_exits.append(
                {
                    "id": str(uuid.uuid4()),
                    "adventure_id": adventure_id,
                    "from_scene_id": ex.get("from_scene_id"),
                    "to_scene_id": ex.get("to_scene_id"),
                    "label": ex.get("label") or "passage",
                    "is_locked": bool(ex.get("is_locked", False)),
                    "lock_description": ex.get("lock_description"),
                }
            )
    
    return AdventureDebugResponse(
        adventure=_serialize_model(adventure),
        protagonist=_serialize_model(avatar) if avatar else None,
        scenes=db_scenes,
        npcs=db_npcs,
        objects=db_objects,
        exits=db_exits,
        entities_all=[_serialize_model(ent) for ent in entities] + db_npcs + db_objects,
    )


@router.get("/{adventure_id}/editor/assets", response_model=AdventureDebugResponse)
async def get_adventure_editor_assets(adventure_id: str, db: AsyncSession = Depends(get_db)):
    """Returns full world/editor asset data for the Adventure Editor UI."""
    return await _build_adventure_editor_assets(adventure_id, db)


@router.get("/{adventure_id}/debug", response_model=AdventureDebugResponse)
async def get_adventure_debug(adventure_id: str, db: AsyncSession = Depends(get_db)):
    """Legacy debug endpoint. Prefer /editor/assets for editor consumption."""
    return await _build_adventure_editor_assets(adventure_id, db)


class EntityUpdateRequest(BaseModel):
    target_type: Literal["cover", "scene", "npc", "object", "protagonist"]
    target_id: str
    name: Optional[str] = None
    description: Optional[str] = None

class AIEditRequest(BaseModel):
    prompt: str
    auto_visualize: bool = True

@router.patch("/{adventure_id}/editor/entity")
async def update_editor_entity(
    adventure_id: str,
    payload: EntityUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    adv = await db.get(Adventure, adventure_id)
    if not adv or adv.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Adventure not found")
        
    if payload.target_type == "cover":
        if payload.name is not None:
            adv.title = payload.name
        if payload.description is not None:
            adv.context = payload.description
    elif payload.target_type == "protagonist":
        av_res = await db.execute(select(Avatar).where(Avatar.adventure_id == adventure_id))
        avatar = av_res.scalars().first()
        if not avatar:
            raise HTTPException(status_code=404, detail="Protagonist not found")
        if payload.name is not None:
            avatar.name = payload.name
        if payload.description is not None:
            avatar.description = payload.description
    elif payload.target_type == "scene":
        sc_res = await db.execute(select(WorldScene).where(WorldScene.adventure_id == adventure_id, WorldScene.id == payload.target_id))
        scene = sc_res.scalars().first()
        if not scene:
            raise HTTPException(status_code=404, detail="Scene not found")
        if payload.name is not None:
            scene.label = payload.name
        if payload.description is not None:
            scene.description = payload.description
    else:
        en_res = await db.execute(select(WorldEntity).where(WorldEntity.adventure_id == adventure_id, WorldEntity.id == payload.target_id))
        ent = en_res.scalars().first()
        if not ent:
            raise HTTPException(status_code=404, detail="Entity not found")
        if payload.name is not None:
            ent.name = payload.name
        if payload.description is not None:
            ent.description = payload.description
            
    await db.commit()
    return {"status": "success"}

@router.post("/{adventure_id}/editor/ai-edit")
async def ai_edit_adventure(
    adventure_id: str,
    payload: AIEditRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    state_res = await db.execute(
        select(GameState).where(
            (GameState.adventure_id == adventure_id) & 
            (GameState.user_id == current_user.id)
        )
    )
    state = state_res.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="Game state not found")
        
    user = current_user
        
    adv = await db.get(Adventure, adventure_id)
    if not adv or adv.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Adventure not found")
        
    scene_res = await db.execute(select(WorldScene).where(WorldScene.adventure_id == adventure_id))
    scenes = scene_res.scalars().all()
    
    exit_res = await db.execute(select(WorldExit).where(WorldExit.adventure_id == adventure_id))
    exits = exit_res.scalars().all()
    
    entity_res = await db.execute(select(WorldEntity).where(WorldEntity.adventure_id == adventure_id))
    entities = entity_res.scalars().all()

    avatar_res = await db.execute(select(Avatar).where(Avatar.adventure_id == adventure_id))
    avatar = avatar_res.scalars().first()

    manifest_dict = {
        "protagonist": {
            "name": avatar.name if avatar else "You",
            "role": avatar.role if avatar else "Adventurer",
            "description": avatar.description if avatar else ""
        },
        "scenes": [{"id": s.id, "name": s.label, "description": s.description} for s in scenes],
        "npcs": [{"id": n.id, "name": n.name, "description": n.description, "type": "NPC", "start_scene_id": n.current_scene_id, "spatial_position": n.spatial_position or "nearby"} for n in entities if n.entity_type == "NPC"],
        "objects": [{"id": o.id, "name": o.name, "description": o.description, "type": "OBJECT", "start_scene_id": o.current_scene_id, "spatial_position": o.spatial_position or "nearby", "item_type": o.item_type} for o in entities if o.entity_type == "OBJECT"],
        "exits": [{"from_scene_id": e.from_scene_id, "to_scene_id": e.to_scene_id, "label": e.label, "is_locked": e.is_locked, "lock_description": e.lock_description} for e in exits],
        "quests": adv.quests or []
    }
    
    from backend.engine.world_generator import WorldManifesto
    
    llm_settings = user.llm_settings or {}
    provider = (
        llm_settings.get("complex_model_provider")
        or llm_settings.get("small_model_provider")
        or llm_settings.get("preferred_provider")
    )
    if not provider:
        raise HTTPException(
            status_code=400,
            detail="No complex LLM provider configured for this user. Open Settings -> LLM and set Complex Model Provider.",
        )
    model = llm_settings.get("complex_model", "gpt-4o")
    llm = GameMasterLLM(user, provider=provider)
    
    system_prompt = (
        "You are the AI Architect for TaleWeaver. Your task is to update the JSON world manifesto based on the user's instructions.\n"
        "1. If the user wants to add new NPCs, Items, or Scenes, you MUST generate a UNIQUE ID (slug) for them (e.g., 'NPC_MYSTERIOUS_STRANGER').\n"
        "2. Ensure all new entities have a 'start_scene_id' that matches one of the existing or newly created scene IDs.\n"
        "3. You must return the COMPLETE WorldManifesto JSON object.\n"
        "4. Do not remove existing entities unless explicitly asked.\n"
        "5. Maintain valid JSON structure at all times."
    )
    user_prompt = f"Current World Manifesto:\n```json\n{json.dumps(manifest_dict, indent=2)}\n```\n\nUser Change Request: {payload.prompt}\n\nOutput the updated JSON Manifesto now."

    
    try:
        new_manifesto: WorldManifesto = llm.execute_complex_task(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=WorldManifesto,
            model=model,
            adventure_id=adventure_id,
            operation="ai_edit_world",
            phase="edit"
        )
    except Exception as e:
        logger.error(f"AI Edit failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI Edit failed: {str(e)}")
        
    await WorldGenerator.apply_manifest(
        db=db,
        adventure_id=adventure_id,
        manifest_dict=new_manifesto.model_dump(),
        user=user,
        gen_npc=payload.auto_visualize,
        gen_items=payload.auto_visualize,
        gen_scenes=payload.auto_visualize,
        gen_protagonist_image=False
    )
    
    await db.commit()
    return {"status": "success"}


@router.post("/{adventure_id}/visuals/regenerate")
async def regenerate_visual(
    adventure_id: str,
    payload: VisualRegenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Regenerates a cover, scene, NPC, object, or protagonist portrait for an adventure."""
    state_res = await db.execute(select(GameState).where(GameState.adventure_id == adventure_id))
    state = state_res.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="Game state not found.")

    user = await db.get(User, state.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    adv = await db.get(Adventure, adventure_id)
    style_instruction, tone_instruction = _resolve_generation_instructions(
        user,
        adv.selected_image_styles if adv else None,
        adv.selected_tone if adv else None,
    )

    target_model, target_data, image_attr = await _resolve_visual_target(
        db=db,
        adventure_id=adventure_id,
        target_type=payload.target_type,
        target_id=payload.target_id,
    )

    image_url: Optional[str] = None
    import litellm

    try:
        if payload.target_type == "cover":
            cover_context = payload.prompt.strip() if payload.prompt and payload.prompt.strip() else (target_data.get("context") or "")
            if style_instruction:
                cover_context = f"{cover_context}\nVisual Style Guidance: {style_instruction}"
            if tone_instruction:
                cover_context = f"{cover_context}\nTone Guidance: {tone_instruction}"
            image_url = await MediaEngine.generate_adventure_cover(
                title=target_data.get("title") or "Adventure",
                context=cover_context,
                adventure_id=adventure_id,
                user_config={"t2i_settings": user.t2i_settings},
                api_keys=user.encrypted_api_keys or {},
            )
            if not image_url:
                raise HTTPException(status_code=504, detail="Cover image generation timed out or failed.")
        elif payload.target_type == "protagonist":
            prompt = _build_visual_prompt(
                payload.target_type,
                target_data,
                payload.prompt,
                style_instruction=style_instruction,
                tone_instruction=tone_instruction,
            )
            image_url = await MediaEngine.generate_entity_image(
                prompt,
                adventure_id,
                target_model.id,
                "PROTAGONIST",
                {"t2i_settings": user.t2i_settings},
                user.encrypted_api_keys or {},
            )
            if not image_url:
                raise HTTPException(status_code=504, detail="Protagonist image generation timed out or failed.")
        elif payload.target_type == "scene":
            prompt = _build_visual_prompt(
                payload.target_type,
                target_data,
                payload.prompt,
                style_instruction=style_instruction,
                tone_instruction=tone_instruction,
            )
            image_url = await MediaEngine.generate_scene_image(
                prompt,
                adventure_id,
                {"t2i_settings": user.t2i_settings},
                user.encrypted_api_keys or {},
            )
            if not image_url:
                raise HTTPException(status_code=504, detail="Scene image generation timed out or failed.")
        else:
            prompt = _build_visual_prompt(
                payload.target_type,
                target_data,
                payload.prompt,
                style_instruction=style_instruction,
                tone_instruction=tone_instruction,
            )
            image_url = await MediaEngine.generate_entity_image(
                prompt,
                adventure_id,
                target_model.id,
                target_model.entity_type,
                {"t2i_settings": user.t2i_settings},
                user.encrypted_api_keys or {},
            )
            if not image_url:
                raise HTTPException(status_code=504, detail="Image generation timed out or failed.")
            
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image generation error: {str(e)}")

    setattr(target_model, image_attr, image_url)
    await db.commit()
    return {
        "status": "updated",
        "adventure_id": adventure_id,
        "target_type": payload.target_type,
        "target_id": payload.target_id,
        "image_url": image_url,
    }


@router.post("/{adventure_id}/visuals/upload")
async def upload_visual(
    adventure_id: str,
    target_type: str = Form(...),
    target_id: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Uploads a visual asset for a cover, protagonist, scene, NPC, or object."""
    state_res = await db.execute(select(GameState).where(GameState.adventure_id == adventure_id))
    state = state_res.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="Game state not found.")

    spec = _get_visual_upload_spec(target_type)

    target_model, _, image_attr = await _resolve_visual_target(
        db=db,
        adventure_id=adventure_id,
        target_type=target_type,
        target_id=target_id,
    )
    ext = _get_extension(file.filename or "")
    if ext not in VISUAL_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file extension. Use jpg, jpeg, png, or webp.")

    if file.content_type and file.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(status_code=400, detail="Unsupported file type. Use png, jpeg, or webp.")

    file_bytes = await file.read()
    if len(file_bytes) > spec["max_bytes"]:
        max_mb = spec["max_bytes"] / (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max file size for this asset is {max_mb:.1f} MB.",
        )

    target_dir = os.path.join(settings.DATA_DIR, "adventures", adventure_id, spec["folder"])
    os.makedirs(target_dir, exist_ok=True)

    filename = f"cover_{uuid.uuid4().hex}.{ext}" if target_type == "cover" else f"{target_id}.{ext}"
    filepath = os.path.join(target_dir, filename)

    try:
        image = Image.open(io.BytesIO(file_bytes))
        image.load()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {exc}") from exc

    if image.width > spec["max_width"] or image.height > spec["max_height"]:
        raise HTTPException(
            status_code=400,
            detail=f"Image too large. Max size for this asset is {spec['max_width']}x{spec['max_height']}.",
        )

    try:
        if image.mode in ("RGBA", "P") and ext in {"jpg", "jpeg"}:
            image = image.convert("RGB")

        save_format = "JPEG" if ext in {"jpg", "jpeg"} else ext.upper()
        image.save(filepath, format=save_format)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to store uploaded image: {exc}") from exc


    image_url = f"/data/adventures/{adventure_id}/{spec['folder']}/{filename}".replace("\\", "/")
    setattr(target_model, image_attr, image_url)
    await db.commit()

    return {
        "status": "uploaded",
        "adventure_id": adventure_id,
        "target_type": target_type,
        "target_id": target_id,
        "image_url": image_url,
        "recommended_format": spec["recommended"],
    }

@router.post("/{adventure_id}/reset")
async def reset_adventure(adventure_id: str, db: AsyncSession = Depends(get_db)):
    """
    Hard-resets the adventure: restores world, wipes chat history, and resets character stats/inventory.
    """
    adv_res = await db.execute(select(Adventure).where(Adventure.id == adventure_id))
    adventure = adv_res.scalars().first()
    if not adventure or not adventure.original_manifest:
        raise HTTPException(status_code=400, detail="Adventure not found or has no original manifest to reset to.")
    
    # 1. Clear current world & narration data
    # Backup image URLs first to preserve visuals
    ent_res = await db.execute(select(WorldEntity).where(WorldEntity.adventure_id == adventure_id))
    img_map = {e.id: e.image_url for e in ent_res.scalars().all() if e.image_url}

    await db.execute(delete(WorldScene).where(WorldScene.adventure_id == adventure_id))
    await db.execute(delete(WorldExit).where(WorldExit.adventure_id == adventure_id))
    await db.execute(delete(WorldEntity).where(WorldEntity.adventure_id == adventure_id))
    await db.execute(delete(WorldMap).where(WorldMap.adventure_id == adventure_id))
    
    # 2. Reset GameState & Avatar
    # ... (same)
    state_res = await db.execute(select(GameState).where(GameState.adventure_id == adventure_id))
    state = state_res.scalars().first()
    if state:
        # Wipe chat logs
        await db.execute(delete(ChatMessage).where(ChatMessage.game_state_id == state.id))
        
        # Reset state parameters
        state.in_game_time = 0
        state.is_paused = False
        
        # Reset Avatar to starting baseline
        av_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
        avatar = av_res.scalars().first()
        if avatar:
            avatar.hp = 200
            avatar.stamina = 200
            avatar.mana = 200
            avatar.inventory = []
            avatar.status_effects = []
            avatar.equipment = {
                "Head": None, "Chest": None, "Arms": None, "Legs": None,
                "Hands": None, "Feet": None, "Ring_1": None, "Ring_2": None, "Amulet": None
            }

    # 3. Re-apply world blueprint (with preserved images)
    normalized_manifest = _normalize_manifest_for_world_generator(adventure.original_manifest)
    manifest_to_apply = normalized_manifest or adventure.original_manifest
    await WorldGenerator.apply_manifest(db, adventure_id, manifest_to_apply, existing_images=img_map)
    
    # 4. Final Scene Calibration
    # We need the first scene ID from the manifest to set the avatar's starting point
    first_scene_id = (manifest_to_apply.get("scenes", [{}])[0].get("id") if isinstance(manifest_to_apply, dict) else None)
    if first_scene_id and state:
        state.scene_id = first_scene_id

    await db.commit()
    logger.info("Hard-reset adventure %s. World, history, and avatar restored.", adventure_id)
    return {"status": "reset", "message": "Chronicle and world have been fully restored."}

@router.get("/{adventure_id}/export/manifest")
async def export_adventure_manifest(adventure_id: str, db: AsyncSession = Depends(get_db)):
    """Exports an importable blueprint manifest without runtime/session state."""
    adv_res = await db.execute(select(Adventure).where(Adventure.id == adventure_id))
    adventure = adv_res.scalars().first()
    if not adventure or not adventure.original_manifest:
        raise HTTPException(status_code=404, detail="Original manifest not found.")

    manifest = deepcopy(adventure.original_manifest)

    # Keep export free of runtime/session data while ensuring expected blueprint metadata exists.
    manifest["format"] = FORMAT_NAME
    manifest["version"] = CURRENT_VERSION
    manifest.setdefault("id", adventure.id)
    manifest.setdefault("title", adventure.title)

    if not manifest.get("story_idea") and adventure.context:
        manifest["story_idea"] = adventure.context
    if not manifest.get("description") and adventure.context:
        manifest["description"] = adventure.context

    if not manifest.get("time_per_turn"):
        manifest["time_per_turn"] = adventure.time_per_turn

    if not manifest.get("pacing_minutes"):
        manifest["pacing_minutes"] = adventure.pacing_minutes

    manifest.setdefault("generate_npc_images", False)
    manifest.setdefault("generate_item_images", False)
    manifest.setdefault("automatic_cover_generation", False)
    manifest.setdefault("clock_enabled", bool(adventure.clock_enabled))
    manifest.setdefault("rule_enforcement_mode", adventure.rule_enforcement_mode)
    manifest.setdefault("tone", adventure.selected_tone)
    if adventure.selected_image_styles:
        manifest.setdefault("image_styles", adventure.selected_image_styles)

    start_dt = _resolve_start_datetime(manifest)
    if start_dt:
        manifest["start_datetime"] = start_dt
        try:
            dt = datetime.fromisoformat(start_dt.replace("Z", "+00:00"))
            manifest.setdefault("start_date", dt.date().isoformat())
            manifest.setdefault("start_time", dt.strftime("%H:%M"))
        except ValueError:
            pass

    return manifest

@router.get("/{adventure_id}/export/session")
async def export_adventure_session(adventure_id: str, db: AsyncSession = Depends(get_db)):
    """Exports the COMPLETE current game state as a bundle."""
    adv_res = await db.execute(select(Adventure).where(Adventure.id == adventure_id))
    adventure = adv_res.scalars().first()
    if not adventure:
        raise HTTPException(status_code=404, detail="Adventure not found")
        
    scene_res = await db.execute(select(WorldScene).where(WorldScene.adventure_id == adventure_id))
    exit_res = await db.execute(select(WorldExit).where(WorldExit.adventure_id == adventure_id))
    entity_res = await db.execute(select(WorldEntity).where(WorldEntity.adventure_id == adventure_id))
    
    # Game State & Avatar
    state_res = await db.execute(select(GameState).where(GameState.adventure_id == adventure_id))
    state = state_res.scalars().first()
    avatar = None
    chat_logs = []
    
    if state:
        av_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
        avatar = av_res.scalars().first()
        
        chat_res = await db.execute(select(ChatMessage).where(ChatMessage.game_state_id == state.id).order_by(ChatMessage.created_at))
        chat_logs = chat_res.scalars().all()

    return {
        "format": FORMAT_NAME,
        "version": CURRENT_VERSION,
        "type": "SESSION_BUNDLE",
        "adventure": {c.name: getattr(adventure, c.name) for c in adventure.__table__.columns},
        "scenes": [{c.name: getattr(s, c.name) for c in s.__table__.columns} for s in scene_res.scalars().all()],
        "exits": [{c.name: getattr(e, c.name) for c in e.__table__.columns} for e in exit_res.scalars().all()],
        "entities": [{c.name: getattr(ent, c.name) for c in ent.__table__.columns} for ent in entity_res.scalars().all()],
        "game_state": {c.name: getattr(state, c.name) for c in state.__table__.columns} if state else None,
        "avatar": {c.name: getattr(avatar, c.name) for c in avatar.__table__.columns} if avatar else None,
        "chat_history": [{c.name: getattr(msg, c.name) for c in msg.__table__.columns} for msg in chat_logs]
    }


def _build_adventure_blueprint_manifest(
    adventure: Adventure,
    scenes: list[WorldScene],
    exits: list[WorldExit],
    entities: list[WorldEntity],
    avatar: Optional[Avatar],
) -> dict[str, Any]:
    return {
        "format": FORMAT_NAME,
        "version": CURRENT_VERSION,
        "type": "ADVENTURE_BLUEPRINT",
        "adventure": {c.name: getattr(adventure, c.name) for c in adventure.__table__.columns},
        "protagonist": {c.name: getattr(avatar, c.name) for c in avatar.__table__.columns} if avatar else None,
        "scenes": [
            {
                "id": s.id,
                "name": s.label,
                "description": s.description,
                "image_url": s.image_url,
            }
            for s in scenes
        ],
        "npcs": [
            {
                **{c.name: getattr(ent, c.name) for c in ent.__table__.columns},
                "start_scene_id": ent.current_scene_id,
            }
            for ent in entities
            if _is_npc_entity(ent)
        ],
        "objects": [
            {
                **{c.name: getattr(ent, c.name) for c in ent.__table__.columns},
                "start_scene_id": ent.current_scene_id,
            }
            for ent in entities
            if _is_object_entity(ent)
        ],
        "exits": [
            {
                "from_scene_id": e.from_scene_id,
                "to_scene_id": e.to_scene_id,
                "label": e.label,
                "is_locked": e.is_locked,
                "lock_description": e.lock_description,
            }
            for e in exits
        ],
    }


@router.get("/{adventure_id}/export/adv")
async def export_adventure_adv(adventure_id: str, db: AsyncSession = Depends(get_db)):
    """Exports the adventure as raw ADV JSON using the same blueprint structure as ADZ."""
    adv_res = await db.execute(select(Adventure).where(Adventure.id == adventure_id))
    adventure = adv_res.scalars().first()
    if not adventure:
        raise HTTPException(status_code=404, detail="Adventure not found")

    scene_res = await db.execute(select(WorldScene).where(WorldScene.adventure_id == adventure_id))
    scenes = scene_res.scalars().all()

    exit_res = await db.execute(select(WorldExit).where(WorldExit.adventure_id == adventure_id))
    exits = exit_res.scalars().all()

    entity_res = await db.execute(select(WorldEntity).where(WorldEntity.adventure_id == adventure_id))
    entities = entity_res.scalars().all()

    avatar_res = await db.execute(select(Avatar).where(Avatar.adventure_id == adventure_id))
    avatar = avatar_res.scalars().first()

    manifest = _build_adventure_blueprint_manifest(adventure, scenes, exits, entities, avatar)

    def json_serial(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    payload = json.dumps(manifest, indent=2, default=json_serial).encode("utf-8")
    safe_title = "".join([c for c in adventure.title if c.isalnum() or c in (" ", "_")]).strip().replace(" ", "_")
    filename = f"{safe_title}.adv"
    return StreamingResponse(
        io.BytesIO(payload),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{adventure_id}/export/adz")
async def export_adventure_adz(adventure_id: str, db: AsyncSession = Depends(get_db)):
    """Exports the adventure as a ZIP archive (ADZ) including all asset images."""
    adv_res = await db.execute(select(Adventure).where(Adventure.id == adventure_id))
    adventure = adv_res.scalars().first()
    if not adventure:
        raise HTTPException(status_code=404, detail="Adventure not found")
        
    scene_res = await db.execute(select(WorldScene).where(WorldScene.adventure_id == adventure_id))
    scenes = scene_res.scalars().all()
    
    exit_res = await db.execute(select(WorldExit).where(WorldExit.adventure_id == adventure_id))
    exits = exit_res.scalars().all()
    
    entity_res = await db.execute(select(WorldEntity).where(WorldEntity.adventure_id == adventure_id))
    entities = entity_res.scalars().all()

    avatar_res = await db.execute(select(Avatar).where(Avatar.adventure_id == adventure_id))
    avatar = avatar_res.scalars().first()

    manifest = _build_adventure_blueprint_manifest(adventure, scenes, exits, entities, avatar)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        image_mapping = {} # original_url -> zip_path
        
        def add_image_to_zip(url: str):
            if not url or url.startswith("http") or url in image_mapping:
                return image_mapping.get(url, url)
            
            if url.startswith("/data/"):
                rel_path = url.removeprefix("/data/")
                abs_path = os.path.join(settings.DATA_DIR, rel_path)
                
                if os.path.exists(abs_path):
                    zip_path = f"assets/{os.path.basename(abs_path)}"
                    counter = 1
                    original_zip_path = zip_path
                    while zip_path in zip_file.namelist():
                        name, ext = os.path.splitext(original_zip_path)
                        zip_path = f"{name}_{counter}{ext}"
                        counter += 1
                        
                    zip_file.write(abs_path, zip_path)
                    image_mapping[url] = zip_path
                    return zip_path
            return url

        # Process all image fields
        if adventure.image_url:
            manifest["adventure"]["image_url"] = add_image_to_zip(adventure.image_url)
            
        if avatar and avatar.profile_image:
            if manifest["protagonist"]:
                manifest["protagonist"]["profile_image"] = add_image_to_zip(avatar.profile_image)

        for i, s in enumerate(scenes):
            if s.image_url:
                manifest["scenes"][i]["image_url"] = add_image_to_zip(s.image_url)

        for i, ent in enumerate(manifest["npcs"]):
            if ent["image_url"]:
                manifest["npcs"][i]["image_url"] = add_image_to_zip(ent["image_url"])

        for i, ent in enumerate(manifest["objects"]):
            if ent["image_url"]:
                manifest["objects"][i]["image_url"] = add_image_to_zip(ent["image_url"])

        # Use a custom serializer to handle datetime objects from the DB
        def json_serial(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        zip_file.writestr("adventure.adv", json.dumps(manifest, indent=2, default=json_serial))

    zip_buffer.seek(0)
    safe_title = "".join([c for c in adventure.title if c.isalnum() or c in (" ", "_")]).strip().replace(" ", "_")
    filename = f"{safe_title}.adz"
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/import/adz", status_code=201)
async def import_adventure_adz(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Imports an adventure from an ADZ archive, including all asset images."""
    if not file.filename.lower().endswith(".adz"):
        raise HTTPException(status_code=400, detail="Invalid file format. Expected .adz")

    zip_content = await file.read()
    zip_buffer = io.BytesIO(zip_content)
    
    try:
        with zipfile.ZipFile(zip_buffer, "r") as zip_file:
            if "adventure.adv" not in zip_file.namelist():
                raise HTTPException(status_code=400, detail="Invalid ADZ archive. Missing adventure.adv")
            
            manifest_data = json.loads(zip_file.read("adventure.adv").decode("utf-8"))
            _validate_import_manifest(manifest_data, require_format=True)
            
            # Create new adventure ID
            new_adv_id = str(uuid.uuid4())
            adv_data = manifest_data["adventure"]
            
            # Create Adventure record
            new_adv = Adventure(
                id=new_adv_id,
                owner_id=current_user.id,
                title=adv_data["title"],
                context=adv_data["context"],
                strict_rules=adv_data.get("strict_rules", True),
                rule_enforcement_mode=adv_data.get("rule_enforcement_mode", "strict"),
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
                    target_path = os.path.join(target_base_dir, filename)
                    with open(target_path, "wb") as f:
                        f.write(zip_file.read(zip_path))
                    
                    rel_path = os.path.relpath(target_path, settings.DATA_DIR).replace("\\", "/")
                    existing_images_mapping[zip_path] = f"/data/{rel_path}"

            # Create Avatar
            prot = manifest_data.get("protagonist")
            if prot:
                profile_image = existing_images_mapping.get(prot.get("profile_image")) if prot.get("profile_image") else None
                
                new_avatar = Avatar(
                    user_id=current_user.id,
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
                    user_id=current_user.id,
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
                "scenes": manifest_data["scenes"],
                "exits": manifest_data["exits"],
                "npcs": manifest_data["npcs"],
                "objects": manifest_data["objects"],
                "quests": adv_data.get("quests", [])
            }

            # Fallback for old ADZs that use current_scene_id instead of start_scene_id
            for n in world_manifest["npcs"]:
                if "start_scene_id" not in n and "current_scene_id" in n:
                    n["start_scene_id"] = n["current_scene_id"]
            for o in world_manifest["objects"]:
                if "start_scene_id" not in o and "current_scene_id" in o:
                    o["start_scene_id"] = o["current_scene_id"]
            
            image_urls = {}
            if prot and prot.get("profile_image") in existing_images_mapping:
                image_urls["PROTAGONIST"] = existing_images_mapping[prot["profile_image"]]
            
            for s in manifest_data["scenes"]:
                if s.get("image_url") in existing_images_mapping:
                    image_urls[s["id"]] = existing_images_mapping[s["image_url"]]
            
            for n in manifest_data["npcs"]:
                if n.get("image_url") in existing_images_mapping:
                    image_urls[n["id"]] = existing_images_mapping[n["image_url"]]

            for o in manifest_data["objects"]:
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
            return {"status": "success", "adventure_id": new_adv_id}

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        logger.exception("ADZ Import failed")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.post("/import/adv", status_code=201)
async def import_adventure_adv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Imports an ADV JSON blueprint using the same structure as ADZ's adventure.adv (without assets)."""
    if not file.filename.lower().endswith(".adv"):
        raise HTTPException(status_code=400, detail="Invalid file format. Expected .adv")

    raw = await file.read()
    try:
        manifest_data = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid ADV JSON file.") from exc

    _validate_import_manifest(manifest_data, require_format=True)

    try:
        adv_data = manifest_data.get("adventure")
        if not isinstance(adv_data, dict):
            raise HTTPException(status_code=400, detail="Invalid ADV file. Missing adventure section")

        new_adv_id = str(uuid.uuid4())
        new_adv = Adventure(
            id=new_adv_id,
            owner_id=current_user.id,
            title=adv_data.get("title") or "Imported Adventure",
            context=adv_data.get("context"),
            strict_rules=adv_data.get("strict_rules", True),
            rule_enforcement_mode=adv_data.get("rule_enforcement_mode", "strict"),
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

        prot = manifest_data.get("protagonist")
        if isinstance(prot, dict):
            new_avatar = Avatar(
                user_id=current_user.id,
                adventure_id=new_adv_id,
                name=prot.get("name") or "You",
                role=prot.get("role"),
                description=prot.get("description"),
                profile_image=prot.get("profile_image"),
                hp=prot.get("hp", 200),
                stamina=prot.get("stamina", 200),
                mana=prot.get("mana", 200),
                inventory=prot.get("inventory", []),
                equipment=prot.get("equipment", {}),
                stats=prot.get("stats", {}),
            )
            db.add(new_avatar)
            await db.flush()

            db.add(
                GameState(
                    id=new_adv_id,
                    user_id=current_user.id,
                    adventure_id=new_adv_id,
                    avatar_id=new_avatar.id,
                    scene_id="START",
                    in_game_time=0,
                )
            )

        world_manifest = {
            "protagonist": {
                "name": prot.get("name") if isinstance(prot, dict) and prot.get("name") else "You",
                "role": prot.get("role") if isinstance(prot, dict) else "Adventurer",
                "description": prot.get("description") if isinstance(prot, dict) else "",
                "starting_inventory": [],
                "starting_equipment": {},
            },
            "scenes": manifest_data.get("scenes", []),
            "exits": manifest_data.get("exits", []),
            "npcs": manifest_data.get("npcs", []),
            "objects": manifest_data.get("objects", []),
            "quests": manifest_data.get("quests", []),
        }

        for n in world_manifest["npcs"]:
            if "start_scene_id" not in n and "current_scene_id" in n:
                n["start_scene_id"] = n["current_scene_id"]
        for o in world_manifest["objects"]:
            if "start_scene_id" not in o and "current_scene_id" in o:
                o["start_scene_id"] = o["current_scene_id"]

        image_urls: dict[str, str] = {}
        if isinstance(prot, dict) and prot.get("profile_image"):
            image_urls["PROTAGONIST"] = prot["profile_image"]

        for s in manifest_data.get("scenes", []):
            if isinstance(s, dict) and s.get("image_url") and s.get("id"):
                image_urls[s["id"]] = s["image_url"]
        for n in manifest_data.get("npcs", []):
            if isinstance(n, dict) and n.get("image_url") and n.get("id"):
                image_urls[n["id"]] = n["image_url"]
        for o in manifest_data.get("objects", []):
            if isinstance(o, dict) and o.get("image_url") and o.get("id"):
                image_urls[o["id"]] = o["image_url"]

        await WorldGenerator.apply_manifest(
            db=db,
            adventure_id=new_adv_id,
            manifest_dict=world_manifest,
            user=None,
            existing_images=image_urls,
        )

        cover_image = adv_data.get("image_url")
        if isinstance(cover_image, str) and (cover_image.startswith("/data/") or cover_image.startswith("http")):
            new_adv.image_url = cover_image

        if not new_adv.image_url:
            new_adv.image_url = await MediaEngine.generate_svg_placeholder(
                new_adv_id,
                new_adv.title,
                os.path.join(settings.DATA_DIR, "adventures", new_adv_id),
                "cover_placeholder.svg",
            )

        await db.commit()
        return {"status": "success", "adventure_id": new_adv_id}

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        logger.exception("ADV Import failed")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

@router.post("/import/session-bundle")
async def import_adventure_session_bundle(
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Imports an adventure from JSON.
    Supports either a Raw Manifest or a Full Session Bundle.
    """
    user = current_user
    _validate_import_manifest(payload, require_format=True)

    # Determine if this is a Session Bundle or just a Manifest
    is_session = payload.get("type") == "SESSION_BUNDLE"
    
    if is_session:
        # --- Handle Session Bundle ---
        data = payload
        old_adv = data["adventure"]
        
        # 1. Recreate Adventure
        new_adv = Adventure(
            owner_id=user.id,
            title=f"{old_adv['title']} (Imported)",
            context=old_adv.get("context"),
            image_url=old_adv.get("image_url"),
            strict_rules=old_adv.get("strict_rules", True),
            time_per_turn=old_adv.get("time_per_turn", 10),
            game_over_rules=old_adv.get("game_over_rules"),
            original_manifest=old_adv.get("original_manifest")
        )
        db.add(new_adv)
        await db.flush() # Get new_adv.id
        
        # 2. Recreate Scenes (ID Slug preservation is fine as they are scoped by adventure_id)
        for s in data["scenes"]:
            db.add(WorldScene(
                id=s["id"],
                adventure_id=new_adv.id,
                label=s["label"],
                description=s["description"]
            ))
            
        # 3. Recreate Entities
        for ent in data["entities"]:
            db.add(WorldEntity(
                id=ent["id"],
                adventure_id=new_adv.id,
                entity_type=ent["entity_type"],
                name=ent["name"],
                description=ent["description"],
                current_scene_id=ent["current_scene_id"],
                spatial_position=ent.get("spatial_position"),
                inventory=ent.get("inventory", []),
                stats=ent.get("stats", {})
            ))
            
        # 4. Recreate Exits
        for ex in data["exits"]:
            db.add(WorldExit(
                adventure_id=new_adv.id,
                from_scene_id=ex["from_scene_id"],
                to_scene_id=ex["to_scene_id"],
                label=ex["label"],
                is_locked=ex.get("is_locked", False),
                lock_description=ex.get("lock_description")
            ))
            
        # 5. Recreate Avatar & GameState
        old_state = data.get("game_state")
        old_avatar = data.get("avatar")
        
        if old_state and old_avatar:
            new_avatar = Avatar(
                user_id=user.id,
                name=old_avatar["name"],
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
            
            new_state = GameState(
                user_id=user.id,
                adventure_id=new_adv.id,
                avatar_id=new_avatar.id,
                scene_id=old_state["scene_id"],
                in_game_time=old_state.get("in_game_time", 0)
            )
            db.add(new_state)
            await db.flush()
            
            # 6. Recreate Chat History
            for msg in data.get("chat_history", []):
                db.add(ChatMessage(
                    game_state_id=new_state.id,
                    role=msg["role"],
                    content=msg["content"]
                ))
        
        await db.commit()
        return {"status": "imported", "adventure_id": new_adv.id, "type": "SESSION"}

    else:
        # --- Handle Pure Manifest Import ---
        # Assume payload IS the manifest
        # We need a title and context to create the shell first
        new_adv = Adventure(
            owner_id=user.id,
            title="Imported Blueprint",
            context="Restored from blueprint.",
            original_manifest=payload
        )
        db.add(new_adv)
        await db.flush()
        
        await WorldGenerator.apply_manifest(db, new_adv.id, payload)
        await db.commit()
        return {"status": "imported", "adventure_id": new_adv.id, "type": "MANIFEST"}

async def _build_sheet_snapshot(avatar: Avatar, state: GameState, db: AsyncSession) -> dict:
    """Builds a serialisable character-sheet snapshot with synchronised world entity images."""
    adv_res = await db.execute(select(Adventure).where(Adventure.id == state.adventure_id))
    adventure = adv_res.scalars().first()
    start_datetime = None
    if adventure and adventure.original_manifest:
        start_datetime = _resolve_start_datetime(adventure.original_manifest)
    
    # Fallback if clock is enabled but manifest lacks start time
    if not start_datetime and adventure and adventure.clock_enabled:
        start_datetime = "2026-04-17T08:00:00" # Consistent default start
    
    # 1. Fetch current adventure entities that have image_urls to ensure the sheet is up to date
    res = await db.execute(
        select(WorldEntity.id, WorldEntity.image_url)
        .where(WorldEntity.adventure_id == state.adventure_id, WorldEntity.image_url.is_not(None))
    )
    img_map = {row.id: row.image_url for row in res.all() if row.id}
    
    # 2. Enrich inventory
    synced_inventory = []
    for item in (avatar.inventory or []):
        item_copy = dict(item)
        item_id = item_copy.get("id")
        if item_id in img_map and not item_copy.get("image_url"):
            item_copy["image_url"] = img_map[item_id]
        synced_inventory.append(item_copy)
        
    synced_equipment = {}
    for slot, item in (avatar.equipment or {}).items():
        if item and isinstance(item, dict):
            item_copy = dict(item)
            item_id = item_copy.get("id")
            if item_id in img_map and not item_copy.get("image_url"):
                item_copy["image_url"] = img_map[item_id]
            synced_equipment[slot] = item_copy
        else:
            synced_equipment[slot] = item
            
    # 4. Include current scene info
    scene_res = await db.execute(select(WorldScene).where(WorldScene.id == state.scene_id, WorldScene.adventure_id == state.adventure_id))
    current_scene = scene_res.scalars().first()
    
    return {
        "name": avatar.name,
        "role": avatar.role,
        "description": avatar.description,
        "profile_image": avatar.profile_image,
        "hp": avatar.hp,
        "stamina": avatar.stamina,
        "mana": avatar.mana,
        "stats": avatar.stats,
        "inventory": synced_inventory,
        "equipment": synced_equipment,
        "status_effects": avatar.status_effects,
        "in_game_time": state.in_game_time,
        "start_datetime": start_datetime,
        "current_scene": current_scene.label if current_scene else state.scene_id,
        "scene_id": state.scene_id,
        "adventure_title": adventure.title if adventure else "Unknown Adventure",
        "adventure_id": state.adventure_id,
        "exp": avatar.exp
    }

async def _enrich_map_nodes(adventure_id: str, nodes: dict, db: AsyncSession) -> dict:
    """Enriches map node metadata (labels/descriptions) with current data from WorldScene table."""
    if not nodes:
        return {}
        
    scene_res = await db.execute(select(WorldScene).where(WorldScene.adventure_id == adventure_id))
    db_scenes = {s.id: s for s in scene_res.scalars().all()}
    
    # Also get safe-id mapped scenes to ensure we find everything
    safe_db_scenes = {MapEngine._safe_id(s.id) if hasattr(MapEngine, '_safe_id') else (s.id.upper().replace("-", "_")): s for s in db_scenes.values()}
    
    enriched = {}
    for sid, meta in nodes.items():
        # Try to find the scene by the stored sid or original ID
        scene = db_scenes.get(meta.get("id")) or safe_db_scenes.get(sid)
        
        enriched[sid] = dict(meta)
        if scene:
            # Only update if the DB version is more detailed or the meta version is empty
            if not meta.get("label") or (scene.label and len(scene.label) > len(meta.get("label", ""))):
                enriched[sid]["label"] = scene.label
            if not meta.get("description") or (scene.description and len(scene.description) > len(meta.get("description", ""))):
                enriched[sid]["description"] = scene.description
            # Note: WorldScene doesn't have image_url yet, so we skip it or use getattr safely
            db_img = getattr(scene, "image_url", None)
            if not meta.get("image_url") and db_img:
                enriched[sid]["image_url"] = db_img
                
    return enriched

async def _get_npc_metadata(adventure_id: str, db: AsyncSession) -> dict:
    """Returns a map of { NPC_Name: EntityData } for all NPCs in the adventure."""
    res = await db.execute(select(WorldEntity).where(
        WorldEntity.adventure_id == adventure_id, 
        WorldEntity.entity_type == "NPC"
    ))
    npcs = res.scalars().all()
    # Return mapping of name to full data for tooltips
    return {
        n.name: {
            "id": n.id,
            "name": n.name,
            "description": n.description,
            "image_url": n.image_url,
            "entity_type": n.entity_type
        } for n in npcs if n.image_url
    }


async def _build_full_world_debug_snapshot(
    adventure: Adventure,
    state: GameState,
    avatar: Optional[Avatar],
    db: AsyncSession,
) -> dict[str, Any]:
    """Builds a complete world snapshot comparable to ADV blueprint exports."""
    scene_res = await db.execute(select(WorldScene).where(WorldScene.adventure_id == state.adventure_id))
    scenes = scene_res.scalars().all()

    exit_res = await db.execute(select(WorldExit).where(WorldExit.adventure_id == state.adventure_id))
    exits = exit_res.scalars().all()

    entity_res = await db.execute(select(WorldEntity).where(WorldEntity.adventure_id == state.adventure_id))
    entities = entity_res.scalars().all()

    blueprint_manifest = _build_adventure_blueprint_manifest(adventure, scenes, exits, entities, avatar)

    return {
        "blueprint": blueprint_manifest,
        "runtime": {
            "game_id": state.id,
            "adventure_id": state.adventure_id,
            "current_scene_id": state.scene_id,
            "in_game_time": state.in_game_time,
            "is_paused": state.is_paused,
        },
        "entities_all": [{c.name: getattr(ent, c.name) for c in ent.__table__.columns} for ent in entities],
    }

@router.get("/{game_id}/chat", response_model=ChatResponse)
async def get_chat_history(
    game_id: str,
    include_full_world: bool = Query(False, description="Include a full ADV-like world snapshot for debugging."),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves full chat history and current session state."""
    state_res = await db.execute(select(GameState).where(GameState.id == game_id))
    state = state_res.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")

    adv_res = await db.execute(
        select(Adventure).where(
            (Adventure.id == state.adventure_id)
            & (Adventure.owner_id == current_user.id)
        )
    )
    adventure = adv_res.scalars().first()
    if not adventure:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Migrate legacy sessions created before strict user ownership checks.
    if state.user_id != current_user.id:
        state.user_id = current_user.id
        await db.commit()
        await db.refresh(state)
        
    av_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
    avatar = av_res.scalars().first()
    
    chat_res = await db.execute(select(ChatMessage).where(ChatMessage.game_state_id == game_id).order_by(ChatMessage.created_at.asc()))
    history = [{"role": m.role, "content": m.content} for m in chat_res.scalars().all()]
    
    map_res = await db.execute(select(WorldMap).where(WorldMap.adventure_id == state.adventure_id))
    world_map = map_res.scalars().first()
    mermaid_data = MapEngine.to_mermaid(world_map) if world_map else None
    
    ent_res = await db.execute(select(WorldEntity).where(
        WorldEntity.adventure_id == state.adventure_id, 
        WorldEntity.current_scene_id == state.scene_id,
        WorldEntity.is_hidden == False,
        WorldEntity.is_in_inventory == False
    ))
    entities = [{c.name: getattr(e, c.name) for c in e.__table__.columns} for e in ent_res.scalars().all()]
    
    scene_res = await db.execute(select(WorldScene).where(
        WorldScene.adventure_id == state.adventure_id,
        WorldScene.id == state.scene_id
    ))
    current_scene = scene_res.scalars().first()

    full_world = None
    if include_full_world:
        full_world = await _build_full_world_debug_snapshot(adventure, state, avatar, db)

    return ChatResponse(
        messages=history,
        sheet=await _build_sheet_snapshot(avatar, state, db),
        mermaid=mermaid_data,
        nodes=await _enrich_map_nodes(state.adventure_id, world_map.nodes if world_map else {}, db),
        entities=entities,
        npc_metadata=await _get_npc_metadata(state.adventure_id, db),
        image_url=current_scene.image_url if current_scene else None,
        adventure_image=adventure.image_url if adventure else None,
        quests=adventure.quests,
        is_completed=adventure.is_completed,
        full_world=full_world,
    )

@router.post("/{game_id}/chat")
async def post_chat_message(
    game_id: str,
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Unified game turn endpoint. Processes user input, advances world state,
    and returns a stream of events (system messages, narrative chunks, final state).
    """
    async def event_generator():
        try:
            user_msg = payload.content.strip()
            
            # Immediately notify the user that we are processing via status event
            yield f"event: status\ndata: {json.dumps(jsonable_encoder({'content': 'Considering...'}))}\n\n"
            
            # 1. Load context
            state_res = await db.execute(select(GameState).where(GameState.id == game_id))
            state = state_res.scalars().first()
            if not state:
                yield f"event: error\ndata: {json.dumps(jsonable_encoder({'detail': 'Game session not found.'}))}\n\n"
                return

            adv_res = await db.execute(
                select(Adventure).where(
                    (Adventure.id == state.adventure_id)
                    & (Adventure.owner_id == current_user.id)
                )
            )
            adventure = adv_res.scalars().first()
            if not adventure:
                yield f"event: error\ndata: {json.dumps(jsonable_encoder({'detail': 'Game session not found.'}))}\n\n"
                return

            # Migrate legacy sessions created before strict user ownership checks.
            if state.user_id != current_user.id:
                state.user_id = current_user.id
                await db.flush()

            if state.is_paused:
                av_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
                avatar = av_res.scalars().first()
                yield f"event: final\ndata: {json.dumps(jsonable_encoder({
                    'messages': [{'role': 'system', 'content': 'The game is currently paused.'}],
                    'sheet': await _build_sheet_snapshot(avatar, state, db) if avatar else {}
                }))}\n\n"
                return

            av_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
            avatar = av_res.scalars().first()

            user = current_user

            response_messages = []
            image_url = None
            game_over = False
            game_over_reason = None
            discovered_item_ids = []

            # --- Fresh Entry / Re-orientation Check ---
            actual_user_input = user_msg
            if not user_msg:
                user_msg = "[LOOK AROUND]"

            # --- Handle Debug Commands ---
            if user_msg.startswith("/debug"):
                cmd_args = user_msg[7:].strip()

                if cmd_args.lower() == "walkthrough":
                    avatar_stats = dict(avatar.stats or {})
                    avatar_stats["walkthrough_revealed"] = True
                    avatar.stats = avatar_stats

                    await db.commit()
                    yield f"event: final\ndata: {json.dumps(jsonable_encoder({
                        'messages': [{'role': 'system', 'content': '[Debug] Walkthrough revealed without XP cost.'}],
                        'sheet': await _build_sheet_snapshot(avatar, state, db)
                    }))}\n\n"
                    return

                debug_info = await DebugEngine.handle_debug_command(db, state, cmd_args)
                
                # Check for special log toggle return markers
                if "[DEBUG_LOG_ON]" in debug_info:
                    msg = {"role": "system", "content": debug_info.replace("[DEBUG_LOG_ON]", "").strip()}
                elif "[DEBUG_LOG_OFF]" in debug_info:
                    msg = {"role": "system", "content": debug_info.replace("[DEBUG_LOG_OFF]", "").strip()}
                else:
                    msg = {"role": "system", "content": debug_info}

                await db.commit() # Persist toggle state
                yield f"event: final\ndata: {json.dumps(jsonable_encoder({
                    'messages': [msg],
                    'sheet': await _build_sheet_snapshot(avatar, state, db)
                }))}\n\n"
                return

            # --- Slash-command fast path ---
            if user_msg.startswith("/"):
                if user_msg.strip().lower() == "/map":
                    map_res = await db.execute(select(WorldMap).where(WorldMap.adventure_id == state.adventure_id))
                    world_map = map_res.scalars().first()
                    mermaid_data = MapEngine.to_mermaid(world_map) if world_map else None
                    yield f"event: final\ndata: {json.dumps(jsonable_encoder({
                        'messages': [], 
                        'sheet': await _build_sheet_snapshot(avatar, state, db), 
                        'mermaid': mermaid_data,
                        'nodes': await _enrich_map_nodes(state.adventure_id, world_map.nodes if world_map else {}, db)
                    }))}\n\n"
                    return
                
                response = CommandParser.parse_command(avatar, user_msg)

                if response == "[TRIGGER_WALKTHROUGH]":
                    walkthrough_state = _build_walkthrough_payload(adventure, avatar)
                    message = walkthrough_state.get("message") or "Walkthrough panel opened."
                    yield f"event: system\ndata: {json.dumps(jsonable_encoder({'role': 'system', 'content': message}))}\n\n"
                    await db.commit()
                    yield f"event: final\ndata: {json.dumps(jsonable_encoder({'sheet': await _build_sheet_snapshot(avatar, state, db)}))}\n\n"
                    return

                if response == "[TRIGGER_WALKTHROUGH_REVEAL]":
                    walkthrough_steps = _extract_walkthrough_steps(adventure)
                    if not walkthrough_steps:
                        message = "No walkthrough available for this adventure yet."
                    elif avatar.exp < WALKTHROUGH_REVEAL_COST:
                        missing = WALKTHROUGH_REVEAL_COST - avatar.exp
                        message = f"Not enough XP to reveal walkthrough. Need {missing} more XP."
                    else:
                        avatar.exp -= WALKTHROUGH_REVEAL_COST
                        avatar_stats = dict(avatar.stats or {})
                        avatar_stats["walkthrough_revealed"] = True
                        avatar.stats = avatar_stats
                        message = f"Walkthrough revealed for {WALKTHROUGH_REVEAL_COST} XP."

                    yield f"event: system\ndata: {json.dumps(jsonable_encoder({'role': 'system', 'content': message}))}\n\n"
                    await db.commit()
                    yield f"event: final\ndata: {json.dumps(jsonable_encoder({'sheet': await _build_sheet_snapshot(avatar, state, db)}))}\n\n"
                    return

                if response == "[TRIGGER_HINT]":
                    walkthrough_steps = _extract_walkthrough_steps(adventure)
                    if not walkthrough_steps:
                        hint_message = "No walkthrough available yet, so hints cannot be generated right now."
                    elif avatar.exp < WALKTHROUGH_HINT_COST:
                        missing = WALKTHROUGH_HINT_COST - avatar.exp
                        hint_message = f"Not enough XP for a hint. Need {missing} more XP."
                    else:
                        avatar.exp -= WALKTHROUGH_HINT_COST
                        avatar_stats = dict(avatar.stats or {})
                        hint_index = max(0, int(avatar_stats.get("walkthrough_hint_index", 0)))
                        step_idx = min(hint_index, len(walkthrough_steps) - 1)
                        hint_message = _hint_for_step(walkthrough_steps[step_idx])
                        avatar_stats["walkthrough_hint_index"] = min(hint_index + 1, len(walkthrough_steps))
                        avatar.stats = avatar_stats
                        hint_message = f"[Hint - {WALKTHROUGH_HINT_COST} XP] {hint_message}"

                    yield f"event: system\ndata: {json.dumps(jsonable_encoder({'role': 'system', 'content': hint_message}))}\n\n"
                    await db.commit()
                    yield f"event: final\ndata: {json.dumps(jsonable_encoder({'sheet': await _build_sheet_snapshot(avatar, state, db)}))}\n\n"
                    return
                
                if response.startswith("[TRIGGER_TAKE]"):
                    item_name = response[14:].strip()
                    ent_res = await db.execute(select(WorldEntity).where(
                        WorldEntity.adventure_id == state.adventure_id,
                        WorldEntity.current_scene_id == state.scene_id,
                        func.lower(WorldEntity.name) == item_name.lower(),
                        WorldEntity.entity_type == "OBJECT",
                        WorldEntity.is_hidden == False
                    ))
                    target_item = ent_res.scalars().first()
                    
                    if not target_item:
                        yield f"event: final\ndata: {json.dumps(jsonable_encoder({
                            'messages': [{'role': 'system', 'content': f"You don't see any '{item_name}' here or it is hidden."}],
                            'sheet': await _build_sheet_snapshot(avatar, state, db)
                        }))}\n\n"
                        return
                    
                    if not target_item.is_portable:
                        yield f"event: final\ndata: {json.dumps(jsonable_encoder({
                            'messages': [{'role': 'system', 'content': f"The '{target_item.name}' is not something you can just carry with you."}],
                            'sheet': await _build_sheet_snapshot(avatar, state, db)
                        }))}\n\n"
                        return
                        
                    target_item.is_in_inventory = True
                    target_item.current_scene_id = "INVENTORY"
                    
                    item_dict = {
                        "id": target_item.id,
                        "name": target_item.name,
                        "description": target_item.description,
                        "image_url": target_item.image_url,
                        "item_type": target_item.item_type,
                        "slot": (target_item.wearable_slots or ["Hands"])[0] if target_item.item_type == "WEARABLE" else "Hands"
                    }
                    new_inv = list(avatar.inventory)
                    new_inv.append(item_dict)
                    avatar.inventory = new_inv
                    
                    await db.commit()
                    yield f"event: final\ndata: {json.dumps(jsonable_encoder({
                        'messages': [{'role': 'system', 'content': f"You added the {target_item.name} to your inventory."}],
                        'sheet': await _build_sheet_snapshot(avatar, state, db),
                        'discovered_item_ids': [target_item.id]
                    }))}\n\n"
                    return

                if response.startswith("[TRIGGER_COMBINE]"):
                    args = response[17:].strip()
                    parts = args.lower().split(" with ") if " with " in args.lower() else args.split(" ", 1)
                    if len(parts) >= 2:
                        name1, name2 = parts[0].strip(), parts[1].strip()
                        all_entities_res = await db.execute(select(WorldEntity).where(WorldEntity.adventure_id == state.adventure_id))
                        all_entities = list(all_entities_res.scalars().all())
                        
                        item1 = next((e for e in all_entities if e.is_in_inventory and e.name.lower() == name1), None)
                        item2 = next((e for e in all_entities if e.is_in_inventory and e.name.lower() == name2), None)
                        if not item2:
                            item2 = next((e for e in all_entities if e.current_scene_id == state.scene_id and e.name.lower() == name2 and not e.is_hidden), None)

                        if item1 and item2:
                            result_item = next((e for e in all_entities if e.is_hidden and e.combination_ingredients and 
                                                set(e.combination_ingredients) == {item1.id, item2.id}), None)
                            
                            if result_item:
                                result_item.is_hidden = False
                                if result_item.is_portable:
                                    result_item.is_in_inventory = True
                                    result_item.current_scene_id = "INVENTORY"
                                    new_inv = [i for i in avatar.inventory if i["id"] not in [item1.id, item2.id]]
                                    new_inv.append({
                                        "id": result_item.id,
                                        "name": result_item.name,
                                        "description": result_item.description,
                                        "image_url": result_item.image_url,
                                        "item_type": result_item.item_type,
                                        "slot": "Hands"
                                    })
                                    avatar.inventory = new_inv
                                
                                await db.commit()
                                yield f"event: final\ndata: {json.dumps(jsonable_encoder({
                                    'messages': [{'role': 'system', 'content': f"SUCCESS! You combined {item1.name} and {item2.name} into: {result_item.name}."}],
                                    'sheet': await _build_sheet_snapshot(avatar, state, db),
                                    'discovered_item_ids': [result_item.id]
                                }))}\n\n"
                                return
                            
                            if item2.reveals_item_id and item2.combination_ingredients and item1.id in item2.combination_ingredients:
                                real_result = next((e for e in all_entities if e.id == item2.reveals_item_id), None)
                                if real_result:
                                    real_result.is_hidden = False
                                    item2.is_final_state = True
                                    item2.state_comment = f"Revealed {real_result.name} using {item1.name}."
                                    await db.commit()
                                    yield f"event: final\ndata: {json.dumps(jsonable_encoder({
                                        'messages': [{'role': 'system', 'content': f"Logic match: Using {item1.name} on {item2.name} revealed the {real_result.name}!"}],
                                        'sheet': await _build_sheet_snapshot(avatar, state, db),
                                        'discovered_item_ids': [real_result.id]
                                    }))}\n\n"
                                    return

                    user_msg = f"[COMBINE ACTION] {user_msg}" 
                
                else:
                    await db.commit()
                    yield f"event: final\ndata: {json.dumps(jsonable_encoder({
                        'messages': [{'role': 'system', 'content': response}],
                        'sheet': await _build_sheet_snapshot(avatar, state, db)
                    }))}\n\n"
                    return

            # --- Turn-based Logic: Advance Time & Status Effects ---
            state.in_game_time += adventure.time_per_turn
            tick_msgs = RuleEngine.apply_ticks(avatar)
            for tm in tick_msgs:
                response_messages.append({"role": "system", "content": tm})

            # Record User Message
            if actual_user_input:
                user_chat_rec = ChatMessage(game_state_id=game_id, role="user", content=actual_user_input)
                db.add(user_chat_rec)
                await db.flush()

            # --- History & Context ---
            hist_res = await db.execute(select(ChatMessage).where(ChatMessage.game_state_id == game_id).order_by(ChatMessage.created_at.asc()))
            history = [{"role": m.role, "content": m.content} for m in hist_res.scalars().all()]

            scene_res = await db.execute(select(WorldScene).where(WorldScene.id == state.scene_id, WorldScene.adventure_id == state.adventure_id))
            current_scene = scene_res.scalars().first()
            
            entity_res = await db.execute(select(WorldEntity).where(WorldEntity.current_scene_id == state.scene_id, WorldEntity.adventure_id == state.adventure_id))
            entities = entity_res.scalars().all()
            
            exit_res = await db.execute(select(WorldExit).where(WorldExit.from_scene_id == state.scene_id, WorldExit.adventure_id == state.adventure_id))
            exits = exit_res.scalars().all()

            context_messages = MemoryManager.build_context(
                avatar, adventure.context or "", history, 
                current_scene=current_scene, entities=entities, exits=exits, in_game_time=state.in_game_time
            )
            if adventure.quests:
                quests_summary = "\n".join([f"- {q.get('title', 'Unknown')}: {q.get('description', '')} (Status: {q.get('status', 'open')})" for q in adventure.quests])
                context_messages[0]["content"] += f"\n\nACTIVE QUESTS:\n{quests_summary}"
            
            system_prompt = context_messages[0]["content"]

            # --- LLM Processing ---
            settings = user.llm_settings or {}
            small_model = settings.get("small_model", "gpt-4o-mini")
            small_model_provider = (
                settings.get("small_model_provider")
                or settings.get("complex_model_provider")
                or settings.get("preferred_provider")
            )
            complex_model = settings.get("complex_model", "gpt-4o")
            complex_model_provider = (
                settings.get("complex_model_provider")
                or settings.get("small_model_provider")
                or settings.get("preferred_provider")
            )
            if not small_model_provider or not complex_model_provider:
                raise ValueError(
                    "No LLM provider configured for this user. "
                    "Open Settings -> LLM and set Small/Complex Model Provider."
                )
            
            # Initial LLM instance for Pass 1 (Mechanics)
            llm = GameMasterLLM(user, provider=small_model_provider, model_category="small")
            game_event = None
            response_text = ""

            if adventure.strict_rules:
                # --- Pass 1: Technical Reasoning ---
                quests_json = json.dumps(adventure.quests or [], indent=2)
                mechanics_system_prompt = system_prompt + "\n\n" + (
                    prompts.GM_STORY_MECHANICS_SUFFIX.format(quests_json=quests_json) if adventure.rule_enforcement_mode == "story" 
                    else prompts.GM_MECHANICS_SUFFIX.format(quests_json=quests_json)
                )
                
                if state.is_debug_enabled:
                    req_content = f"**[DEBUG] MECHANICAL REQUEST (Pass 1):**\n**System Prompt:**\n```text\n{mechanics_system_prompt}\n```\n**User Prompt:**\n```text\n{user_msg}\n```"
                    yield f"event: system\ndata: {json.dumps(jsonable_encoder({'role': 'assistant', 'content': req_content, 'is_debug': True}))}\n\n"

                yield f"event: status\ndata: {json.dumps(jsonable_encoder({'content': 'Validating rules...'}))}\n\n"
                
                game_event = await llm.aexecute_complex_task(
                    system_prompt=mechanics_system_prompt,
                    user_prompt=user_msg,
                    response_model=GameEvent,
                    model=small_model,
                    adventure_id=state.adventure_id,
                    game_id=game_id,
                    operation="chat_turn",
                    phase="mechanics",
                )

                if state.is_debug_enabled:
                    res_content = f"**[DEBUG] MECHANICAL RESPONSE (Pass 1):**\n```json\n{game_event.model_dump_json(indent=2)}\n```"
                    yield f"event: system\ndata: {json.dumps(jsonable_encoder({'role': 'assistant', 'content': res_content, 'is_debug': True}))}\n\n"

                if game_event.requested_skill_checks:
                    for req in game_event.requested_skill_checks:
                        stat_key = req.stat.lower().replace(" ", "_")
                        res = roll_skill_check(avatar, stat_key, req.dc)
                        check_res = SkillCheckResult(
                            stat=req.stat, dc=req.dc, roll=res["d20"], modifier=res["modifier"], 
                            total=res["total"], success=res["success"], reason=req.reason
                        )
                        status_text = "SUCCESS" if check_res.success else "FAILURE"
                        outcome_msg = f"[ROLL] {check_res.reason}: {check_res.stat.upper()} Check (DC {check_res.dc}) -> Rolled {check_res.roll} + {check_res.modifier} = {check_res.total} ({status_text})"
                        if state.is_debug_enabled:
                            yield f"event: system\ndata: {json.dumps(jsonable_encoder({'role': 'assistant', 'content': f'**[DEBUG] TOOL CALL (Skill Check):**\n{outcome_msg}', 'is_debug': True}))}\n\n"
                        response_messages.append({"role": "system", "content": outcome_msg})
                        game_event.skill_check_results = (game_event.skill_check_results or []) + [check_res]

                # --- Apply World State Updates (Move before narration) ---
                try:
                    RuleEngine.apply_event(avatar, game_event)
                except GameOverException as exc:
                    game_over = True
                    game_over_reason = str(exc)

                if game_event.new_scene_id:
                    resolved_scene_id = await _resolve_scene_id(db, state.adventure_id, game_event.new_scene_id)
                    if resolved_scene_id: state.scene_id = resolved_scene_id

                if game_event.moved_entities:
                    for move in game_event.moved_entities:
                        ent_mv_res = await db.execute(select(WorldEntity).where(WorldEntity.id == move.entity_id, WorldEntity.adventure_id == state.adventure_id))
                        ent_mv = ent_mv_res.scalars().first()
                        if ent_mv:
                            if move.to_scene_id == "INVENTORY":
                                ent_mv.is_in_inventory = True
                                response_messages.append({"role": "system", "content": f"[System] Item '{ent_mv.name}' added to inventory."})
                                discovered_item_ids.append(ent_mv.id)
                            else:
                                old_scene = ent_mv.current_scene_id
                                resolved_target_scene_id = await _resolve_scene_id(db, state.adventure_id, move.to_scene_id)
                                ent_mv.current_scene_id = resolved_target_scene_id or ent_mv.current_scene_id
                                ent_mv.is_in_inventory = False
                                if old_scene == "INVENTORY":
                                    response_messages.append({"role": "system", "content": f"[System] Item '{ent_mv.name}' removed from inventory."})
                                else:
                                    response_messages.append({"role": "system", "content": f"[System] NPC '{ent_mv.name}' moved to {move.to_scene_id}."})
                            if move.to_spatial_position: ent_mv.spatial_position = move.to_spatial_position

                if game_event.updated_entities:
                    for upd in game_event.updated_entities:
                        ent_upd_res = await db.execute(select(WorldEntity).where(WorldEntity.id == upd.entity_id, WorldEntity.adventure_id == state.adventure_id))
                        ent_upd = ent_upd_res.scalars().first()
                        if ent_upd:
                            if upd.name: ent_upd.name = upd.name
                            if upd.description: ent_upd.description = upd.description
                            if upd.spatial_position: ent_upd.spatial_position = upd.spatial_position
                            if upd.is_hidden is not None: ent_upd.is_hidden = upd.is_hidden
                            if upd.hp is not None: ent_upd.hp = upd.hp
                            if upd.mana is not None: ent_upd.mana = upd.mana
                            if upd.stamina is not None: ent_upd.stamina = upd.stamina

                if game_event.deleted_entities:
                    for d_id in game_event.deleted_entities:
                        await db.execute(delete(WorldEntity).where(WorldEntity.id == d_id, WorldEntity.adventure_id == state.adventure_id))

                if game_event.new_inventory_items:
                    for item in game_event.new_inventory_items:
                        ent_sync_res = await db.execute(select(WorldEntity).where(WorldEntity.id == item.id, WorldEntity.adventure_id == state.adventure_id))
                        ent_sync = ent_sync_res.scalars().first()
                        if ent_sync:
                            ent_sync.is_in_inventory = True
                            ent_sync.is_hidden = False
                            new_inv = []
                            for inv_item in avatar.inventory:
                                updated_item = dict(inv_item)
                                if updated_item.get('id') == item.id and not updated_item.get('image_url'):
                                    updated_item['image_url'] = ent_sync.image_url
                                new_inv.append(updated_item)
                            avatar.inventory = new_inv
                            response_messages.append({"role": "system", "content": f"[System] Item '{item.name}' added to inventory."})
                            discovered_item_ids.append(ent_sync.id)
                        else:
                            new_ent = WorldEntity(
                                id=item.id or str(uuid.uuid4()), adventure_id=state.adventure_id,
                                entity_type="OBJECT", name=item.name, description=item.description,
                                current_scene_id="INVENTORY", is_in_inventory=True,
                                item_type=item.item_type or "PICKABLE", image_url=item.image_url
                            )
                            db.add(new_ent)
                            response_messages.append({"role": "system", "content": f"[System] New discovery: '{item.name}' added to inventory."})

                if game_event.updated_exits:
                    for upd in game_event.updated_exits:
                        ex_res = await db.execute(select(WorldExit).where(WorldExit.from_scene_id == upd.from_scene_id, WorldExit.to_scene_id == upd.to_scene_id, WorldExit.adventure_id == state.adventure_id))
                        world_exit = ex_res.scalars().first()
                        if world_exit: world_exit.is_locked = upd.is_locked

                if game_event.extra_time_minutes:
                    state.in_game_time += game_event.extra_time_minutes
                    response_messages.append({"role": "system", "content": f"[System] Time advancement: +{game_event.extra_time_minutes} minutes."})

                if game_event.time_override_minutes is not None:
                    state.in_game_time = game_event.time_override_minutes
                    response_messages.append({"role": "system", "content": f"[System] Time jump: clock set to {game_event.time_override_minutes} minutes from start."})

                if game_event.start_datetime_override:
                    if adventure.original_manifest:
                        # Update the manifest so it persists across resets/reloads
                        manifest = dict(adventure.original_manifest)
                        manifest["start_datetime"] = game_event.start_datetime_override
                        adventure.original_manifest = manifest
                    response_messages.append({"role": "system", "content": f"[System] Calendar shift: adventure start time updated to {game_event.start_datetime_override}."})

                if game_event.completed_quest_ids:
                    updated_quests = deepcopy(adventure.quests or [])
                    any_updated = False
                    for q_id in game_event.completed_quest_ids:
                        for q in updated_quests:
                            if q.get("id") == q_id and q.get("status", "open") == "open":
                                q["status"] = "completed"
                                avatar.exp += q.get("exp_reward", 0)
                                response_messages.append({"role": "system", "content": f"[QUEST COMPLETED] {q.get('title', 'Unknown Quest')} (+{q.get('exp_reward', 0)} EXP)"})
                                any_updated = True
                    if any_updated:
                        adventure.quests = updated_quests
                        flag_modified(adventure, "quests")
                        main_quests = [q for q in updated_quests if q.get("is_main")]
                        if main_quests and all(q.get("status", "open") == "completed" for q in main_quests):
                            adventure.is_completed = True
                            response_messages.append({"role": "system", "content": "[ADVENTURE COMPLETED] All main objectives achieved!"})

                if state.is_debug_enabled:
                    debug_payload = game_event.model_dump(exclude={'narrative_description'})
                    content = f"**[DEBUG] MECHANICAL OUTCOME:**\n```json\n{json.dumps(debug_payload, indent=2)}\n```"
                    yield f"event: system\ndata: {json.dumps(jsonable_encoder({'role': 'assistant', 'content': content, 'is_debug': True}))}\n\n"

                yield f"event: status\ndata: {json.dumps(jsonable_encoder({'content': 'Generating narrative...'}))}\n\n"

                # --- Pass 2: Atmospheric Narration ---
                # Ensure LLM uses complex model settings for Pass 2 (Narration)
                llm = GameMasterLLM(user, provider=complex_model_provider, model_category="complex")
                
                narration_system_prompt = system_prompt + "\n\n" + prompts.GM_NARRATION_TECHNICAL_OUTCOME_PREFIX.format(
                    outcome_json=game_event.model_dump_json(exclude={'narrative_description'})
                )
                is_new_scene = bool(game_event.new_scene_id and game_event.new_scene_id != state.scene_id)
                is_detailed_request = any(word in user_msg.lower() for word in ["look", "examine", "describe", "search", "details"])
                
                if is_new_scene: narration_system_prompt += prompts.GM_NARRATION_NEW_LOCATION_SUFFIX
                elif is_detailed_request: narration_system_prompt += prompts.GM_NARRATION_DETAILED_REQUEST_SUFFIX
                else: narration_system_prompt += prompts.GM_NARRATION_SNAPPY_SUFFIX

                narration_system_prompt += f"\n{prompts.GM_NARRATION_MANDATORY_FORMATTING}"
                
                if state.is_debug_enabled:
                    req_content = f"**[DEBUG] NARRATION REQUEST (Pass 2):**\n**System Prompt:**\n```text\n{narration_system_prompt}\n```\n**User Prompt:**\n```text\n{user_msg}\n```"
                    yield f"event: system\ndata: {json.dumps(jsonable_encoder({'role': 'assistant', 'content': req_content, 'is_debug': True}))}\n\n"

                for sys_msg in response_messages:
                    yield f"event: system\ndata: {json.dumps(jsonable_encoder(sys_msg))}\n\n"

                if game_over:
                    response_text = game_over_reason
                    yield f"event: chunk\ndata: {json.dumps(jsonable_encoder({'content': response_text}))}\n\n"
                else:
                    stream = await llm.stream_simple_task(
                        system_prompt=narration_system_prompt, user_prompt=user_msg, model=complex_model,
                        adventure_id=state.adventure_id, game_id=game_id, operation="chat_turn", phase="narration"
                    )
                    async for chunk in stream:
                        delta = chunk.choices[0].delta.content or ""
                        if delta:
                            response_text += delta
                            yield f"event: chunk\ndata: {json.dumps(jsonable_encoder({'content': delta}))}\n\n"
                    
                response_text = _sanitize_narrative_response(response_text, fallback=game_event.narrative_description)

            else:
                freeform_system_prompt = system_prompt
                if adventure.rule_enforcement_mode == "chat":
                    freeform_system_prompt += f"\n\n{prompts.GM_CHAT_NARRATION_SUFFIX}"
                
                for sys_msg in response_messages:
                    yield f"event: system\ndata: {json.dumps(jsonable_encoder(sys_msg))}\n\n"

                stream = await llm.stream_simple_task(
                    freeform_system_prompt, user_msg, complex_model,
                    adventure_id=state.adventure_id, game_id=game_id, operation="chat_turn", phase="freeform"
                )
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        response_text += delta
                        yield f"event: chunk\ndata: {json.dumps({'content': delta})}\n\n"
                response_text = _sanitize_narrative_response(response_text)

            assistant_chat = ChatMessage(game_state_id=game_id, role="assistant", content=response_text)
            db.add(assistant_chat)

            map_res = await db.execute(select(WorldMap).where(WorldMap.adventure_id == state.adventure_id))
            world_map = map_res.scalars().first()
            if not world_map:
                world_map = WorldMap(adventure_id=state.adventure_id)
                db.add(world_map)

            scene_res = await db.execute(select(WorldScene).where(WorldScene.id == state.scene_id, WorldScene.adventure_id == state.adventure_id))
            current_scene = scene_res.scalars().first()

            MapEngine.register_visit(
                world_map, state.scene_id, 
                label=(game_event.scene_label if game_event and game_event.scene_label else (current_scene.label if current_scene else None)),
                description=(current_scene.description if current_scene else None),
                image_url=(current_scene.image_url if current_scene else None)
            )
            room_exits_res = await db.execute(select(WorldExit).where(WorldExit.from_scene_id == state.scene_id, WorldExit.adventure_id == state.adventure_id))
            for ex in room_exits_res.scalars().all():
                MapEngine.register_exit(world_map, ex.from_scene_id, ex.to_scene_id, exit_label=ex.label, is_locked=ex.is_locked)
            
            if adventure.strict_rules and game_event and game_event.image_prompt and payload.auto_visualize:
                try:
                    image_url = await MediaEngine.generate_scene_image(
                        game_event.image_prompt, adventure.id, {"t2i_settings": user.t2i_settings}, user.encrypted_api_keys
                    )
                    if current_scene: current_scene.image_url = image_url
                    MapEngine.register_visit(world_map, state.scene_id, image_url=image_url)
                except Exception as e:
                    logger.error(f"On-demand scene generation failed: {e}")

            await db.commit()
            
            curr_ent_res = await db.execute(select(WorldEntity).where(
                WorldEntity.adventure_id == state.adventure_id, 
                WorldEntity.current_scene_id == state.scene_id,
                WorldEntity.is_in_inventory == False,
                WorldEntity.is_hidden == False
            ))
            curr_entities = [{c.name: getattr(e, c.name) for c in e.__table__.columns} for e in curr_ent_res.scalars().all()]

            yield f"event: final\ndata: {json.dumps(jsonable_encoder({
                'sheet': await _build_sheet_snapshot(avatar, state, db),
                'mermaid': MapEngine.to_mermaid(world_map),
                'nodes': await _enrich_map_nodes(state.adventure_id, world_map.nodes if world_map else {}, db),
                'image_url': image_url or (current_scene.image_url if current_scene else None),
                'entities': curr_entities,
                'npc_metadata': await _get_npc_metadata(state.adventure_id, db),
                'game_over': game_over,
                'game_over_reason': game_over_reason,
                'adventure_image': adventure.image_url if adventure else None,
                'quests': adventure.quests,
                'is_completed': adventure.is_completed,
                'discovered_item_ids': discovered_item_ids
            }))}\n\n"

        except Exception as e:
            logger.exception("Chat processing error")
            msg = str(e)
            # If it's a known LLM/Provider error, send the specific message
            if any(x in msg.lower() for x in ["litellm", "openai", "provider", "model", "notfounderror"]):
                detail = msg
            else:
                detail = "The Game Master is momentarily unavailable."
                
            yield f"event: error\ndata: {json.dumps(jsonable_encoder({'detail': detail}))}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
