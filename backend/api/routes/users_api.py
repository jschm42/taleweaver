from __future__ import annotations

import logging
import os
import shutil
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.account_api import router as account_router
from backend.api.routes.auth_api import UserResponse
from backend.core.account_recovery import (
    RESET_TOKEN_TTL,
    issue_password_reset_token,
    set_new_password,
)
from backend.core.auth import (
    aget_password_hash,
    get_current_admin,
    get_current_user,
    validate_password_strength,
    validate_username,
)
from backend.core.config import settings
from backend.core.database import get_db
from backend.core.llm_router import GameMasterLLM
from backend.core.prompts import (
    USER_BIO_GENERATION_SYSTEM_PROMPT,
    USER_BIO_GENERATION_USER_PROMPT_TEMPLATE,
)
from backend.core.security import encryption_util
from backend.engine.media_engine import MediaEngine
from backend.models.user import User
from backend.utils.path_security import (
    ensure_within_data_dir,
    local_path_to_data_url,
    safe_data_path,
    sanitize_path_component,
)

router = APIRouter()
# Self-service account routes (/users/me/...) live in their own module but share this router.
router.include_router(account_router)
logger = logging.getLogger(__name__)

ADMIN_DEP = Depends(get_current_admin)
USER_DEP = Depends(get_current_user)
DB_DEP = Depends(get_db)
UPLOAD_FILE_DEP = File(...)
_SAFE_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
_ALLOWED_ROLES = {"admin", "user"}


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


class PasswordResetLinkResponse(BaseModel):
    token: str
    expires_in_hours: int


class ProfileImageGenerateRequest(BaseModel):
    bio: Optional[str] = None


def _normalize_public_data_url(url: str) -> str:
    """Normalize accidental duplicated /data prefixes in generated URLs."""
    normalized = (url or "").replace("\\", "/")
    while normalized.startswith("/data/data/"):
        normalized = normalized.replace("/data/data/", "/data/", 1)
    return normalized


def _sanitize_path_component(value: str) -> Optional[str]:
    return sanitize_path_component(value)


def _ensure_within_data_dir(path: str) -> str:
    return ensure_within_data_dir(path)


def _sanitize_image_extension(filename: Optional[str]) -> str:
    if not filename or "." not in filename:
        return ".png"
    ext = os.path.splitext(filename)[1].strip().lower()
    if ext not in _SAFE_IMAGE_EXTENSIONS:
        return ".png"
    return ext


def _validated_username(username: str) -> str:
    try:
        return validate_username(username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _validated_password(password: str) -> str:
    try:
        validate_password_strength(password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return password


def _validated_role(role: str) -> str:
    if role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"Unknown role '{role}'.")
    return role


async def _ensure_username_available(db: AsyncSession, username: str) -> None:
    taken = await db.execute(select(User.id).where(User.username == username))
    if taken.first() is not None:
        raise HTTPException(status_code=400, detail="Username already registered")


async def _ensure_admin_remains(db: AsyncSession, user: User, new_role: str, admin: User) -> None:
    """Block demotions that would lock everyone out of administration."""
    if user.role != "admin" or new_role == "admin":
        return
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot remove your own admin role.")
    other_admins = await db.execute(
        select(User.id).where(User.role == "admin", User.id != user.id).limit(1)
    )
    if other_admins.first() is None:
        raise HTTPException(status_code=400, detail="At least one administrator must remain.")


def _resolve_provider_api_key(
    provider: str, api_keys_dict: Optional[dict[str, str]]
) -> Optional[str]:
    provider_key = (provider or "").lower()
    env_key = settings.get_env_api_key(provider_key)
    if env_key:
        return env_key

    if api_keys_dict and provider_key in api_keys_dict:
        try:
            return encryption_util.decrypt_key(api_keys_dict[provider_key])
        except (ValueError, TypeError, KeyError):
            logger.error("Failed to decrypt API key for provider '%s'", provider_key)
            return None

    return None


@router.get("/users", response_model=list[UserResponse])
async def list_users(_admin: User = ADMIN_DEP, db: AsyncSession = DB_DEP):
    result = await db.execute(select(User))
    return result.scalars().all()


@router.post("/users", response_model=UserResponse)
async def create_user(
    request: UserCreateRequest,
    _admin: User = ADMIN_DEP,
    db: AsyncSession = DB_DEP,
):
    username = _validated_username(request.username)
    await _ensure_username_available(db, username)

    new_user = User(
        username=username,
        hashed_password=await aget_password_hash(_validated_password(request.password)),
        role=_validated_role(request.role),
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    request: UserUpdateRequest,
    admin: User = ADMIN_DEP,
    db: AsyncSession = DB_DEP,
):
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if request.username:
        username = _validated_username(request.username)
        if username != user.username:
            await _ensure_username_available(db, username)
        user.username = username

    if request.role:
        new_role = _validated_role(request.role)
        await _ensure_admin_remains(db, user, new_role, admin)
        user.role = new_role
    if request.password:
        # Also revokes the user's existing sessions.
        await set_new_password(user, _validated_password(request.password))
    if request.bio is not None:
        user.bio = request.bio
    if request.default_language is not None:
        user.default_language = request.default_language

    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: User = ADMIN_DEP, db: AsyncSession = DB_DEP):
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


