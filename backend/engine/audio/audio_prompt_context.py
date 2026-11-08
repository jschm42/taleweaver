"""Prompts for generated audio tracks (scene loops, title tracks), suggested by the small LLM.

The suggestion is built from the adventure's tone (``selected_tone``), title and teaser plus the
scene's name and description. Every suggested prompt ends with a loop instruction
(``ensure_loopable``), because scene audio repeats for as long as the player stays.
Music models block artist names and lyrics, so the system prompt forbids both.
"""

from __future__ import annotations

import re
from typing import Any, Optional

MAX_AUDIO_PROMPT_CHARS = 1000

LOOP_INSTRUCTION = (
    "Seamless loop: no intro, no fade-out ending, steady energy, so the end flows straight "
    "back into the start."
)

AUDIO_PROMPT_SYSTEM_PROMPT = """You write prompts for an instrumental music generation model \
(Google Lyria, ACE-Step) that creates background music for an interactive text adventure.

Write ONE prompt of 2-4 short sentences in English that describes the music itself:
- genre and style, lead and supporting instruments, tempo (with BPM), key or mode if useful,
- mood and atmosphere that fit the place and the adventure's tone,
- dynamics: calm background music that never drowns out narration.

Rules:
- Instrumental only. No vocals, no lyrics, no singing.
- Never name artists, bands, composers, songs, films or games.
- Do not describe the plot or the scene; describe only how the audio sounds.
- The audio will loop, so ask for a seamless loop without intro or ending.
- Output only the prompt text, no quotes, no labels."""

AUDIO_PROMPT_USER_TEMPLATE = """Adventure: {title}
Tone: {tone}
Premise: {teaser}

{target_label}: {name}
Description: {description}

Write the music prompt for this {target_kind}."""

_LOOP_WORD_RE = re.compile(r"\bloop", re.IGNORECASE)


def ensure_loopable(prompt: str) -> str:
    """Return ``prompt`` with the loop instruction appended unless it already asks for a loop."""
    text = re.sub(r"\s+", " ", str(prompt or "")).strip().strip("\"'")
    if not text:
        return ""
    if _LOOP_WORD_RE.search(text):
        return text[:MAX_AUDIO_PROMPT_CHARS]
    room = MAX_AUDIO_PROMPT_CHARS - len(LOOP_INSTRUCTION) - 1
    return f"{text[:room].rstrip()} {LOOP_INSTRUCTION}"


def tone_text(selected_tone: Optional[dict[str, Any]]) -> str:
    tone = selected_tone or {}
    name = str(tone.get("name") or tone.get("id") or "").strip()
    detail = str(tone.get("description") or tone.get("instruction") or "").strip()
    text = f"{name} - {detail}" if name and detail else (name or detail)
    return text[:400] or "Neutral"


def build_audio_prompt_request(
    adventure: Any, *, target_kind: str, name: str, description: str
) -> str:
    """User prompt for the suggestion LLM (``target_kind``: ``scene`` or ``main theme``)."""
    is_scene = target_kind == "scene"
    return AUDIO_PROMPT_USER_TEMPLATE.format(
        title=str(getattr(adventure, "title", "") or "")[:200],
        tone=tone_text(getattr(adventure, "selected_tone", None)),
        teaser=str(getattr(adventure, "teaser", "") or "")[:600],
        target_label="Scene" if is_scene else "Theme for",
        name=name[:200],
        description=description[:1500],
        target_kind="scene loop" if is_scene else "main theme",
    )
