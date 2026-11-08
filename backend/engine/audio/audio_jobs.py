"""In-memory registry of background audio renders that a UI polls by id.

A render can take minutes (model loading on the first ComfyUI run), far longer than an HTTP
request may stay open, so routes start a job and the UI polls its status. Jobs live in process
memory; only the newest finished ones are remembered. ``meta`` carries what a route needs to
check ownership and is never shown to clients.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from collections.abc import Awaitable, Callable
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

JobWork = Callable[[], Awaitable[dict[str, Any]]]


class AudioJobs:
    """Starts renders as asyncio tasks and keeps their public status."""

    def __init__(self, max_remembered: int = 20):
        self._max = max_remembered
        self._jobs: dict[str, dict[str, Any]] = {}
        self.tasks: dict[str, asyncio.Task] = {}

    def _finish(self, job: dict[str, Any], **values: Any) -> None:
        job.update(values, finished_at=time.time())

    async def _run(self, job_id: str, work: JobWork) -> None:
        job = self._jobs[job_id]
        try:
            self._finish(job, status="done", **(await work()))
        except (ValueError, TimeoutError, OSError) as exc:
            self._finish(job, status="failed", error=str(exc))
        except httpx.HTTPError as exc:
            self._finish(job, status="failed", error=f"Audio provider is not reachable: {exc}")
        except Exception as exc:  # keep any provider error visible in the UI
            logger.exception("Audio job %s failed.", job_id)
            self._finish(job, status="failed", error=f"Audio generation failed: {exc}")
        finally:
            self.tasks.pop(job_id, None)

    def _forget_old(self) -> None:
        finished = [jid for jid, job in self._jobs.items() if job["status"] != "running"]
        for job_id in finished[: max(0, len(self._jobs) - self._max + 1)]:
            self._jobs.pop(job_id, None)

    def start(self, work: JobWork, meta: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        self._forget_old()
        job_id = secrets.token_hex(8)
        self._jobs[job_id] = {
            "id": job_id,
            "status": "running",
            "started_at": time.time(),
            "meta": dict(meta or {}),
        }
        self.tasks[job_id] = asyncio.create_task(self._run(job_id, work))
        return self.status(job_id) or {}

    def matching(self, **filters: Any) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        """``(meta, status)`` of every remembered job whose meta matches ``filters``."""
        found = []
        for job_id, job in self._jobs.items():
            meta = job["meta"]
            if all(meta.get(key) == value for key, value in filters.items()):
                found.append((meta, self.status(job_id) or {}))
        return found

    def meta(self, job_id: str) -> Optional[dict[str, Any]]:
        job = self._jobs.get(job_id)
        return job["meta"] if job else None

    def status(self, job_id: str) -> Optional[dict[str, Any]]:
        """``running`` / ``done`` (result fields) / ``failed`` (error), plus elapsed seconds."""
        job = self._jobs.get(job_id)
        if job is None:
            return None
        end = job.get("finished_at") or time.time()
        hidden = {"started_at", "finished_at", "meta"}
        public = {k: v for k, v in job.items() if k not in hidden}
        public["elapsed"] = round(end - job["started_at"])
        return public
