from typing import Optional, Union
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

@router.post("/data/image")
async def upload_image(
    file: UploadFile = File(...),
    type: str = Query("character", description="Type of upload: 'character' or 'adventure'"),
    adventure_id: Optional[str] = Query(None, description="Optional ID for adventure-specific subfolders")
):
    """
    Uploads an image, resizes/crops it based on type, and returns the URL.
    - characters: saved to data/characters, max 256x256
    - adventures: saved to data/adventures/library/{adventure_id}, max 512x512
    """
    if type not in {"character", "adventure"}:
        raise HTTPException(status_code=400, detail="Invalid upload type")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    ext = _get_extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file extension. Use jpg, png, or webp.")

    # Determine target directory
    if type == "character":
        subfolder = "characters"
        target_dir = os.path.join(settings.DATA_DIR, subfolder)
    else:
        if adventure_id:
            # Security: Validate adventure_id to prevent path traversal
            if not re.match(r"^[a-z0-9-]+$", adventure_id):
                raise HTTPException(status_code=400, detail="Invalid adventure ID format")
            subfolder = f"adventures/library/{adventure_id}"
        else:
            subfolder = "adventures/library"
        target_dir = os.path.join(settings.DATA_DIR, subfolder)
    
    # Final safety check: ensure target_dir is still within DATA_DIR
    target_dir = os.path.abspath(target_dir)
    data_dir_abs = os.path.abspath(settings.DATA_DIR)
    if not target_dir.startswith(data_dir_abs):
        raise HTTPException(status_code=400, detail="Invalid path traversal attempt")
    
    os.makedirs(target_dir, exist_ok=True)

    # Generate a unique filename
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = os.path.join(target_dir, filename)

    try:
        # Read the image using Pillow
        image = Image.open(file.file)
        
        # Max dimensions based on type
        max_size = (256, 256) if type == "character" else (512, 512)
        
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
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")
