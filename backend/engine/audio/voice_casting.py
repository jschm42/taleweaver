"""Deterministic voice casting: gives every NPC a fitting voice that differs from its neighbours.

Voices come from the curated voice list (see ``elevenlabs_voices``), whatever the speech provider:
ElevenLabs speaks the list ids, Google TTS and the OpenAI-compatible server the voices the admin
mapped to them (``voice_provider_map``; unmapped voices fall back to the narrator voice). Voices are
picked by the gender implied in the NPC's description, avoiding voices that sound like the
narrator and voices already used by other NPCs. The choice depends only on the NPC id and the order
of the NPCs, so the same adventure always sounds the same. An NPC whose stored voice was removed
from the list uses the narrator voice.
"""

from __future__ import annotations

import re
import zlib
from collections.abc import Iterable, Sequence
from typing import Any, Final, NamedTuple, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.api_keys import resolve_api_key
from backend.core.global_settings import SettingsSource, read_server_settings
from backend.engine.audio.elevenlabs_voices import VoiceOption, custom_voice_id, load_voice_catalog
from backend.engine.audio.voice_provider_map import effective_voice_map, voices_sounding_like
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession

NPC_VOICE_PROVIDER: Final = "elevenlabs"
# Key of the protagonist in the voice metadata (NPC ids are upper-case slugs, never this).
PROTAGONIST_VOICE_KEY: Final = "__protagonist__"

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
    # List voice ids the provider speaks with the narrator voice (never cast to characters).
    reserved: tuple[str, ...] = ()


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


def _playable_stored_voice(voice: Optional[str], known: set[str]) -> Optional[str]:
    """Custom voices are always used; list voices only while they are still in the list."""
    return custom_voice_id(voice) or (voice if voice in known else None)


def cast_voices(
    candidates: Sequence[CastingCandidate],
    voices: Sequence[VoiceOption],
    reserved: Iterable[str] = (),
) -> dict[str, Optional[str]]:
    """Maps every NPC id to a playable voice id; ``None`` means the narrator voice.

    A custom voice ("custom:<id>") is always used, a voice from the list is kept, a voice no longer
    in the list falls back to the narrator voice, and NPCs without any voice get one cast.
    """
    known = {v["id"] for v in voices}
    blocked = {voice for voice in reserved if voice}
    blocked.update(v for c in candidates if (v := _playable_stored_voice(c.voice, known)))
    cast: dict[str, Optional[str]] = {}
    for candidate in candidates:
        if candidate.voice:
            cast[candidate.npc_id] = _playable_stored_voice(candidate.voice, known)
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
    """Per-NPC list voices (``None`` = narrator voice), avoiding the narrator's own voice."""
    return cast_voices(candidates, setup.voices, reserved=setup.reserved)


def provider_api_key(provider: str, source: Optional[SettingsSource]) -> Optional[str]:
    """The key for ``provider`` per the key policy (personal, env or stored server key).

    ``source`` is a user with the settings overlay (effective keys) or the server row.
    Raises ``PersonalKeyRequiredError`` when the provider is unavailable for that user.
    """
    return resolve_api_key(source.encrypted_api_keys if source else None, provider)


def _narrator_voice(provider: str, tts_settings: dict[str, Any]) -> str:
    keys = {NPC_VOICE_PROVIDER: "elevenlabs_voice_id", "custom_openai": "custom_openai_voice"}
    return str(tts_settings.get(keys.get(provider, "selected_voice")) or "")


async def resolve_voice_setup(db: AsyncSession) -> VoiceSetup:
    """Active TTS provider, its narrator voice, the voice list and the voices to keep free."""
    server = await read_server_settings(db)
    tts_settings = server.tts_settings or {}
    provider = str(tts_settings.get("provider") or "google").lower()
    narrator = _narrator_voice(provider, tts_settings)
    voices = load_voice_catalog()
    voice_map = effective_voice_map(server.voice_provider_map, voices)
    reserved = tuple(voices_sounding_like(voice_map, provider, narrator))
    return VoiceSetup(provider, narrator, voices, reserved)


async def load_protagonist(
    db: AsyncSession, template_id: Optional[str], session_id: Optional[str]
) -> Optional[Avatar]:
    """The session's avatar, else the adventure's template avatar (the first one created)."""
    if session_id:
        avatar_id = (
            await db.execute(select(GameSession.avatar_id).where(GameSession.id == session_id))
        ).scalar_one_or_none()
        return await db.get(Avatar, avatar_id) if avatar_id else None
    if not template_id:
        return None
    query = (
        select(Avatar)
        .where(Avatar.template_id == template_id)
        .order_by(Avatar.created_at.asc())
        .limit(1)
    )
    return (await db.execute(query)).scalars().first()


def protagonist_candidate(avatar: Avatar) -> CastingCandidate:
    text = f"{avatar.name} {avatar.description or ''} {avatar.character or ''}"
    return CastingCandidate(PROTAGONIST_VOICE_KEY, text, avatar.voice)


async def cast_adventure_voices(
    db: AsyncSession, npcs: Sequence[Any], template_id: Optional[str], session_id: Optional[str]
) -> tuple[dict[str, Optional[str]], Optional[dict[str, Any]]]:
    """Voices for the NPCs and the protagonist (cast together, so they all differ).

    Returns the voice per NPC id and the protagonist's metadata entry (``None`` without avatar),
    stored under ``PROTAGONIST_VOICE_KEY`` so the player's own lines get their voice too.
    """
    protagonist = await load_protagonist(db, template_id, session_id)
    candidates = [protagonist_candidate(protagonist)] if protagonist else []
    candidates += [
        CastingCandidate(npc.id, f"{npc.name} {npc.description} {npc.character or ''}", npc.voice)
        for npc in npcs
    ]
    voices = cast_npc_voices(await resolve_voice_setup(db), candidates)
    if not protagonist:
        return voices, None
    return voices, {
        "name": protagonist.name,
        "description": protagonist.description or "",
        "image_url": protagonist.profile_image,
        "voice": voices.get(PROTAGONIST_VOICE_KEY),
        "entity_type": "PROTAGONIST",
    }
