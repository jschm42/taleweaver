"""Deterministic voice casting: gives every NPC a fitting TTS voice that differs from its neighbours.

Voices are picked from the Google TTS catalog by the gender implied in the NPC's description,
avoiding the narrator voice and voices already used by other NPCs. The choice depends only on the
NPC id and the order of the NPCs, so the same adventure always sounds the same.
"""

from __future__ import annotations

import re
import zlib
from collections.abc import Iterable, Sequence
from typing import Final, NamedTuple, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.tts_voices import GOOGLE_TTS_VOICE_CATALOG, GOOGLE_TTS_VOICE_NAMES
from backend.models.user import User

DEFAULT_NARRATOR_VOICE: Final = "Puck"

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


def is_known_voice(voice: object) -> bool:
    return isinstance(voice, str) and voice in GOOGLE_TTS_VOICE_NAMES


def infer_voice_gender(text: str) -> Optional[str]:
    """``female``/``male`` when the description's wording clearly leans one way, else ``None``."""
    female = len(_FEMALE_WORDS.findall(text or ""))
    male = len(_MALE_WORDS.findall(text or ""))
    if female == male:
        return None
    return "female" if female > male else "male"


def _pick_voice(candidate: CastingCandidate, blocked: set[str]) -> str:
    gender = infer_voice_gender(candidate.description)
    matching = [
        entry["name"]
        for entry in GOOGLE_TTS_VOICE_CATALOG
        if gender is None or entry.get("gender") == gender
    ]
    free = [name for name in matching if name not in blocked] or matching
    return free[zlib.crc32(candidate.npc_id.encode("utf-8")) % len(free)]


def cast_voices(
    candidates: Sequence[CastingCandidate], reserved: Iterable[str] = ()
) -> dict[str, str]:
    """Maps every NPC id to a voice. Valid voices already set are kept; the rest are cast."""
    blocked = {voice for voice in reserved if voice}
    blocked.update(c.voice for c in candidates if is_known_voice(c.voice))
    voices: dict[str, str] = {}
    for candidate in candidates:
        if is_known_voice(candidate.voice):
            voices[candidate.npc_id] = str(candidate.voice)
            continue
        voice = _pick_voice(candidate, blocked)
        blocked.add(voice)
        voices[candidate.npc_id] = voice
    return voices


async def resolve_narrator_voice(db: AsyncSession) -> str:
    """The narrator voice from the global (admin-owned) TTS settings."""
    admin = (await db.execute(select(User).where(User.role == "admin").limit(1))).scalars().first()
    tts_settings = (admin.tts_settings if admin else None) or {}
    voice = tts_settings.get("selected_voice") if isinstance(tts_settings, dict) else None
    return voice if is_known_voice(voice) else DEFAULT_NARRATOR_VOICE
