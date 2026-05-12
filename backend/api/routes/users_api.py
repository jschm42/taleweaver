from typing import Optional, Union
import logging
import os
import shutil
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.auth_api import UserResponse
from backend.core.auth import get_current_admin, get_current_user, get_password_hash
from backend.core.config import settings
from backend.core.database import get_db
from backend.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)

class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str = "user"

class UserUpdateRequest(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None
    bio: Optional[str] = None
    default_language: Optional[str] = None

class BioUpdateRequest(BaseModel):
    bio: str


class ProfileImageGenerateRequest(BaseModel):
    bio: Optional[str] = None


def _normalize_public_data_url(url: str) -> str:
    """Normalize accidental duplicated /data prefixes in generated URLs."""
    normalized = (url or "").replace("\\", "/")
    while normalized.startswith("/data/data/"):
        normalized = normalized.replace("/data/data/", "/data/", 1)
    return normalized

@router.get("/users", response_model=list[UserResponse])
async def list_users(admin: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User))
    return result.scalars().all()

@router.post("/users", response_model=UserResponse)
async def create_user(request: UserCreateRequest, admin: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.username == request.username))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Username already registered")
        
    new_user = User(
        username=request.username,
        hashed_password=get_password_hash(request.password),
        role=request.role
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, request: UserUpdateRequest, admin: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if request.username:
        # Check uniqueness if username changed
        if request.username != user.username:
            check_res = await db.execute(select(User).filter(User.username == request.username))
            if check_res.scalars().first():
                raise HTTPException(status_code=400, detail="Username already registered")
        user.username = request.username
        
    if request.role:
        user.role = request.role
    if request.password:
        user.hashed_password = get_password_hash(request.password)
    if request.bio is not None:
        user.bio = request.bio
    if request.default_language is not None:
        user.default_language = request.default_language
        
    await db.commit()
    await db.refresh(user)
    return user

@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent deleting yourself
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
        
    await db.delete(user)
    await db.commit()
    return {"message": "User deleted"}

@router.put("/users/me/bio", response_model=UserResponse)
async def update_my_bio(request: BioUpdateRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    current_user.bio = request.bio
    await db.commit()
    await db.refresh(current_user)
    return current_user

@router.post("/users/me/profile-image", response_model=UserResponse)
async def upload_my_profile_image(file: UploadFile = File(...), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    upload_dir = os.path.join(settings.DATA_DIR, "users")
    os.makedirs(upload_dir, exist_ok=True)
    
    file_ext = os.path.splitext(file.filename)[1]
    filename = f"{current_user.id}_{uuid4().hex[:8]}{file_ext}"
    file_path = os.path.join(upload_dir, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    current_user.profile_image_url = f"/data/users/{filename}"
    await db.commit()
    await db.refresh(current_user)
    return current_user

@router.post("/users/me/bio/generate")
async def generate_my_bio(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from backend.engine.gm_engine import GameMasterLLM
    
    gm = GameMasterLLM()
    prompt = f"Write a short, epic, and mysterious lore bio (max 3 sentences) for a legendary storyteller named '{current_user.username}'. Focus on their role as a weaver of realities in the Aether."
    
    try:
        bio = await gm.generate_narrative(prompt, max_tokens=150)
        current_user.bio = bio
        await db.commit()
        await db.refresh(current_user)
        return {"bio": bio}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bio generation failed: {str(e)}")

@router.post("/users/me/profile-image/generate", response_model=UserResponse)
async def generate_my_profile_image(
    payload: Optional[ProfileImageGenerateRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from backend.engine.media_engine import MediaEngine

    admin_res = await db.execute(select(User).where(User.role == "admin").limit(1))
    settings_owner = admin_res.scalars().first() or current_user

    t2i = settings_owner.t2i_settings or {}
    if not t2i:
        raise HTTPException(status_code=400, detail="Visual preferences are not configured by admin.")

    provider = (t2i.get("simple_model_provider") or "openai").lower()
    model = t2i.get("simple_model")

    if not model:
        raise HTTPException(status_code=400, detail="Simple image model not configured")

    api_key = MediaEngine._resolve_api_key(provider, settings_owner.encrypted_api_keys or {})

    prompt_source = payload.bio if payload and payload.bio is not None else current_user.bio
    prompt = (prompt_source or "").strip() or "A fantasy roleplaying avatar"
        
    # Use absolute path so MediaEngine doesn't prepend DATA_DIR again for relative values.
    target_dir = os.path.abspath(os.path.join(settings.DATA_DIR, "users"))
    ext = "jpg" if (t2i.get("image_format") or "jpeg").lower() == "jpeg" else "png"
    filename = f"{current_user.id}_{uuid4().hex[:8]}.{ext}"
    
    try:
        logger.info(f"Starting profile image generation for user {current_user.id} with prompt: {prompt}")
        image_url = await MediaEngine.generate_image(
            prompt=prompt,
            model=model,
            api_key=api_key,
            provider=provider,
            target_dir=target_dir,
            filename=filename,
            provider_options=t2i
        )
        logger.info(f"Image generation completed. URL: {image_url}")
        
        if not image_url:
            logger.error("Image generation failed to return a URL")
            raise HTTPException(status_code=500, detail="Image generation failed to return a URL")
            
        current_user.profile_image_url = _normalize_public_data_url(image_url)
        logger.info(f"Updating user {current_user.id} profile image URL to: {image_url}")
        await db.commit()
        await db.refresh(current_user)
        logger.info(f"User {current_user.id} profile updated successfully")
        return current_user
    except Exception as e:
        import traceback
        logger.error(f"Profile image generation failed for user {current_user.id}: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")

