import os
import uuid
from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from PIL import Image
from backend.core.config import settings

router = APIRouter()

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

def _get_extension(filename: str) -> str:
    return filename.split(".")[-1].lower() if "." in filename else ""

@router.post("/data/image")
async def upload_image(
    file: UploadFile = File(...),
    type: str = Query("character", description="Type of upload: 'character' or 'adventure'"),
):
    """
    Uploads an image, resizes/crops it based on type, and returns the URL.
    - characters: saved to data/characters, max 256x256
    - adventures: saved to data/adventures, max 512x512
    """
    if type not in {"character", "adventure"}:
        raise HTTPException(status_code=400, detail="Invalid upload type")

    ext = _get_extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file extension. Use jpg, png, or webp.")

    # Determine target directory
    subfolder = "characters" if type == "character" else "adventures"
    target_dir = os.path.join(settings.DATA_DIR, subfolder)
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
        return {"url": f"/data/{subfolder}/{filename}"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")
