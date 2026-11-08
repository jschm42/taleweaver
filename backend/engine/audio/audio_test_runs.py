"""Admin test renders of the audio settings, run in the background and polled by id."""

from __future__ import annotations

import os
import secrets
from typing import Any, Optional

from backend.engine.audio.audio_jobs import AudioJobs
from backend.engine.audio.audio_providers import render_exclusive
from backend.utils.path_security import (
    assert_within_data_dir,
    local_path_to_data_url,
    safe_data_path,
)

test_jobs = AudioJobs(max_remembered=10)


def _save(data: bytes, extension: str) -> str:
    folder = safe_data_path("scratch", "audio_test")
    os.makedirs(folder, exist_ok=True)
    target = assert_within_data_dir(os.path.join(folder, f"{secrets.token_hex(8)}.{extension}"))
    with open(target, "wb") as handle:
        handle.write(data)
    return local_path_to_data_url(target)


def check_provider_ready(settings: dict[str, Any], api_key: Optional[str]) -> None:
    """Raise ``ValueError`` when the configured provider cannot render at all."""
    if settings.get("provider") == "lyria":
        if not api_key:
            raise ValueError("Lyria needs a Google (Gemini) API key in the Provider Vault.")
        return
    if not settings.get("comfyui_workflow"):
        raise ValueError("No ComfyUI audio workflow is uploaded.")


def start_test_run(
    track: dict[str, Any], settings: dict[str, Any], api_key: Optional[str] = None
) -> dict[str, Any]:
    """Start a background render and return its public status."""
    check_provider_ready(settings, api_key)

    async def work() -> dict[str, Any]:
        data, extension = await render_exclusive(dict(track), settings, api_key)
        return {"url": _save(data, extension), "bytes": len(data)}

    return test_jobs.start(work)


def audio_test_status(run_id: str) -> Optional[dict[str, Any]]:
    return test_jobs.status(run_id)
