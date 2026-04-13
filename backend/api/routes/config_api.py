from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.database import get_db
from backend.models.user import User
from backend.core.security import encryption_util

router = APIRouter(prefix="/settings", tags=["Settings"])

class ApiKeyPayload(BaseModel):
    provider: str
    api_key: str

class SettingsPayload(BaseModel):
    small_model: str
    complex_model: str
    preferred_provider: str # openai, openrouter, etc.

@router.get("")
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Returns the current settings (sanitized keys)."""
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()
    if not user:
        return {"keys": {}, "llm_settings": {}}
    
    # Return providers that have keys, but not the actual keys
    configured_providers = list(user.encrypted_api_keys.keys()) if user.encrypted_api_keys else []
    return {
        "keys": {provider: "********" for provider in configured_providers},
        "llm_settings": user.llm_settings or {
            "small_model": "openai/gpt-4o-mini",
            "complex_model": "openai/gpt-4o-mini",
            "preferred_provider": "openai"
        }
    }

@router.post("/keys")
async def update_api_key(payload: ApiKeyPayload, db: AsyncSession = Depends(get_db)):
    """Saves an encrypted API key for the default local user."""
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()
    
    if not user:
        user = User(username="local_default_user")
        db.add(user)
        await db.flush()
    
    encrypted_key = encryption_util.encrypt_key(payload.api_key)
    
    current_keys = user.encrypted_api_keys or {}
    new_keys = dict(current_keys)
    new_keys[payload.provider.lower()] = encrypted_key
    user.encrypted_api_keys = new_keys
    
    await db.commit()
    return {"status": "success", "message": f"{payload.provider} key saved securely."}

@router.post("/llm")
async def update_llm_settings(payload: SettingsPayload, db: AsyncSession = Depends(get_db)):
    """Updates the LLM model preferences."""
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()
    
    if not user:
        user = User(username="local_default_user")
        db.add(user)
        await db.flush()
        
    user.llm_settings = payload.dict()
    await db.commit()
    return {"status": "success", "message": "LLM settings updated."}

