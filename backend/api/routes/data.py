from typing import Optional
import os
import uuid
import re

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.core.database import get_db
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.utils.path_security import ensure_within_data_dir, local_path_to_data_url, safe_data_path, sanitize_path_component

# Security: Limit Pillow's decompressed pixel count to mitigate image-bomb DoS.
# A 1 MB PNG can otherwise expand to >100k x 100k pixels and exhaust RAM.
MAX_IMAGE_PIXELS = 50_000_000
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

router = APIRouter()

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB raw upload

def _get_extension(filename: str) -> str:
    return filename.rsplit(".", maxsplit=1)[-1].lower() if "." in filename else ""


def _safe_data_path(*parts: str) -> str:
    """Build a path under DATA_DIR and reject traversal."""
    try:
        return safe_data_path(*parts)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid path traversal attempt") from exc

@router.post("/data/image")
async def upload_image(
    file: UploadFile = File(...),
    upload_type: str = Query(
        "character",
        alias="type",
        description="Type of upload: 'character' or 'adventure'",
    ),
    adventure_id: Optional[str] = Query(None, description="Optional ID for adventure-specific subfolders"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Uploads an image, resizes/crops it based on type, and returns the URL.
    - characters: saved to data/characters, max 256x256
    - adventures: saved to data/adventures/library/{adventure_id}, max 512x512

    Requires authentication. Adventure-scoped uploads additionally require
    that the caller owns the target AdventureTemplate.
    """
    if upload_type not in {"character", "adventure"}:
        raise HTTPException(status_code=400, detail="Invalid upload type")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    ext = _get_extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file extension. Use jpg, png, or webp.")

    # Determine target directory
    url_parts: list[str]
    path_parts: list[str]
    if upload_type == "character":
        url_parts = ["characters"]
        path_parts = ["characters"]
        target_dir = _safe_data_path(*path_parts)
    else:
        if adventure_id:
            safe_adventure_id = sanitize_path_component(adventure_id)
            if not safe_adventure_id or not re.match(r"^[a-z0-9-]+$", safe_adventure_id):
                raise HTTPException(status_code=400, detail="Invalid adventure ID format")
            # Tenant isolation: only the owner (or admin) may upload to a template's directory.
            adv_res = await db.execute(
                select(AdventureTemplate).where(AdventureTemplate.id == safe_adventure_id)
            )
            adv = adv_res.scalars().first()
            if not adv or (adv.owner_id != current_user.id and current_user.role != "admin"):
                raise HTTPException(status_code=404, detail="AdventureTemplate not found.")
            url_parts = ["adventures", "library", safe_adventure_id]
            path_parts = ["adventures", "library", safe_adventure_id]
        else:
            url_parts = ["adventures", "library"]
            path_parts = ["adventures", "library"]
        target_dir = _safe_data_path(*path_parts)
    
    os.makedirs(target_dir, exist_ok=True)

    # Generate a unique filename
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = ensure_within_data_dir(os.path.join(target_dir, filename))

    try:
        # Read the image using Pillow (enforces MAX_IMAGE_PIXELS set above)
        file_bytes = await file.read()
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large. Max 10 MB.")
        image = Image.open(__import__("io").BytesIO(file_bytes))

        # Max dimensions based on type
        max_size = (256, 256) if upload_type == "character" else (512, 512)
        
        # Convert to RGB if needed
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        # Resize keeping aspect ratio
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        image.save(filepath, format=ext.upper() if ext != "jpg" else "JPEG")
        
        # Return the public URL for the image
        url = local_path_to_data_url(filepath)
        return {"url": url}

    except HTTPException:
        raise
    except Image.DecompressionBombWarning:  # type: ignore[attr-defined]
        raise HTTPException(status_code=400, detail="Image dimensions exceed safety limits.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}") from e
