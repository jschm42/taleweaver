"""
REST endpoints for the World Map.

GET  /api/adventures/{template_id}/map          — returns raw graph JSON
POST /api/adventures/{template_id}/map/visit    — register a scene visit (internal / debug)
POST /api/adventures/{template_id}/map/exit     — register an exit between scenes

All endpoints require authentication and are scoped to the owner of the
AdventureTemplate and, with ``session_id``, of that session (admins always allowed).
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.logic import AdventureLogic
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.engine.interaction.map_engine import MapEngine, load_map_exits
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User

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


async def _get_owned_adventure_or_404(
    db: AsyncSession, template_id: str, user_id: str, is_admin: bool
) -> AdventureTemplate:
    adv = await db.get(AdventureTemplate, template_id)
    if not adv or (adv.owner_id != user_id and not is_admin):
        raise HTTPException(status_code=404, detail="AdventureTemplate not found.")
    return adv


async def _authorize_map_access(
    db: AsyncSession, template_id: str, session_id: Optional[str], user: User
) -> None:
    """Owner (or admin) of the template, and of the session's map when one is named."""
    is_admin = user.role == "admin"
    await _get_owned_adventure_or_404(db, template_id, user.id, is_admin)
    if not session_id:
        return
    state = await AdventureLogic.resolve_session_state(
        db, session_id, user_id=None if is_admin else user.id
    )
    if not state or state.session_id != session_id or state.template_id != template_id:
        raise HTTPException(status_code=404, detail="Session not found.")


# _get_or_create_map moved to AdventureLogic.get_or_create_map


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get("/adventures/{template_id}/map")
async def get_map(
    template_id: str,
    session_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return the raw scene-graph JSON (nodes + edges) for an owned template."""
    await _authorize_map_access(db, template_id, session_id, current_user)
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
            exits = await load_map_exits(db, template_id, session_id)
            exit_states = None
            if session_id:
                state = await AdventureLogic.resolve_session_state(db, session_id)
                exit_states = state.exit_states if state else None
            map_dict = MapEngine.augment_map_data(
                map_dict, exits, raw_current_id, exit_states=exit_states
            )

    return map_dict


@router.post("/adventures/{template_id}/map/visit", status_code=200)
async def post_visit(
    template_id: str,
    payload: VisitPayload,
    session_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Register a scene visit — upserts the node and sets it as current (owner only)."""
    await _authorize_map_access(db, template_id, session_id, current_user)

    world_map = await AdventureLogic.get_or_create_map(db, template_id, session_id=session_id)
    MapEngine.register_visit(
        world_map, payload.scene_id, payload.label, payload.description, payload.image_url
    )
    await db.commit()
    return {"status": "ok", "current_scene_id": payload.scene_id}


@router.post("/adventures/{template_id}/map/exit", status_code=200)
async def post_exit(
    template_id: str,
    payload: ExitPayload,
    session_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Register a directed exit between two scenes (owner only)."""
    await _authorize_map_access(db, template_id, session_id, current_user)
    world_map = await AdventureLogic.get_or_create_map(db, template_id, session_id=session_id)
    MapEngine.register_exit(
        world_map, payload.from_scene, payload.to_scene, payload.exit_label or ""
    )
    await db.commit()
    return {"status": "ok"}
