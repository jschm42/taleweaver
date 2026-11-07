"""Admin test renders of the music workflow, run in the background and polled by id.

A render can take minutes (ComfyUI loads the model on the first run), far longer than an HTTP
request may stay open, so the admin UI starts a run and polls its status instead of waiting.
Runs are kept in process memory; only the newest few are remembered.
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
import time
from typing import Any, Optional

import httpx

from backend.engine.audio.music_generation import render_exclusive
from backend.utils.path_security import (
    assert_within_data_dir,
    local_path_to_data_url,
    safe_data_path,
)

logger = logging.getLogger(__name__)

MAX_REMEMBERED_RUNS = 10

_runs: dict[str, dict[str, Any]] = {}
_tasks: dict[str, asyncio.Task] = {}


def _save(data: bytes, extension: str) -> str:
    folder = safe_data_path("scratch", "music_test")
    os.makedirs(folder, exist_ok=True)
    target = assert_within_data_dir(os.path.join(folder, f"{secrets.token_hex(8)}.{extension}"))
    with open(target, "wb") as handle:
        handle.write(data)
    return local_path_to_data_url(target)


def _finish(run: dict[str, Any], **values: Any) -> None:
    run.update(values, finished_at=time.time())


async def _execute(run_id: str, track: dict[str, Any], settings: dict[str, Any]) -> None:
    run = _runs[run_id]
    try:
        data, extension = await render_exclusive(track, settings)
        _finish(run, status="done", url=_save(data, extension), bytes=len(data))
    except (ValueError, TimeoutError, OSError) as exc:
        _finish(run, status="failed", error=str(exc))
    except httpx.HTTPError as exc:
        _finish(run, status="failed", error=f"ComfyUI is not reachable: {exc}")
    except Exception as exc:  # keep any provider error visible in the admin UI
        logger.exception("Music test run %s failed.", run_id)
        _finish(run, status="failed", error=f"Music generation failed: {exc}")
    finally:
        _tasks.pop(run_id, None)


def _forget_old_runs() -> None:
    finished = [rid for rid, run in _runs.items() if run["status"] != "running"]
    for run_id in finished[: max(0, len(_runs) - MAX_REMEMBERED_RUNS + 1)]:
        _runs.pop(run_id, None)


def start_test_run(track: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    """Start a background render and return its public status."""
    if not settings.get("comfyui_workflow"):
        raise ValueError("No ComfyUI music workflow is uploaded.")
    _forget_old_runs()
    run_id = secrets.token_hex(8)
    _runs[run_id] = {"id": run_id, "status": "running", "started_at": time.time()}
    _tasks[run_id] = asyncio.create_task(_execute(run_id, dict(track), settings))
    return music_test_status(run_id) or {}


def music_test_status(run_id: str) -> Optional[dict[str, Any]]:
    """Public status of a run: running / done (url, bytes) / failed (error), plus elapsed seconds."""
    run = _runs.get(run_id)
    if run is None:
        return None
    end = run.get("finished_at") or time.time()
    public = {k: v for k, v in run.items() if k not in {"started_at", "finished_at"}}
    public["elapsed"] = round(end - run["started_at"])
    return public
