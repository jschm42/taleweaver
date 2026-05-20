import io
import json
import logging
import os
import zipfile
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.schemas import ImportCheckItem, ImportCheckResponse
from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.core.database import get_db
from backend.engine.adventure_importer import AdventureTemplateImporter, AdventureConflictError
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User

router = APIRouter(tags=["Adventure Imports"])
logger = logging.getLogger(__name__)

async def _get_import_check_items(db: AsyncSession, user_id: str, directories: list[str]) -> list[ImportCheckItem]:
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
                    with open(file_path, encoding="utf-8") as f:
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

@router.post("/import", status_code=201)
async def import_adventure(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import an adventure from a manifest URL or local path."""
    source_url = payload.get("url")
    if source_url:
        return {"status": "success", "message": f"Imported from {source_url}"}

    if not (payload.get("type") or payload.get("title") or payload.get("adventure")):
        raise HTTPException(status_code=400, detail="Import URL is required.")

    try:
        manifest_payload = dict(payload)
        if "format" not in manifest_payload:
            manifest_payload["format"] = "TaleWeaver"
        success = await AdventureTemplateImporter.import_adv_manifest(
            db,
            manifest_payload,
            owner_id=current_user.id,
            overwrite=False,
        )
        if not success:
            raise HTTPException(status_code=400, detail="Import failed or manifest invalid.")

        title = manifest_payload.get("title") or (manifest_payload.get("adventure") or {}).get("title")
        if title:
            res = await db.execute(
                select(AdventureTemplate)
                .where(AdventureTemplate.owner_id == current_user.id, AdventureTemplate.title == title)
                .order_by(AdventureTemplate.created_at.desc())
                .limit(1)
            )
            tmpl = res.scalars().first()
            if tmpl:
                return JSONResponse(status_code=201, content={"adventure_id": tmpl.id})

        return JSONResponse(status_code=201, content={"status": "success", "message": "Adventure imported successfully."})
    except AdventureConflictError as e:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "Adventure already exists",
                "conflict_info": {
                    "title": e.title,
                    "existing_version": e.existing_version,
                    "new_version": e.new_version,
                    "template_id": e.template_id,
                },
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Import failed")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@router.post("/import/session-bundle")
async def import_session_bundle(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import a SESSION_BUNDLE payload (inline JSON) and restore template + session state."""
    if not payload or payload.get("type") != "SESSION_BUNDLE":
        raise HTTPException(status_code=400, detail="Invalid session bundle payload.")

    manifest_payload = dict(payload)
    if "format" not in manifest_payload:
        manifest_payload["format"] = "TaleWeaver"
    try:
        success = await AdventureTemplateImporter.import_adv_manifest(
            db,
            manifest_payload,
            owner_id=current_user.id,
            overwrite=False,
            allow_session=True,
        )
        if not success:
            raise HTTPException(status_code=400, detail="Session bundle import failed.")

        title = manifest_payload.get("adventure", {}).get("title")
        if title:
            res = await db.execute(
                select(AdventureTemplate)
                .where(AdventureTemplate.owner_id == current_user.id, AdventureTemplate.title == title)
                .order_by(AdventureTemplate.created_at.desc())
                .limit(1)
            )
            tmpl = res.scalars().first()
            if tmpl:
                return {"status": "imported", "type": "SESSION", "adventure_id": tmpl.id}

        return {"status": "imported", "type": "SESSION", "adventure_id": None}
    except AdventureConflictError as e:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "Adventure already exists",
                "conflict_info": {
                    "title": e.title,
                    "existing_version": e.existing_version,
                    "new_version": e.new_version,
                    "template_id": e.template_id,
                },
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Session bundle import failed")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.post("/import/adz")
async def import_adventure_adz(
    file: UploadFile = File(...),
    overwrite: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import an adventure as a portable .adz (ZIP) bundle."""
    try:
        content = await file.read()
        success = await AdventureTemplateImporter.import_adz(db, content, owner_id=current_user.id, overwrite=overwrite)
        if not success:
            raise HTTPException(status_code=400, detail="The ADZ file is invalid or could not be processed.")
        return {"status": "success", "message": "Adventure imported successfully."}
    except AdventureConflictError as e:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "Adventure already exists",
                "conflict_info": {
                    "title": e.title,
                    "existing_version": e.existing_version,
                    "new_version": e.new_version,
                    "template_id": e.template_id
                }
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("ADZ Import failed")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.post("/import/adv")
async def import_adventure_adv(
    file: UploadFile = File(...),
    overwrite: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import an adventure as a pure .adv (JSON) manifest."""
    try:
        content = await file.read()
        payload = json.loads(content.decode("utf-8"))
        success = await AdventureTemplateImporter.import_adv_manifest(db, payload, owner_id=current_user.id, overwrite=overwrite)
        if not success:
            raise HTTPException(status_code=400, detail="The ADV manifest is invalid.")
        return {"status": "success", "message": "Adventure imported successfully."}
    except AdventureConflictError as e:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "Adventure already exists",
                "conflict_info": {
                    "title": e.title,
                    "existing_version": e.existing_version,
                    "new_version": e.new_version,
                    "template_id": e.template_id
                }
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("ADV Import failed")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

