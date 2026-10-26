"""Deterministic voice casting: gives every NPC a fitting ElevenLabs voice that differs from its neighbours.

Per-character voices are an ElevenLabs feature; with Gemini TTS everything is spoken in the
narrator voice. Voices come from the curated voice list (see ``elevenlabs_voices``) and are picked by
the gender implied in the NPC's description, avoiding the narrator voice and voices already used by
other NPCs. The choice depends only on the NPC id and the order of the NPCs, so the same adventure
always sounds the same. An NPC whose stored voice was removed from the list uses the narrator voice.
"""

from __future__ import annotations

import re
import zlib
from collections.abc import Iterable, Sequence
from typing import Final, NamedTuple, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.security import encryption_util
from backend.engine.elevenlabs_voices import VoiceOption, load_voice_catalog
from backend.models.user import User

NPC_VOICE_PROVIDER: Final = "elevenlabs"

_FEMALE_WORDS: Final = re.compile(
    r"\b(?:she|her|hers|herself|woman|women|girl|lady|queen|mother|sister|daughter|wife|"
    r"grandmother|matron|priestess|witch|madam|duchess|princess|female|widow|niece|aunt)\b",
    re.I,
)
_MALE_WORDS: Final = re.compile(
    r"\b(?:he|him|his|himself|man|men|boy|lord|king|father|brother|son|husband|grandfather|"
    r"priest|sir|duke|prince|male|widower|nephew|uncle|guy)\b",
    re.I,
)


class CastingCandidate(NamedTuple):
    npc_id: str
    description: str = ""
    voice: Optional[str] = None


class VoiceSetup(NamedTuple):
    provider: str
    narrator_voice: str
    voices: list[VoiceOption]

    @property
    def supports_npc_voices(self) -> bool:
        return self.provider == NPC_VOICE_PROVIDER


def infer_voice_gender(text: str) -> Optional[str]:
    """``female``/``male`` when the description's wording clearly leans one way, else ``None``."""
    female = len(_FEMALE_WORDS.findall(text or ""))
    male = len(_MALE_WORDS.findall(text or ""))
    if female == male:
        return None
    return "female" if female > male else "male"


def _pick_voice(
    candidate: CastingCandidate, voices: Sequence[VoiceOption], blocked: set[str]
) -> str:
    gender = infer_voice_gender(candidate.description)
    matching = [v["id"] for v in voices if gender is None or v["gender"] in (gender, None)]
    matching = matching or [v["id"] for v in voices]
    free = [voice_id for voice_id in matching if voice_id not in blocked] or matching
    return free[zlib.crc32(candidate.npc_id.encode("utf-8")) % len(free)]


def cast_voices(
    candidates: Sequence[CastingCandidate],
    voices: Sequence[VoiceOption],
    reserved: Iterable[str] = (),
) -> dict[str, Optional[str]]:
    """Maps every NPC id to a voice id from ``voices``; ``None`` means the narrator voice.

    A voice from the list is kept, a voice no longer in the list falls back to the narrator voice,
    and NPCs without any voice get one cast.
    """
    known = {v["id"] for v in voices}
    blocked = {voice for voice in reserved if voice}
    blocked.update(str(c.voice) for c in candidates if c.voice in known)
    cast: dict[str, Optional[str]] = {}
    for candidate in candidates:
        if candidate.voice:
            cast[candidate.npc_id] = candidate.voice if candidate.voice in known else None
            continue
        if not known:
            cast[candidate.npc_id] = None
            continue
        voice_id = _pick_voice(candidate, voices, blocked)
        blocked.add(voice_id)
        cast[candidate.npc_id] = voice_id
    return cast


def cast_npc_voices(
    setup: VoiceSetup, candidates: Sequence[CastingCandidate]
) -> dict[str, Optional[str]]:
    """Per-NPC voices for the active provider; ``None`` everywhere when it has no NPC voices."""
    if not setup.supports_npc_voices:
        return {c.npc_id: None for c in candidates}
    return cast_voices(candidates, setup.voices, reserved=[setup.narrator_voice])


async def load_tts_owner(db: AsyncSession) -> Optional[User]:
    """TTS settings are global and owned by the (first) admin."""
    return (await db.execute(select(User).where(User.role == "admin").limit(1))).scalars().first()


def provider_api_key(provider: str, owner: Optional[User]) -> Optional[str]:
    """The provider key from the environment, else the owner's stored (encrypted) key."""
    api_key = settings.get_env_api_key(provider)
    if api_key:
        return api_key
    encrypted = ((owner.encrypted_api_keys if owner else None) or {}).get(provider)
    return encryption_util.decrypt_key(encrypted) if encrypted else None


async def resolve_voice_setup(db: AsyncSession) -> VoiceSetup:
    """Active TTS provider, narrator voice and (for ElevenLabs) the voice list."""
    owner = await load_tts_owner(db)
    tts_settings = (owner.tts_settings if owner else None) or {}
    provider = str(tts_settings.get("provider") or "google").lower()
    if provider != NPC_VOICE_PROVIDER:
        return VoiceSetup(provider, str(tts_settings.get("selected_voice") or ""), [])
    return VoiceSetup(
        provider, str(tts_settings.get("elevenlabs_voice_id") or ""), load_voice_catalog()
    )
