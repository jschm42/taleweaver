from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os
import shutil
from uuid import uuid4

from backend.core.database import get_db
from backend.core.auth import get_current_user, get_current_admin, get_password_hash
from backend.models.user import User
from backend.core.config import settings
from backend.api.routes.auth_api import UserResponse
from pydantic import BaseModel

router = APIRouter()

class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str = "user"

class UserUpdateRequest(BaseModel):
    username: str | None = None
    role: str | None = None
    password: str | None = None
    bio: str | None = None

class BioUpdateRequest(BaseModel):
    bio: str

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
async def generate_my_profile_image(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from backend.engine.media_engine import MediaEngine
    from backend.core.config import settings
    from backend.models.settings import SystemSettings
    
    # Get admin config for image generation
    settings_res = await db.execute(select(SystemSettings))
    system_settings = settings_res.scalars().first()
    if not system_settings:
        raise HTTPException(status_code=500, detail="System settings not found")
        
    user_config = system_settings.config
    api_keys = system_settings.api_keys
    
    t2i = user_config.get("t2i_settings")
    if not t2i:
        raise HTTPException(status_code=400, detail="Visual preferences not configured in Admin settings")
        
    provider = (t2i.get("simple_model_provider") or t2i.get("provider", "openai")).lower()
    model = t2i.get("simple_model")
    
    if not model:
        raise HTTPException(status_code=400, detail="Simple image model not configured")
        
    api_key = MediaEngine._resolve_api_key(provider, api_keys)
    
    prompt = f"A high-quality fantasy portrait avatar of a legendary storyteller. Theme: Aether weaver, mystical hood, glowing accents. Based on user: {current_user.username}. Style: Digital art, clean background, epic lighting."
    if current_user.bio:
        prompt += f" Reference: {current_user.bio[:200]}"
        
    target_dir = os.path.join(settings.DATA_DIR, "users")
    ext = "jpg" if (t2i.get("image_format") or "jpeg").lower() == "jpeg" else "png"
    filename = f"{current_user.id}_{uuid4().hex[:8]}.{ext}"
    
    try:
        image_url = await MediaEngine.generate_image(
            prompt=prompt,
            model=model,
            api_key=api_key,
            provider=provider,
            target_dir=target_dir,
            filename=filename,
            provider_options=t2i
        )
        
        if not image_url:
            raise HTTPException(status_code=500, detail="Image generation failed to return a URL")
            
        current_user.profile_image_url = image_url
        await db.commit()
        await db.refresh(current_user)
        return current_user
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")
