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
    new_keys[payload.provider] = encrypted_key
    user.encrypted_api_keys = new_keys
    
    await db.commit()
    return {"status": "success", "message": f"{payload.provider} key saved securely."}
