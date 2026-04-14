import logging
import uuid
from copy import deepcopy
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from pydantic import BaseModel

from backend.core.database import get_db
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
from backend.engine.rule_engine import RuleEngine, GameEvent, GameOverException
from backend.engine.map_engine import MapEngine
from backend.engine.media_engine import MediaEngine
from backend.engine.memory_manager import MemoryManager
from backend.engine.debug_engine import DebugEngine
from backend.core.llm_router import GameMasterLLM

router = APIRouter(prefix="/adventures", tags=["Adventures"])
logger = logging.getLogger(__name__)


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
    generate_npc_images: bool = False
    generate_item_images: bool = False
    time_per_turn: int = 5
    heartbeat_enabled: Optional[bool] = False
    heartbeat_interval: Optional[int] = None
    game_over_rules: Optional[Dict[str, Any]] = None
    # Advanced/import fields
    original_manifest: Optional[Dict[str, Any]] = None
    automatic_cover_generation: Optional[bool] = False
    pacing: Optional[Dict[str, Any]] = None


class AdventureResponse(BaseModel):
    """Full adventure details returned to the client."""
    id: str
    title: str
    strict_rules: bool
    time_per_turn: int
    heartbeat_enabled: bool
    heartbeat_interval: Optional[int] = None
    game_over_rules: Optional[Dict[str, Any]]
    context: Optional[str] = None

    class Config:
        from_attributes = True


class GameSessionResponse(BaseModel):
    """Summary of a game session (GameState + linked entities)."""
    game_id: str
    adventure_id: str
    avatar_id: str
    adventure_title: str
    image_url: Optional[str] = None
    scene_id: str
    in_game_time: int
    is_paused: bool

