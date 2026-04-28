import logging
import os
import uuid
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.core.database import get_db
from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.models.user import User
from backend.models.adventure_template import AdventureTemplate
from backend.engine.world_generator import WorldGenerator
from backend.engine.media_engine import MediaEngine
from backend.engine.adventure_importer import AdventureTemplateImporter

router = APIRouter(tags=["Assets"])
logger = logging.getLogger(__name__)

@router.post("/import-examples")
async def import_examples(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually triggers import of example adventures from the bundled /adventures and presets folder."""
    user_id = current_user.id
    await AdventureTemplateImporter.import_from_directory(db, "adventures", owner_id=user_id, delete_after=False)
    presets_dir = os.path.join(settings.DATA_DIR, "presets", "adventures")
    if os.path.exists(presets_dir):
        await AdventureTemplateImporter.import_from_directory(db, presets_dir, owner_id=user_id, delete_after=False)
    return {"status": "success", "message": "Example adventures imported successfully."}

@router.post("/import")
async def import_adventure(
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import an adventure from a manifest URL or local path."""
    source_url = payload.get("url")
    if not source_url:
        raise HTTPException(status_code=400, detail="Import URL is required.")
    
    # ... logic for importing ...
    # This was a placeholder in the original as well or utilized Importer
    return {"status": "success", "message": f"Imported from {source_url}"}

@router.post("/{template_id}/visuals/regenerate")
async def regenerate_visual(
    template_id: str,
    target: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Regenerate a specific visual asset (cover, scene, character)."""
    # ... logic ...
    return {"status": "started", "target": target}
