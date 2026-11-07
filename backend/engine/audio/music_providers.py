"""Music providers: one ``render`` entry point for ComfyUI workflows and Google Lyria.

Every render (session music, editor scene music, admin test) goes through ``render_exclusive``,
which limits how many renders run at once per provider: ComfyUI one (a local GPU), Lyria a few
parallel API calls. Each render is logged as ``music.render`` for the telemetry tools.
"""

from __future__ import annotations

import asyncio
import secrets
import time
from typing import Any, Optional

from backend.core.llm_logger import log_structured_event
from backend.engine.audio.comfyui_music import AudioResult, render_music
from backend.engine.audio.lyria_music import CLIP_SECONDS, lyria_prompt, render_lyria
from backend.engine.audio.music_workflow import fill_music_workflow

LYRIA_PARALLEL_RENDERS = 2

_limits: dict[str, asyncio.Semaphore] = {}


def _limit(provider: str) -> asyncio.Semaphore:
    if provider not in _limits:
        _limits[provider] = asyncio.Semaphore(LYRIA_PARALLEL_RENDERS if provider == "lyria" else 1)
    return _limits[provider]


def track_duration(track: dict[str, Any], settings: dict[str, Any]) -> int:
    requested = track.get("duration") or settings["default_duration"]
    return max(5, min(int(requested), int(settings["max_duration"])))


async def _render_comfyui(track: dict[str, Any], settings: dict[str, Any]) -> AudioResult:
    workflow = settings.get("comfyui_workflow")
    if not workflow:
        raise ValueError("No ComfyUI music workflow is uploaded.")
    graph = fill_music_workflow(
        workflow,
        prompt=str(track.get("prompt") or ""),
        negative_prompt=str(track.get("negative_prompt") or ""),
        seed=int(track.get("seed") or secrets.randbelow(2**31)),
        duration=track_duration(track, settings),
    )
    return await render_music(
        graph,
        comfyui_url=settings["comfyui_url"],
        timeout=int(settings["comfyui_timeout"]),
        output_node_id=str(settings.get("comfyui_output_node_id") or ""),
    )


def lyria_model_for(track: dict[str, Any], settings: dict[str, Any]) -> tuple[str, bool]:
    """(model, is_full_model): short loops use the 30-second clip model."""
    if track_duration(track, settings) <= CLIP_SECONDS:
        return settings["lyria_clip_model"], False
    return settings["lyria_full_model"], True


async def _render_lyria(
    track: dict[str, Any], settings: dict[str, Any], api_key: Optional[str]
) -> AudioResult:
    model, full = lyria_model_for(track, settings)
    prompt = lyria_prompt(
        str(track.get("prompt") or ""),
        str(track.get("negative_prompt") or ""),
        track_duration(track, settings),
        full,
    )
    return await render_lyria(
        prompt,
        model=model,
        api_key=api_key or "",
        timeout=int(settings["lyria_timeout"]),
        wav=bool(full and settings.get("lyria_wav")),
    )


async def render_track(
    track: dict[str, Any], settings: dict[str, Any], api_key: Optional[str] = None
) -> tuple[bytes, str]:
    """Render one track with the configured provider; returns (audio bytes, extension)."""
    if settings.get("provider") == "lyria":
        result = await _render_lyria(track, settings, api_key)
    else:
        result = await _render_comfyui(track, settings)
    return result.data, result.extension


async def render_exclusive(
    track: dict[str, Any], settings: dict[str, Any], api_key: Optional[str] = None
) -> tuple[bytes, str]:
    """``render_track`` within the provider's concurrency limit, with telemetry."""
    provider = str(settings.get("provider") or "comfyui")
    async with _limit(provider):
        started = time.monotonic()
        ok = False
        size = 0
        try:
            data, extension = await render_track(track, settings, api_key)
            ok, size = True, len(data)
            return data, extension
        finally:
            log_structured_event(
                "music.render",
                provider=provider,
                seconds=round(time.monotonic() - started, 2),
                bytes=size,
                ok=ok,
            )
