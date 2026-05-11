from typing import Optional
import os
import uuid
import re

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from PIL import Image

from backend.core.config import settings

router = APIRouter()

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

def _get_extension(filename: str) -> str:
    return filename.rsplit(".", maxsplit=1)[-1].lower() if "." in filename else ""


def _safe_data_path(*parts: str) -> str:
    """Build a path under DATA_DIR and reject traversal."""
    data_root = os.path.abspath(settings.DATA_DIR)
    candidate = os.path.abspath(os.path.join(data_root, *parts))
    try:
        if os.path.commonpath([candidate, data_root]) != data_root:
            raise HTTPException(status_code=400, detail="Invalid path traversal attempt")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid path traversal attempt") from exc
    return candidate

@router.post("/data/image")
async def upload_image(
    file: UploadFile = File(...),
    upload_type: str = Query(
        "character",
        alias="type",
        description="Type of upload: 'character' or 'adventure'",
    ),
    adventure_id: Optional[str] = Query(None, description="Optional ID for adventure-specific subfolders")
):
    """
    Uploads an image, resizes/crops it based on type, and returns the URL.
    - characters: saved to data/characters, max 256x256
    - adventures: saved to data/adventures/library/{adventure_id}, max 512x512
    """
    if upload_type not in {"character", "adventure"}:
        raise HTTPException(status_code=400, detail="Invalid upload type")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    ext = _get_extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file extension. Use jpg, png, or webp.")

    # Determine target directory
    if upload_type == "character":
        subfolder = "characters"
        target_dir = _safe_data_path(subfolder)
    else:
        if adventure_id:
            # Security: Validate adventure_id to prevent path traversal
            if not re.match(r"^[a-z0-9-]+$", adventure_id):
                raise HTTPException(status_code=400, detail="Invalid adventure ID format")
            subfolder = f"adventures/library/{adventure_id}"
        else:
            subfolder = "adventures/library"
        target_dir = _safe_data_path(subfolder)
    
    os.makedirs(target_dir, exist_ok=True)

    # Generate a unique filename
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = _safe_data_path(subfolder, filename)

    try:
        # Read the image using Pillow
        image = Image.open(file.file)
        
        # Max dimensions based on type
        max_size = (256, 256) if upload_type == "character" else (512, 512)
        
        # Convert to RGB if needed
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        # Resize keeping aspect ratio
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        image.save(filepath, format=ext.upper() if ext != "jpg" else "JPEG")
        
        # Return the public URL for the image
        url = f"/data/{subfolder}/{filename}".replace("\\", "/")
        return {"url": url}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}") from e