@router.post("/users/{user_id}/password-reset-link", response_model=PasswordResetLinkResponse)
async def create_password_reset_link(
    user_id: str, _admin: User = ADMIN_DEP, db: AsyncSession = DB_DEP
):
    """Issue a one-time password reset token for a user (replaces any previous one)."""
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    token = issue_password_reset_token(user)
    await db.commit()
    logger.info("Admin issued a password reset link for user %s", user.id)
    return PasswordResetLinkResponse(
        token=token, expires_in_hours=int(RESET_TOKEN_TTL.total_seconds() // 3600)
    )


@router.put("/users/me/bio", response_model=UserResponse)
async def update_my_bio(
    request: BioUpdateRequest, current_user: User = USER_DEP, db: AsyncSession = DB_DEP
):
    current_user.bio = request.bio
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post("/users/me/profile-image", response_model=UserResponse)
async def upload_my_profile_image(
    file: UploadFile = UPLOAD_FILE_DEP,
    current_user: User = USER_DEP,
    db: AsyncSession = DB_DEP,
):
    safe_user_id = _sanitize_path_component(current_user.id)
    if not safe_user_id:
        raise HTTPException(status_code=400, detail="Invalid user identifier")

    upload_dir = safe_data_path("users")
    os.makedirs(upload_dir, exist_ok=True)

    file_ext = _sanitize_image_extension(file.filename)
    filename = f"{safe_user_id}_{uuid4().hex[:8]}{file_ext}"
    file_path = _ensure_within_data_dir(os.path.join(upload_dir, filename))

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    current_user.profile_image_url = local_path_to_data_url(file_path)
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post("/users/me/bio/generate")
async def generate_my_bio(current_user: User = USER_DEP, db: AsyncSession = DB_DEP):
    llm_settings = current_user.llm_settings or {}
    provider = (llm_settings.get("small_model_provider") or "openai").lower()
    model = llm_settings.get("small_model") or "gpt-4o-mini"

    gm = GameMasterLLM(current_user, provider=provider, model_category="small")
    system_prompt = USER_BIO_GENERATION_SYSTEM_PROMPT
    user_prompt = USER_BIO_GENERATION_USER_PROMPT_TEMPLATE.format(username=current_user.username)

    try:
        bio = await gm.aexecute_simple_task(system_prompt, user_prompt, model)
        current_user.bio = bio
        await db.commit()
        await db.refresh(current_user)
        return {"bio": bio}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bio generation failed: {str(e)}") from e


@router.post("/users/me/profile-image/generate", response_model=UserResponse)
async def generate_my_profile_image(
    payload: Optional[ProfileImageGenerateRequest] = None,
    current_user: User = USER_DEP,
    db: AsyncSession = DB_DEP,
):
    admin_res = await db.execute(select(User).where(User.role == "admin").limit(1))
    settings_owner = admin_res.scalars().first() or current_user

    t2i = settings_owner.t2i_settings or {}
    if not t2i:
        raise HTTPException(
            status_code=400, detail="Visual preferences are not configured by admin."
        )

    provider = (t2i.get("simple_model_provider") or "openai").lower()
    model = t2i.get("simple_model")

    if not model:
        raise HTTPException(status_code=400, detail="Simple image model not configured")

    api_key = _resolve_provider_api_key(provider, settings_owner.encrypted_api_keys or {})

    prompt_source = payload.bio if payload and payload.bio is not None else current_user.bio
    prompt = (prompt_source or "").strip() or "A fantasy roleplaying avatar"

    target_dir = safe_data_path("users")
    safe_user_id = _sanitize_path_component(current_user.id)
    if not safe_user_id:
        raise HTTPException(status_code=400, detail="Invalid user identifier")
    ext = "jpg" if (t2i.get("image_format") or "jpeg").lower() == "jpeg" else "png"
    filename = f"{safe_user_id}_{uuid4().hex[:8]}.{ext}"

    try:
        logger.info(
            "Starting profile image generation for user %s with prompt: %s",
            current_user.id,
            prompt,
        )
        image_url = await MediaEngine.generate_image(
            prompt=prompt,
            model=model,
            api_key=api_key,
            provider=provider,
            target_dir=target_dir,
            filename=filename,
            provider_options=t2i,
        )
        logger.info("Image generation completed. URL: %s", image_url)

        if not image_url:
            logger.error("Image generation failed to return a URL")
            raise HTTPException(status_code=500, detail="Image generation failed to return a URL")

        current_user.profile_image_url = _normalize_public_data_url(image_url)
        logger.info("Updating user %s profile image URL to: %s", current_user.id, image_url)
        await db.commit()
        await db.refresh(current_user)
        logger.info("User %s profile updated successfully", current_user.id)
        return current_user
    except Exception as e:
        logger.exception("Profile image generation failed for user %s", current_user.id)
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}") from e