class ChatResponse(BaseModel):
    """Unified response for a game turn."""
    messages: List[Dict[str, str]] # [{'role': '...', 'content': '...'}]
    sheet: Dict[str, Any]
    mermaid: Optional[str] = None
    nodes: Optional[Dict[str, Any]] = None # Metadata for nodes
    image_url: Optional[str] = None
    entities: List[Dict[str, Any]] = []
    game_over: bool = False
    game_over_reason: Optional[str] = None

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
) -> dict:
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()
    if not user:
        user = User(username="local_default_user")
        db.add(user)
        await db.flush()

    # Create placeholder adventure
    # Allow server-side id generation if client didn't provide one
    adv_kwargs = dict(
        title=payload.title,
        image_url=payload.image_url,
        context=payload.context,
        strict_rules=payload.strict_rules,
        time_per_turn=payload.time_per_turn,
        game_over_rules=payload.game_over_rules,
        is_ready=False,
        creation_status="Initializing Foundations...",
        heartbeat_enabled=bool(payload.heartbeat_enabled)
    )

    if payload.heartbeat_interval is not None:
        adv_kwargs["heartbeat_interval"] = int(payload.heartbeat_interval)

    adv = Adventure(**adv_kwargs)
    db.add(adv)
    await db.flush()
    # Create a minimal placeholder Avatar which will be populated by WorldGenerator
    avatar_name = payload.avatar_name or "You"
    avatar = Avatar(
        user_id=user.id,
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
    # Create initial GameState so the session is visible immediately to clients/tests
    db.add(GameState(
        id=adv.id,
        user_id=user.id,
        adventure_id=adv.id,
        avatar_id=avatar.id,
        scene_id="START",
        in_game_time=0
    ))
    await db.commit()

    # Store original_manifest if provided and dispatch generation with payload
    if getattr(payload, 'original_manifest', None):
        adv.original_manifest = payload.original_manifest

    await db.commit()

    # Prepare payload for background generation; include original_manifest if present
    bg_payload = payload.model_dump()
    background_tasks.add_task(run_background_generation, adv.id, user.id, bg_payload)
    
    # Return IDs expected by existing clients/tests
    return {"game_id": adv.id, "adventure_id": adv.id, "avatar_id": avatar.id}

async def run_background_generation(adventure_id: str, user_id: str, payload_dict: dict):
    """Background task for world gen, scene init, and auto-cleanup on failure."""
    from backend.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            # Re-fetch user in this session; if DB schema isn't fully migrated, abort gracefully
            try:
                result = await db.execute(select(User).where(User.id == user_id))
                user = result.scalars().first()
                if not user:
                    logger.warning("Background Gen: user not found for %s", user_id)
                    return
            except Exception as e:
                logger.error("Background Gen user fetch failed for %s: %s", user_id, e)
                return

            llm_settings = user.llm_settings or {}
            complex_model = llm_settings.get("complex_model", "gpt-4o")
            preferred_provider = llm_settings.get("preferred_provider", "openai")
            adv_for_context = await db.get(Adventure, adventure_id)
            source_manifest = (adv_for_context.original_manifest if adv_for_context else None) or payload_dict.get("original_manifest")
            normalized_manifest = _normalize_manifest_for_world_generator(source_manifest)
            initial_scene_id = normalized_manifest["scenes"][0]["id"] if normalized_manifest else None
            
            # 1. World Gen
            adventure_context = payload_dict.get('context')
            if not adventure_context:
                manifest = (adv_for_context.original_manifest or {}) if adv_for_context else {}
                adventure_context = manifest.get('story_idea') or manifest.get('description') or "A standard fantasy world."

            if normalized_manifest:
                if adv_for_context:
                    adv_for_context.creation_status = "Applying Imported Manifest..."
                    await db.commit()

                await WorldGenerator.apply_manifest(
                    db=db,
                    adventure_id=adventure_id,
                    manifest_dict=normalized_manifest,
                    user=user if (payload_dict.get('generate_npc_images', False) or payload_dict.get('generate_item_images', False)) else None,
                    gen_npc=payload_dict.get('generate_npc_images', False),
                    gen_items=payload_dict.get('generate_item_images', False),
                    gen_protagonist_image=True,
                )
            else:
                await WorldGenerator.generate_world(
                    db=db,
                    user=user,
                    adventure_id=adventure_id,
                    title=payload_dict['title'],
                    context=adventure_context,
                    model=complex_model,
                    provider=preferred_provider,
                    generate_npc_images=payload_dict.get('generate_npc_images', False),
                    generate_item_images=payload_dict.get('generate_item_images', False)
                )
            
            # 2. Initial GameState
            scenes_res = await db.execute(select(WorldScene).where(WorldScene.adventure_id == adventure_id))
            scenes = scenes_res.scalars().all()
            if not scenes: raise ValueError("Engine failed to sprout any locations.")
            
            # Get Avatar ID
            avatar_res = await db.execute(select(Avatar).where(Avatar.adventure_id == adventure_id))
            avatar = avatar_res.scalars().first()
            
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
            
            # 3. Mark Ready
            adv = await db.get(Adventure, adventure_id)
            if adv:
                adv.is_ready = True
                adv.creation_status = "Ready"
            
            await db.commit()
            
        except Exception as e:
            logger.error("Background Gen Failed for %s: %s", adventure_id, e)
            try:
                await db.rollback()
                # Do not auto-delete adventures during background failures in tests.
                adv = await db.get(Adventure, adventure_id)
                if adv:
                    adv.creation_status = "Generation Failed"
                    adv.creation_error = str(e)
                    await db.commit()
            except Exception:
                pass

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


@router.get("", response_model=List[GameSessionResponse])
async def list_adventures(db: AsyncSession = Depends(get_db)) -> list:
    """Returns all game sessions with their linked adventure and avatar IDs."""
    result = await db.execute(
        select(GameState, Adventure)
        .join(Adventure, GameState.adventure_id == Adventure.id)
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
            in_game_time=s.in_game_time,
            is_paused=s.is_paused,
        )
        for s, a in rows
    ]


@router.get("/{adventure_id}", response_model=AdventureResponse)
async def get_adventure(adventure_id: str, db: AsyncSession = Depends(get_db)) -> Adventure:
    """Returns the details of a single adventure by its ID."""
    result = await db.execute(select(Adventure).where(Adventure.id == adventure_id))
    adv = result.scalars().first()
    if not adv:
        raise HTTPException(status_code=404, detail="Adventure not found.")
    return adv


