"""
REST endpoints for the World Map.

GET  /api/adventures/{adventure_id}/map          — returns raw graph JSON
GET  /api/adventures/{adventure_id}/map/mermaid  — returns Mermaid diagram string
POST /api/adventures/{adventure_id}/map/visit    — register a scene visit (internal / debug)
POST /api/adventures/{adventure_id}/map/exit     — register an exit between scenes
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from backend.core.database import get_db
from backend.models.world_map import WorldMap
from backend.models.adventure import Adventure
from backend.engine.map_engine import MapEngine

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

async def _get_or_create_map(adventure_id: str, db: AsyncSession) -> WorldMap:
    """Fetch or lazily create a WorldMap row for the given adventure."""
    result = await db.execute(
        select(WorldMap).where(WorldMap.adventure_id == adventure_id)
    )
    world_map = result.scalars().first()
    if not world_map:
        world_map = WorldMap(adventure_id=adventure_id)
        db.add(world_map)
        await db.flush()
    return world_map


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/adventures/{adventure_id}/map")
async def get_map(adventure_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Return the raw scene-graph JSON (nodes + edges)."""
    result = await db.execute(
        select(WorldMap).where(WorldMap.adventure_id == adventure_id)
    )
    world_map = result.scalars().first()
    if not world_map:
        return {"nodes": {}, "edges": [], "current_scene_id": None}

    return {
        "nodes": world_map.nodes,
        "edges": world_map.edges,
        "current_scene_id": world_map.current_scene_id,
    }


@router.get("/adventures/{adventure_id}/map/mermaid")
async def get_mermaid(adventure_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Return the scene graph serialised as a Mermaid.js flowchart string and node metadata."""
    result = await db.execute(
        select(WorldMap).where(WorldMap.adventure_id == adventure_id)
    )
    world_map = result.scalars().first()
    if not world_map or not world_map.nodes:
        # Return a minimal Mermaid diagram that shows an empty state.
        return {
            "mermaid": 'flowchart LR\n  START["No map data yet..."]',
            "nodes": {}
        }

    return {
        "mermaid": MapEngine.to_mermaid(world_map),
        "nodes": world_map.nodes
    }


@router.post("/adventures/{adventure_id}/map/visit", status_code=200)
async def post_visit(
    adventure_id: str,
    payload: VisitPayload,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Register a scene visit — upserts the node and sets it as current."""
    # Validate adventure exists
    adv = await db.execute(select(Adventure).where(Adventure.id == adventure_id))
    if not adv.scalars().first():
        raise HTTPException(status_code=404, detail="Adventure not found.")

    world_map = await _get_or_create_map(adventure_id, db)
    MapEngine.register_visit(
        world_map, 
        payload.scene_id, 
        payload.label, 
        payload.description,
        payload.image_url
    )
    await db.commit()
    return {"status": "ok", "current_scene_id": payload.scene_id}


@router.post("/adventures/{adventure_id}/map/exit", status_code=200)
async def post_exit(
    adventure_id: str,
    payload: ExitPayload,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Register a directed exit between two scenes."""
    world_map = await _get_or_create_map(adventure_id, db)
    MapEngine.register_exit(world_map, payload.from_scene, payload.to_scene, payload.exit_label or "")
    await db.commit()
    return {"status": "ok"}
