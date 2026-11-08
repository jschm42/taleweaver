"""Background rendering of session audio tracks (ComfyUI or Lyria, see audio_providers).

A track is *ready* once ``adventures/sessions/<session>/audio/<track_id>.<ext>`` exists, so the
state in ``entity_states`` never has to be written from a background task (no lost updates
against a running turn). Running jobs and their errors are kept in process memory: after a
restart a missing track is simply rendered again. Concurrency per provider is limited in
``audio_providers.render_exclusive``.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Literal, Optional

from backend.core.audio_settings import normalize_audio_settings
from backend.engine.audio.audio_providers import render_exclusive
from backend.engine.audio.audio_state import TRACK_ID_RE
from backend.engine.audio.comfyui_audio import AUDIO_EXTENSIONS
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


def audio_dir(session_id: str) -> str:
    safe_session = sanitize_path_component(session_id)
    if not safe_session:
        raise ValueError("Invalid session id for audio storage.")
    return safe_data_path("adventures", "sessions", safe_session, "audio")


def track_path(session_id: str, track_id: str) -> Optional[str]:
    """Return the local file of a rendered track, or None."""
    if not TRACK_ID_RE.fullmatch(track_id):
        return None
    # Tracks rendered before the rename to audio live in the session's music/ folder.
    folders = (audio_dir(session_id), os.path.join(os.path.dirname(audio_dir(session_id)), "music"))
    for folder in folders:
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
    folder = audio_dir(session_id)
    os.makedirs(folder, exist_ok=True)
    target = assert_within_data_dir(os.path.join(folder, f"{track_id}.{extension}"))
    partial = assert_within_data_dir(target + ".part")
    with open(partial, "wb") as handle:
        handle.write(data)
    # Atomic rename: a half-written file never counts as ready.
    os.replace(partial, target)


async def _generate(
    session_id: str, track_id: str, track: dict, settings: dict, api_key: Optional[str]
) -> None:
    key = f"{session_id}:{track_id}"
    try:
        data, extension = await render_exclusive(track, settings, api_key)
        _write_track(session_id, track_id, data, extension)
        logger.info("Audio track %s of session %s is ready.", track_id, session_id)
    except (ValueError, TimeoutError, OSError) as exc:
        _errors[key] = str(exc)
        logger.warning("Audio track %s of session %s failed: %s", track_id, session_id, exc)
    except Exception as exc:  # httpx and provider errors: keep the message for the client
        _errors[key] = f"Audio generation failed: {exc}"
        logger.exception("Audio track %s of session %s failed.", track_id, session_id)
    finally:
        _jobs.pop(key, None)


def ensure_generation(
    session_id: str,
    track_id: str,
    track: dict[str, Any],
    raw_settings: Optional[dict],
    api_key: Optional[str] = None,
) -> None:
    """Start rendering ``track`` unless it is ready, running or failed."""
    key = f"{session_id}:{track_id}"
    if key in _jobs or key in _errors or track_path(session_id, track_id):
        return
    settings = normalize_audio_settings(raw_settings)
    _jobs[key] = asyncio.create_task(
        _generate(session_id, track_id, dict(track), settings, api_key)
    )


def mark_failed(session_id: str, track_id: str, message: str) -> None:
    _errors[f"{session_id}:{track_id}"] = message


def is_generating(session_id: str, track_id: str) -> bool:
    return f"{session_id}:{track_id}" in _jobs
