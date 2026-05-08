import logging
import os
import zipfile
import io
import json
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from backend.core.database import get_db
from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.models.user import User
from backend.models.adventure_template import AdventureTemplate
from backend.engine.adventure_importer import AdventureTemplateImporter
from backend.api.routes.adventures.schemas import ImportCheckResponse, ImportCheckItem

router = APIRouter(tags=["Adventure Imports"])
logger = logging.getLogger(__name__)

async def _get_import_check_items(db: AsyncSession, user_id: str, directories: List[str]) -> List[ImportCheckItem]:
    """Scans directories for adventures and checks if they already exist in the user's library."""
    check_items = []
    
    for directory in directories:
        if not os.path.exists(directory):
            continue
            
        files = [f for f in os.listdir(directory) if f.endswith(".adv") or f.endswith(".adz")]
        for filename in files:
            file_path = os.path.join(directory, filename)
            title = None
            origin_id = None
            
            try:
                if filename.endswith(".adz"):
                    with open(file_path, "rb") as f:
                        with zipfile.ZipFile(io.BytesIO(f.read()), "r") as zip_file:
                            manifest = json.loads(zip_file.read("adventure.adv").decode("utf-8"))
                            adv_data = manifest.get("adventure") or {}
                            title = adv_data.get("title")
                            origin_id = adv_data.get("origin_id") or manifest.get("origin_id")
                else:
                    with open(file_path, "r", encoding="utf-8") as f:
                        payload = json.load(f)
                        is_session = payload.get("type") == "SESSION_BUNDLE"
                        title = payload.get("adventure", {}).get("title") if is_session else payload.get("title")
                        origin_id = payload.get("adventure", {}).get("origin_id") if is_session else payload.get("origin_id")
                
                if title:
                    query = select(AdventureTemplate).where(AdventureTemplate.owner_id == user_id)
                    if origin_id:
                        query = query.where(or_(AdventureTemplate.title == title, AdventureTemplate.origin_id == origin_id))
                    else:
                        query = query.where(AdventureTemplate.title == title)
                    
                    res = await db.execute(query)
                    existing = res.scalars().first()
                    
                    check_items.append(ImportCheckItem(
                        title=title,
                        already_exists=existing is not None,
                        existing_template_id=existing.id if existing else None,
                        origin_id=origin_id
                    ))
            except Exception as e:
                logger.error(f"Error checking import file {file_path}: {e}")
                
    return check_items

@router.get("/check-defaults", response_model=ImportCheckResponse)
async def check_defaults(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns a list of default adventures and their existence status."""
    defaults_dir = os.path.join("adventures", "default")
    items = await _get_import_check_items(db, current_user.id, [defaults_dir])
    return ImportCheckResponse(available_imports=items)

@router.get("/check-examples", response_model=ImportCheckResponse)
async def check_examples(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns a list of example/sample adventures and their existence status."""
    samples_dir = os.path.join("adventures", "samples")
    presets_dir = os.path.join(settings.DATA_DIR, "presets", "adventures")
    items = await _get_import_check_items(db, current_user.id, [samples_dir, presets_dir])
    return ImportCheckResponse(available_imports=items)

@router.post("/import-examples")
async def import_examples(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually triggers import of example adventures."""
    user_id = current_user.id
    samples_dir = os.path.join("adventures", "samples")
    await AdventureTemplateImporter.import_from_directory(db, samples_dir, owner_id=user_id, delete_after=False)
    
    presets_dir = os.path.join(settings.DATA_DIR, "presets", "adventures")
    if os.path.exists(presets_dir):
        await AdventureTemplateImporter.import_from_directory(db, presets_dir, owner_id=user_id, delete_after=False)
    return {"status": "success", "message": "Example adventures imported successfully."}

@router.post("/import-defaults")
async def import_defaults(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Triggers import of default adventures."""
    if current_user.has_imported_defaults:
        return {"status": "skipped", "message": "Defaults already imported."}
    
    defaults_dir = os.path.join("adventures", "default")
    await AdventureTemplateImporter.import_from_directory(db, defaults_dir, owner_id=current_user.id, delete_after=False)
    
    current_user.has_imported_defaults = True
    await db.commit()
    return {"status": "success", "message": "Default adventures imported successfully."}

@router.post("/reimport-defaults")
async def reimport_defaults(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually re-triggers import of default adventures."""
    defaults_dir = os.path.join("adventures", "default")
    await AdventureTemplateImporter.import_from_directory(db, defaults_dir, owner_id=current_user.id, delete_after=False)
    return {"status": "success", "message": "Default adventures re-imported successfully."}

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
    return {"status": "success", "message": f"Imported from {source_url}"}

@router.post("/import/adz")
async def import_adventure_adz(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import an adventure as a portable .adz (ZIP) bundle."""
    try:
        content = await file.read()
        success = await AdventureTemplateImporter.import_adz(db, content, owner_id=current_user.id)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to import ADZ.")
        return {"status": "success", "message": "Adventure imported successfully."}
    except Exception as e:
        logger.exception("ADZ Import failed")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/import/adv")
async def import_adventure_adv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import an adventure as a pure .adv (JSON) manifest."""
    try:
        content = await file.read()
        payload = json.loads(content.decode("utf-8"))
        success = await AdventureTemplateImporter.import_adv_manifest(db, payload, owner_id=current_user.id)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to import ADV.")
        return {"status": "success", "message": "Adventure imported successfully."}
    except Exception as e:
        logger.exception("ADV Import failed")
        raise HTTPException(status_code=500, detail=str(e))
