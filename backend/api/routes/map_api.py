from typing import Optional, Union
"""
REST endpoints for the World Map.

GET  /api/adventures/{template_id}/map          — returns raw graph JSON
POST /api/adventures/{template_id}/map/visit    — register a scene visit (internal / debug)
POST /api/adventures/{template_id}/map/exit     — register an exit between scenes
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.logic import AdventureLogic
from backend.core.database import get_db
from backend.engine.map_engine import MapEngine
from backend.models.adventure_template import AdventureTemplate
from backend.models.world_map import WorldMap
from backend.models.world_entity import WorldExit

router = APIRouter(tags=["WorldMap"])
logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class VisitPayload(BaseModel):
    scene_id: str
    label: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None


class ExitPayload(BaseModel):
    from_scene: str
    to_scene: str
    exit_label: Optional[str] = ""


# ── Route helpers ─────────────────────────────────────────────────────────────

# _get_or_create_map moved to AdventureLogic.get_or_create_map


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/adventures/{template_id}/map")
async def get_map(template_id: str, session_id: Optional[str] = None, db: AsyncSession = Depends(get_db)) -> dict:
    """Return the raw scene-graph JSON (nodes + edges)."""
    world_map = await AdventureLogic.get_or_create_map(db, template_id, session_id=session_id)
    if not world_map:
        return {"nodes": {}, "edges": [], "current_scene_id": None}

    map_dict = MapEngine.to_dict(world_map)
    
    # Augment with adjacent unvisited scenes
    if world_map.current_scene_id:
        # Find the raw ID for the current scene (stored in metadata)
        current_node = world_map.nodes.get(world_map.current_scene_id)
        raw_current_id = current_node.get("id") if current_node else None
        
        if raw_current_id:
            # Fetch exits for this session or template
            exit_query = select(WorldExit).where(
                or_(
                    WorldExit.session_id == session_id,
                    WorldExit.template_id == template_id
                )
            )
            exits_res = await db.execute(exit_query)
            exits = list(exits_res.scalars().all())
            
            map_dict = MapEngine.augment_map_data(map_dict, exits, raw_current_id)

    return map_dict


@router.post("/adventures/{template_id}/map/visit", status_code=200)
async def post_visit(
    template_id: str,
    payload: VisitPayload,
    session_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Register a scene visit — upserts the node and sets it as current."""
    # Validate adventure exists
    adv = await db.execute(select(AdventureTemplate).where(AdventureTemplate.id == template_id))
    if not adv.scalars().first():
        raise HTTPException(status_code=404, detail="AdventureTemplate not found.")

    world_map = await AdventureLogic.get_or_create_map(db, template_id, session_id=session_id)
    MapEngine.register_visit(
        world_map, 
        payload.scene_id, 
        payload.label, 
        payload.description,
        payload.image_url
    )
    await db.commit()
    return {"status": "ok", "current_scene_id": payload.scene_id}


@router.post("/adventures/{template_id}/map/exit", status_code=200)
async def post_exit(
    template_id: str,
    payload: ExitPayload,
    session_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Register a directed exit between two scenes."""
    world_map = await AdventureLogic.get_or_create_map(db, template_id, session_id=session_id)
    MapEngine.register_exit(world_map, payload.from_scene, payload.to_scene, payload.exit_label or "")
    await db.commit()
    return {"status": "ok"}