@router.post("/import", status_code=201)
async def import_adventure(
    payload: AdventureImportPayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Import an adventure manifest (versioned .ADV JSON). Opens an adventure scaffold and starts background generation."""
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()
    if not user:
        user = User(username="local_default_user")
        db.add(user)
        await db.flush()

    adv_kwargs = dict(
        title=payload.title,
        image_url=None,
        context=payload.story_idea or payload.description or payload.subtitle,
        strict_rules=True,
        time_per_turn=payload.time_per_turn or 5,
        game_over_rules=None,
        is_ready=False,
        creation_status="Importing Manifest...",
        heartbeat_enabled=False,
        original_manifest=payload.model_dump()
    )

    adv = Adventure(**adv_kwargs)
    db.add(adv)
    await db.flush()

    avatar_name = None
    if payload.protagonist and payload.protagonist.name:
        avatar_name = payload.protagonist.name
    avatar_name = avatar_name or "You"

    avatar = Avatar(
        user_id=user.id,
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
        user_id=user.id,
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
        "pacing": payload.pacing.model_dump() if payload.pacing else None,
        "start_date": payload.start_date,
        "start_time": payload.start_time,
        "start_datetime": payload.start_datetime,
        "original_manifest": payload.model_dump(),
    }

    background_tasks.add_task(run_background_generation, adv.id, user.id, payload_dict)

    return {"game_id": adv.id, "adventure_id": adv.id, "avatar_id": avatar.id}


@router.patch("/{adventure_id}", response_model=AdventureResponse)
async def update_adventure(
    adventure_id: str,
    payload: AdventureUpdate,
    db: AsyncSession = Depends(get_db),
) -> Adventure:
    """
    Partially updates an adventure's configuration (title, rules, heartbeat settings).
    Only provided fields are updated.
    """
    result = await db.execute(select(Adventure).where(Adventure.id == adventure_id))
    adv = result.scalars().first()
    if not adv:
        raise HTTPException(status_code=404, detail="Adventure not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(adv, field, value)

    await db.commit()
    await db.refresh(adv)
    logger.info("Updated adventure %s: %s", adventure_id, update_data)
    return adv


@router.delete("/{adventure_id}", status_code=204)
async def delete_adventure(adventure_id: str, db: AsyncSession = Depends(get_db)) -> None:
    """
    Deletes an adventure and its associated game state.
    Returns 204 No Content on success.
    """
    result = await db.execute(select(Adventure).where(Adventure.id == adventure_id))
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
    logger.info("Deleted adventure %s", adventure_id)


# ---------------------------------------------------------------------------
# Game-State sub-routes
# ---------------------------------------------------------------------------

@router.get("/{adventure_id}/state", response_model=GameSessionResponse)
async def get_game_state(adventure_id: str, db: AsyncSession = Depends(get_db)) -> GameSessionResponse:
    """Returns the current game state for a given adventure."""
    result = await db.execute(
        select(GameState).where(GameState.adventure_id == adventure_id)
    )
    state = result.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="Game state not found.")
    # Fetch linked adventure for title and image
    adv = await db.get(Adventure, state.adventure_id)
    return GameSessionResponse(
        game_id=state.id,
        adventure_id=state.adventure_id,
        avatar_id=state.avatar_id,
        adventure_title=adv.title if adv else "",
        image_url=adv.image_url if adv else None,
        scene_id=state.scene_id,
        in_game_time=state.in_game_time,
        is_paused=state.is_paused,
    )


@router.patch("/{adventure_id}/state")
async def update_game_state(
    adventure_id: str,
    payload: GameStateUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Updates scene_id or in_game_time for the active game state of an adventure."""
    result = await db.execute(
        select(GameState).where(GameState.adventure_id == adventure_id)
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
async def pause_game(adventure_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Pauses the heartbeat processing for a game session."""
    result = await db.execute(
        select(GameState).where(GameState.adventure_id == adventure_id)
    )
    state = result.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="Game state not found.")
    state.is_paused = True
    await db.commit()
    return {"status": "paused", "game_id": state.id}


@router.post("/{adventure_id}/resume")
async def resume_game(adventure_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Resumes heartbeat processing for a paused game session."""
    result = await db.execute(
        select(GameState).where(GameState.adventure_id == adventure_id)
    )
    state = result.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="Game state not found.")
    state.is_paused = False
    await db.commit()
    return {"status": "resumed", "game_id": state.id}

@router.get("/{adventure_id}/debug", response_model=AdventureDebugResponse)
async def get_adventure_debug(adventure_id: str, db: AsyncSession = Depends(get_db)):
    """
    Returns full world state and configuration for a specific adventure.
    """
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
    
    # Return serializable dicts
    return AdventureDebugResponse(
        adventure={c.name: getattr(adventure, c.name) for c in adventure.__table__.columns},
        scenes=[{c.name: getattr(s, c.name) for c in s.__table__.columns} for s in scenes],
        npcs=[{c.name: getattr(ent, c.name) for c in ent.__table__.columns} for ent in entities if ent.entity_type == "NPC"],
        objects=[{c.name: getattr(ent, c.name) for c in ent.__table__.columns} for ent in entities if ent.entity_type == "OBJECT"],
        exits=[{c.name: getattr(ex, c.name) for c in ex.__table__.columns} for ex in exits]
    )

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
    manifest.setdefault("version", "1.0")
    manifest.setdefault("id", adventure.id)
    manifest.setdefault("title", adventure.title)

    if not manifest.get("story_idea") and adventure.context:
        manifest["story_idea"] = adventure.context
    if not manifest.get("description") and adventure.context:
        manifest["description"] = adventure.context

    if not manifest.get("time_per_turn"):
        manifest["time_per_turn"] = adventure.time_per_turn

    manifest.setdefault("generate_npc_images", False)
    manifest.setdefault("generate_item_images", False)
    manifest.setdefault("automatic_cover_generation", False)

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
        "version": "1.0",
        "type": "SESSION_BUNDLE",
        "adventure": {c.name: getattr(adventure, c.name) for c in adventure.__table__.columns},
        "scenes": [{c.name: getattr(s, c.name) for c in s.__table__.columns} for s in scene_res.scalars().all()],
        "exits": [{c.name: getattr(e, c.name) for c in e.__table__.columns} for e in exit_res.scalars().all()],
        "entities": [{c.name: getattr(ent, c.name) for c in ent.__table__.columns} for ent in entity_res.scalars().all()],
        "game_state": {c.name: getattr(state, c.name) for c in state.__table__.columns} if state else None,
        "avatar": {c.name: getattr(avatar, c.name) for c in avatar.__table__.columns} if avatar else None,
        "chat_history": [{c.name: getattr(msg, c.name) for c in msg.__table__.columns} for msg in chat_logs]
    }

@router.post("/import/session-bundle")
async def import_adventure_session_bundle(payload: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    """
    Imports an adventure from JSON.
    Supports either a Raw Manifest or a Full Session Bundle.
    """
    res = await db.execute(select(User).limit(1))
    user = res.scalars().first()
    if not user:
        user = User(username="default_player")
        db.add(user)
        await db.flush()

    # Determine if this is a Session Bundle or just a Manifest
    is_session = payload.get("type") == "SESSION_BUNDLE"
    
    if is_session:
        # --- Handle Session Bundle ---
        data = payload
        old_adv = data["adventure"]
        
        # 1. Recreate Adventure
        new_adv = Adventure(
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
        
    # 3. Enrich equipment
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

@router.get("/{game_id}/chat", response_model=ChatResponse)
async def get_chat_history(game_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieves full chat history and current session state."""
    state_res = await db.execute(select(GameState).where(GameState.id == game_id))
    state = state_res.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")
        
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
    
    return ChatResponse(
        messages=history,
        sheet=await _build_sheet_snapshot(avatar, state, db),
        mermaid=mermaid_data,
        nodes=await _enrich_map_nodes(state.adventure_id, world_map.nodes if world_map else {}, db),
        entities=entities
    )

@router.post("/{game_id}/chat", response_model=ChatResponse)
async def post_chat_message(
    game_id: str,
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Unified game turn endpoint. Processes user input (natural language or slash command),
    advances world state, and returns all updates.
    """
    user_msg = payload.content.strip()
    
    # 1. Load context
    state_res = await db.execute(select(GameState).where(GameState.id == game_id))
    state = state_res.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="Game session not found.")

    if state.is_paused:
        # We need to fetch the avatar if it's not already there for the snapshot
        if 'avatar' not in locals():
            av_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
            avatar = av_res.scalars().first()

        return ChatResponse(
            messages=[{"role": "system", "content": "The game is currently paused."}],
            sheet=await _build_sheet_snapshot(avatar, state, db) if avatar else {}
        )

    av_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
    avatar = av_res.scalars().first()
    
    u_res = await db.execute(select(User).where(User.id == state.user_id))
    user = u_res.scalars().first()

    adv_res = await db.execute(select(Adventure).where(Adventure.id == state.adventure_id))
    adventure = adv_res.scalars().first()

    response_messages = []
    mermaid_data = None
    image_url = None
    game_over = False
    game_over_reason = None

    # --- Fresh Entry / Re-orientation Check ---
    msg_count_res = await db.execute(select(ChatMessage).where(ChatMessage.game_state_id == game_id).limit(1))
    is_first_message = msg_count_res.scalars().first() is None
    
    # If it's a [LOOK AROUND] trigger or a completely new start
    actual_user_input = user_msg
    if not user_msg:
        user_msg = "[LOOK AROUND]"

    # --- Handle Debug Commands ---
    if user_msg.startswith("/debug"):
        cmd_args = user_msg[7:].strip()
        debug_info = await DebugEngine.handle_debug_command(db, state, cmd_args)
        return ChatResponse(
            messages=[{"role": "system", "content": debug_info}],
            sheet=await _build_sheet_snapshot(avatar, state, db)
        )

    # --- Slash-command fast path ---
    if user_msg.startswith("/"):
        if user_msg.strip().lower() == "/map":
            map_res = await db.execute(select(WorldMap).where(WorldMap.adventure_id == state.adventure_id))
            world_map = map_res.scalars().first()
            mermaid_data = MapEngine.to_mermaid(world_map) if world_map else None
            return ChatResponse(messages=[], sheet=await _build_sheet_snapshot(avatar, state, db), mermaid=mermaid_data)
        
        response = CommandParser.parse_command(avatar, user_msg)
        
        if response == "[TRIGGER_COMBINE]":
            # Let the message fall through to the LLM to decide the outcome
            user_msg = f"[COMBINE ACTION] {user_msg}"
        else:
            await db.commit()
            return ChatResponse(
                messages=[{"role": "system", "content": response}],
                sheet=await _build_sheet_snapshot(avatar, state, db)
            )

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

    # Fetch pre-generated entities for context
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
    system_prompt = context_messages[0]["content"]

    # --- LLM Processing ---
    settings = user.llm_settings or {}
    small_model = settings.get("small_model", "openai/gpt-4o-mini")
    complex_model = settings.get("complex_model", "openai/gpt-4o-mini")
    provider = settings.get("preferred_provider", "openai")
    
    llm = GameMasterLLM(user, provider=provider)
    game_event = None
    response_text = ""

    try:
        if adventure.strict_rules:
            # --- PASS 1: Technical Reasoning (Small Model) ---
            # We ask the small model to decide the technical outcomes (GameEvent)
            # focusing on IDs, resources, and world state.
            mechanics_system_prompt = system_prompt + "\n\nCRITICAL: Focus on logical consistency and mechanics. Your 'narrative_description' will be used as a draft/log; keep it short."
            game_event = llm.execute_complex_task(
                system_prompt=mechanics_system_prompt,
                user_prompt=user_msg,
                response_model=GameEvent,
                model=small_model
            )

            # --- PASS 2: Atmospheric Narration (Complex Model) ---
            # We use the complex model to turn the technical outcome into premium prose.
            narration_system_prompt = system_prompt + f"\n\nTECHNICAL OUTCOME TO NARRATE: {game_event.model_dump_json(exclude={'narrative_description'})}\n"
            
            # Determine target length
            is_new_scene = bool(game_event.new_scene_id and game_event.new_scene_id != state.scene_id)
            is_detailed_request = any(word in user_msg.lower() for word in ["look", "examine", "describe", "search", "details"])
            
            if is_new_scene:
                narration_system_prompt += "The player moved to a NEW location. Write a rich, atmospheric introduction (2-3 paragraphs). Describe the architecture, smell, and general mood."
            elif is_detailed_request:
                narration_system_prompt += "The player is looking for details. Provide a very detailed physical description of the surroundings or objects mentioned."
            else:
                narration_system_prompt += "Keep the response snappy and punchy (1 short paragraph). Move the action forward without excessive flowery prose."

            narration_system_prompt += "\nDo not mention numbers, IDs, or system terms. Use English. 1-3 paragraphs based on the context above."
            narration_system_prompt += "\n\nMANDATORY FORMATTING: Start all character dialogue on a NEW LINE. Use the format: **Character Name:** \"Dialogue\". Separate narrative prose from speech with a blank line."
            
            response_text = llm.execute_simple_task(
                system_prompt=narration_system_prompt,
                user_prompt=user_msg,
                model=complex_model
            )
            
            # Apply mechanics to avatar, but use the complex narration for the final output
            try:
                # We ignore the small model's narrative draft and use the complex one
                RuleEngine.apply_event(avatar, game_event)
            except GameOverException as exc:
                game_over = True
                game_over_reason = str(exc)
                response_text = str(exc)
        else:
            # Free-form narrative always uses the high-quality complex model
            response_text = llm.execute_simple_task(system_prompt, user_msg, complex_model)

        # Record Assistant Message
        assistant_chat = ChatMessage(game_state_id=game_id, role="assistant", content=response_text)
        db.add(assistant_chat)
        response_messages.append({"role": "assistant", "content": response_text})

        # --- Update World State ---
        if adventure.strict_rules and game_event:
            if game_event.new_scene_id:
                resolved_scene_id = await _resolve_scene_id(db, state.adventure_id, game_event.new_scene_id)
                if resolved_scene_id:
                    state.scene_id = resolved_scene_id
                else:
                    logger.warning(
                        "Unresolved new_scene_id '%s' for adventure %s; staying in scene %s",
                        game_event.new_scene_id,
                        state.adventure_id,
                        state.scene_id,
                    )

            if game_event.moved_entities:
                for move in game_event.moved_entities:
                    ent_mv_res = await db.execute(
                        select(WorldEntity).where(
                            WorldEntity.id == move.entity_id,
                            WorldEntity.adventure_id == state.adventure_id,
                        )
                    )
                    ent_mv = ent_mv_res.scalars().first()
                    if ent_mv:
                        if move.to_scene_id == "INVENTORY":
                            ent_mv.is_in_inventory = True
                            response_messages.append({"role": "system", "content": f"[System] Item '{ent_mv.name}' added to inventory."})
                        else:
                            old_scene = ent_mv.current_scene_id
                            resolved_target_scene_id = await _resolve_scene_id(db, state.adventure_id, move.to_scene_id)
                            if move.to_scene_id and not resolved_target_scene_id:
                                logger.warning(
                                    "Unresolved move target '%s' for entity %s in adventure %s; keeping current scene %s",
                                    move.to_scene_id,
                                    move.entity_id,
                                    state.adventure_id,
                                    ent_mv.current_scene_id,
                                )
                            ent_mv.current_scene_id = resolved_target_scene_id or ent_mv.current_scene_id
                            ent_mv.is_in_inventory = False
                            if old_scene == "INVENTORY":
                                response_messages.append({"role": "system", "content": f"[System] Item '{ent_mv.name}' removed from inventory."})

                        if move.to_spatial_position:
                            ent_mv.spatial_position = move.to_spatial_position

            if game_event.updated_entities:
                for upd in game_event.updated_entities:
                    ent_upd_res = await db.execute(select(WorldEntity).where(WorldEntity.id == upd.entity_id, WorldEntity.adventure_id == state.adventure_id))
                    ent_upd = ent_upd_res.scalars().first()
                    if ent_upd:
                        if upd.name: ent_upd.name = upd.name
                        if upd.description: ent_upd.description = upd.description
                        if upd.spatial_position: ent_upd.spatial_position = upd.spatial_position
                        if upd.is_hidden is not None: ent_upd.is_hidden = upd.is_hidden

            if game_event.deleted_entities:
                for d_id in game_event.deleted_entities:
                    await db.execute(delete(WorldEntity).where(WorldEntity.id == d_id, WorldEntity.adventure_id == state.adventure_id))

            if game_event.new_inventory_items:
                # If the LLM generates a brand NEW item (not an existing world entity), 
                # we should still consider syncing it if it has an ID
                for item in game_event.new_inventory_items:
                    ent_sync_res = await db.execute(select(WorldEntity).where(WorldEntity.id == item.id, WorldEntity.adventure_id == state.adventure_id))
                    ent_sync = ent_sync_res.scalars().first()
                    
                    if ent_sync:
                        ent_sync.is_in_inventory = True
                        ent_sync.is_hidden = False

                        # BACKFILL image_url into the avatar's inventory if missing (with persistence fix)
                        new_inv = []
                        for inv_item in avatar.inventory:
                            updated_item = dict(inv_item) # Copy to ensure change detection
                            if updated_item.get('id') == item.id and not updated_item.get('image_url'):
                                updated_item['image_url'] = ent_sync.image_url
                            new_inv.append(updated_item)
                        avatar.inventory = new_inv

                        response_messages.append({"role": "system", "content": f"[System] Item '{item.name}' added to inventory."})
                    else:
                        # CREATE brand new entity for runtime items
                        new_ent = WorldEntity(
                            id=item.id or str(uuid.uuid4()),
                            adventure_id=state.adventure_id,
                            entity_type="OBJECT",
                            name=item.name,
                            description=item.description,
                            current_scene_id="INVENTORY", # Mark as in inventory
                            is_in_inventory=True,
                            item_type=item.item_type or "PICKABLE",
                            image_url=item.image_url
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
                response_messages.append({"role": "system", "content": f"Gamemaster added +{game_event.extra_time_minutes} minutes."})

        # If we moved, refresh the current_scene record to get proper labels/images for the map
        if game_event and game_event.new_scene_id:
            scene_res = await db.execute(select(WorldScene).where(WorldScene.id == state.scene_id, WorldScene.adventure_id == state.adventure_id))
            current_scene = scene_res.scalars().first()

        MapEngine.register_visit(
            world_map, 
            state.scene_id, 
            label=(game_event.scene_label if game_event and game_event.scene_label else (current_scene.label if current_scene else None)),
            description=(current_scene.description if current_scene else None),
            image_url=(current_scene.image_url if current_scene else None)
        )
        room_exits_res = await db.execute(select(WorldExit).where(WorldExit.from_scene_id == state.scene_id, WorldExit.adventure_id == state.adventure_id))
        for ex in room_exits_res.scalars().all():
            MapEngine.register_exit(world_map, ex.from_scene_id, ex.to_scene_id, exit_label=ex.label, is_locked=ex.is_locked)
        
        mermaid_data = MapEngine.to_mermaid(world_map)
        
        # --- Media Generation ---
        if adventure.strict_rules and game_event and game_event.image_prompt and payload.auto_visualize:
            try:
                image_url = await MediaEngine.generate_scene_image(
                    game_event.image_prompt, 
                    adventure.id,  
                    {"t2i_settings": user.t2i_settings}, 
                    user.encrypted_api_keys
                )
                # Persist image to the world scene record
                if current_scene:
                    current_scene.image_url = image_url
                
                # Update map node immediately
                MapEngine.register_visit(world_map, state.scene_id, image_url=image_url)
                
            except Exception as e:
                logger.error(f"On-demand scene generation failed: {e}")
                # We do NOT fail the turn, just return no image
                image_url = None

        await db.commit()
        
        # Fetch current entities for the response (only show what is logically 'there')
        curr_ent_res = await db.execute(select(WorldEntity).where(
            WorldEntity.adventure_id == state.adventure_id, 
            WorldEntity.current_scene_id == state.scene_id,
            WorldEntity.is_in_inventory == False,
            WorldEntity.is_hidden == False
        ))
        curr_entities = [{c.name: getattr(e, c.name) for c in e.__table__.columns} for e in curr_ent_res.scalars().all()]

        return ChatResponse(
            messages=[{"role": "system", "content": response_text}],
            sheet=await _build_sheet_snapshot(avatar, state, db),
            mermaid=mermaid_data,
            nodes=await _enrich_map_nodes(state.adventure_id, world_map.nodes if world_map else {}, db),
            image_url=image_url,
            entities=curr_entities,
            game_over=game_over,
            game_over_reason=game_over_reason
        )

    except Exception as e:
        logger.exception("Chat processing error")
        return ChatResponse(
            messages=[{"role": "system", "content": "The Game Master is momentarily unavailable. Please try again."}],
            sheet=await _build_sheet_snapshot(avatar, state, db) if 'avatar' in locals() else {}
        )
