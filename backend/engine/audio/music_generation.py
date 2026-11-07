"""Background rendering of session music tracks (experimental ComfyUI provider).

A track is *ready* once ``adventures/sessions/<session>/music/<track_id>.<ext>`` exists, so the
state in ``entity_states`` never has to be written from a background task (no lost updates
against a running turn). Running jobs and their errors are kept in process memory: after a
restart a missing track is simply rendered again. One job runs at a time, since local music
models usually take the whole GPU.
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
from typing import Any, Literal, Optional

from backend.core.music_settings import normalize_music_settings
from backend.engine.audio.comfyui_music import AUDIO_EXTENSIONS, render_music
from backend.engine.audio.music_state import TRACK_ID_RE
from backend.engine.audio.music_workflow import fill_music_workflow
from backend.utils.path_security import (
    assert_within_data_dir,
    local_path_to_data_url,
    safe_data_path,
    sanitize_path_component,
)

logger = logging.getLogger(__name__)

TrackStatus = Literal["ready", "pending", "failed"]

_jobs: dict[str, asyncio.Task] = {}
_errors: dict[str, str] = {}
_gpu_lock = asyncio.Lock()


def music_dir(session_id: str) -> str:
    safe_session = sanitize_path_component(session_id)
    if not safe_session:
        raise ValueError("Invalid session id for music storage.")
    return safe_data_path("adventures", "sessions", safe_session, "music")


def track_path(session_id: str, track_id: str) -> Optional[str]:
    """Return the local file of a rendered track, or None."""
    if not TRACK_ID_RE.fullmatch(track_id):
        return None
    folder = music_dir(session_id)
    for extension in sorted(AUDIO_EXTENSIONS):
        candidate = os.path.join(folder, f"{track_id}.{extension}")
        if os.path.isfile(candidate):
            return assert_within_data_dir(candidate)
    return None


def track_status(session_id: str, track_id: str) -> tuple[TrackStatus, Optional[str]]:
    """``("ready", url)``, ``("failed", error)`` or ``("pending", None)``."""
    path = track_path(session_id, track_id)
    if path:
        return "ready", local_path_to_data_url(path)
    key = f"{session_id}:{track_id}"
    if key in _errors:
        return "failed", _errors[key]
    return "pending", None


def _write_track(session_id: str, track_id: str, data: bytes, extension: str) -> None:
    folder = music_dir(session_id)
    os.makedirs(folder, exist_ok=True)
    target = assert_within_data_dir(os.path.join(folder, f"{track_id}.{extension}"))
    partial = assert_within_data_dir(target + ".part")
    with open(partial, "wb") as handle:
        handle.write(data)
    # Atomic rename: a half-written file never counts as ready.
    os.replace(partial, target)


def _duration(track: dict[str, Any], settings: dict[str, Any]) -> int:
    requested = track.get("duration") or settings["default_duration"]
    return max(5, min(int(requested), int(settings["max_duration"])))


async def render_track(track: dict[str, Any], settings: dict[str, Any]) -> tuple[bytes, str]:
    """Render one track with the configured workflow; returns (audio bytes, extension)."""
    workflow = settings.get("comfyui_workflow")
    if not workflow:
        raise ValueError("No ComfyUI music workflow is uploaded.")
    graph = fill_music_workflow(
        workflow,
        prompt=str(track.get("prompt") or ""),
        negative_prompt=str(track.get("negative_prompt") or ""),
        seed=int(track.get("seed") or secrets.randbelow(2**31)),
        duration=_duration(track, settings),
    )
    result = await render_music(
        graph,
        comfyui_url=settings["comfyui_url"],
        timeout=int(settings["comfyui_timeout"]),
        output_node_id=str(settings.get("comfyui_output_node_id") or ""),
    )
    return result.data, result.extension


async def _generate(session_id: str, track_id: str, track: dict, settings: dict) -> None:
    key = f"{session_id}:{track_id}"
    try:
        async with _gpu_lock:
            data, extension = await render_track(track, settings)
        _write_track(session_id, track_id, data, extension)
        logger.info("Music track %s of session %s is ready.", track_id, session_id)
    except (ValueError, TimeoutError, OSError) as exc:
        _errors[key] = str(exc)
        logger.warning("Music track %s of session %s failed: %s", track_id, session_id, exc)
    except Exception as exc:  # httpx and provider errors: keep the message for the client
        _errors[key] = f"Music generation failed: {exc}"
        logger.exception("Music track %s of session %s failed.", track_id, session_id)
    finally:
        _jobs.pop(key, None)


def ensure_generation(
    session_id: str, track_id: str, track: dict[str, Any], raw_settings: Optional[dict]
) -> None:
    """Start rendering ``track`` unless it is ready, running or failed."""
    key = f"{session_id}:{track_id}"
    if key in _jobs or key in _errors or track_path(session_id, track_id):
        return
    settings = normalize_music_settings(raw_settings)
    _jobs[key] = asyncio.create_task(_generate(session_id, track_id, dict(track), settings))


def mark_failed(session_id: str, track_id: str, message: str) -> None:
    _errors[f"{session_id}:{track_id}"] = message


def is_generating(session_id: str, track_id: str) -> bool:
    return f"{session_id}:{track_id}" in _jobs
