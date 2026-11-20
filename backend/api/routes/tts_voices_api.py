"""The voice list for per-character speech, with the voices the active provider speaks."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.core.global_settings import read_server_settings
from backend.engine.audio.elevenlabs_voices import load_voice_catalog
from backend.engine.audio.voice_casting import NPC_VOICE_PROVIDER
from backend.engine.audio.voice_provider_map import (
    effective_voice_map,
    provider_voices,
    supports_character_voices,
)
from backend.models.user import User

router = APIRouter(prefix="/tts", tags=["TTS"])


@router.get("/voices")
async def list_tts_voices(
    provider: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """The voice list for per-character speech.

    The list is always returned so voices can be assigned in the editor at any time.
    ``provider_voices`` maps list ids to the voice the provider speaks (ElevenLabs: every voice;
    Google / OpenAI-compatible: the admin's voice mapping); unmapped voices use the narrator voice.
    ``supports_npc_voices`` is set once at least one voice is mapped. ``provider`` lets the
    settings form ask before the provider is saved.
    """
    _ = current_user
    owner = await read_server_settings(db)
    active = str((owner.tts_settings or {}).get("provider") or "google").lower()
    requested = (provider or active).lower()
    voices = load_voice_catalog()
    voice_map = effective_voice_map(owner.voice_provider_map, voices)
    mapped = (
        {v["id"]: v["id"] for v in voices}
        if requested == NPC_VOICE_PROVIDER
        else provider_voices(voice_map, requested)
    )
    return {
        "provider": requested,
        "supports_npc_voices": supports_character_voices(requested, voice_map),
        "provider_voices": mapped,
        "voices": voices,
    }
