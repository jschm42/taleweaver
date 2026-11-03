"""Admin-managed catalog of narrator voices (how the GM narrates).

Every user reads the catalog of the admin account, so new users see the current voices without
a settings broadcast. Adventures store a full copy of their voice (see core/narrator_voices.py).
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import get_current_admin, get_current_user
from backend.core.database import get_db
from backend.core.narrator_voices import default_narrator_voices, normalize_voice_catalog
from backend.models.user import User

router = APIRouter(prefix="/settings/narrator-voices", tags=["Settings"])


class NarratorVoicePayload(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    instruction: str
    sample: Optional[str] = None


class NarratorVoiceCatalogPayload(BaseModel):
    items: list[NarratorVoicePayload]


async def _catalog_owner(db: AsyncSession, fallback: User) -> User:
    admin = (await db.execute(select(User).where(User.role == "admin").limit(1))).scalars().first()
    return admin or fallback


@router.get("")
async def get_narrator_voices(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """The narrator voices adventures can pick, plus the built-in defaults for a reset."""
    owner = await _catalog_owner(db, current_user)
    return {
        "items": normalize_voice_catalog(owner.narrator_voice_catalog),
        "defaults": default_narrator_voices(),
    }


@router.post("")
async def update_narrator_voices(
    payload: NarratorVoiceCatalogPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """Replaces the catalog; an empty list restores the defaults."""
    owner = await _catalog_owner(db, current_user)
    items = normalize_voice_catalog([item.model_dump() for item in payload.items])
    owner.narrator_voice_catalog = items
    await db.commit()
    return {"status": "success", "items": items}
