"""Google Lyria audio transport (Gemini Interactions API).

``POST /v1beta/interactions`` with ``{"model", "input"}``; the response lists ``steps`` whose
``model_output`` content holds base64 audio blocks. Lyria 3 Clip always returns 30-second MP3
clips; Lyria 3.5 returns longer tracks (length follows the prompt), MP3 by default or WAV with
``response_format: {"type": "audio"}``. There are no seed, duration or negative-prompt fields,
so those are folded into the prompt text.
"""

from __future__ import annotations

import base64
import binascii
from typing import Any, Optional

import httpx

from backend.engine.audio.comfyui_audio import MAX_AUDIO_BYTES, AudioResult

INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
API_REVISION = "2026-05-20"
CLIP_SECONDS = 30
INSTRUMENTAL_NOTE = "Instrumental only, no vocals, no lyrics."

_MIME_EXTENSIONS = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
}


def lyria_prompt(prompt: str, negative_prompt: str, duration: Optional[int], full: bool) -> str:
    """Prompt text for Lyria; length and exclusions can only be asked for in words."""
    parts = [prompt.strip().rstrip(".") + "."]
    if full and duration:
        parts.append(f"About {int(duration)} seconds long.")
    if negative_prompt.strip():
        parts.append(f"Avoid: {negative_prompt.strip()}.")
    parts.append(INSTRUMENTAL_NOTE)
    return " ".join(parts)


def _audio_blocks(reply: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for step in reply.get("steps") or []:
        if not isinstance(step, dict) or step.get("type") != "model_output":
            continue
        blocks.extend(
            c for c in step.get("content") or [] if isinstance(c, dict) and c.get("type") == "audio"
        )
    return blocks


def parse_lyria_reply(reply: dict[str, Any], wav: bool) -> AudioResult:
    """Decode the first audio block of an Interactions reply."""
    blocks = _audio_blocks(reply)
    if not blocks:
        raise ValueError(
            "Lyria returned no audio. The prompt may have been blocked by the safety filter "
            "(for example artist names or song lyrics)."
        )
    block = blocks[0]
    try:
        data = base64.b64decode(str(block.get("data") or ""), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Lyria returned invalid audio data.") from exc
    if not data or len(data) > MAX_AUDIO_BYTES:
        raise ValueError("Lyria returned empty or oversized audio.")
    mime = str(block.get("mime_type") or block.get("mimeType") or "").lower()
    extension = _MIME_EXTENSIONS.get(mime) or ("wav" if wav else "mp3")
    return AudioResult(data, extension)


def _error_detail(response: httpx.Response) -> str:
    try:
        message = (response.json().get("error") or {}).get("message")
    except ValueError:
        message = None
    return str(message or response.text[:200] or f"HTTP {response.status_code}")


async def render_lyria(
    prompt: str, *, model: str, api_key: str, timeout: int, wav: bool = False
) -> AudioResult:
    """Render one track with a Lyria model and return the audio file."""
    if not api_key:
        raise ValueError("Lyria needs a Google (Gemini) API key.")
    body: dict[str, Any] = {"model": model, "input": prompt}
    if wav:
        body["response_format"] = {"type": "audio"}
    headers = {
        "Content-Type": "application/json",
        "Api-Revision": API_REVISION,
        "x-goog-api-key": api_key,
    }
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        response = await client.post(INTERACTIONS_URL, json=body, headers=headers)
    if response.is_error:
        raise ValueError(f"Lyria rejected the request: {_error_detail(response)}")
    return parse_lyria_reply(response.json(), wav)
