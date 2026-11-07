"""ComfyUI music transport (experimental): submit one filled workflow, wait, download its audio.

Mirrors the image transport in ``backend.engine.media.comfyui``: only our own job is polled,
and on timeout only our own queued job is deleted, never another running workflow.
"""

from __future__ import annotations

import asyncio
import re
from contextlib import suppress
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Optional
from uuid import uuid4

import httpx

from backend.utils.path_security import validate_provider_url

MAX_AUDIO_BYTES = 96 * 1024 * 1024
AUDIO_EXTENSIONS = {"flac", "mp3", "wav", "ogg", "opus"}
POLL_SECONDS = 1.0


@dataclass(frozen=True)
class AudioResult:
    data: bytes
    extension: str


async def _request_json(client: httpx.AsyncClient, method: str, path: str, **kwargs: Any) -> Any:
    response = await client.request(method, path, **kwargs)
    if response.is_error:
        raise ValueError(
            f"ComfyUI rejected {method} {path} (HTTP {response.status_code}). Check its server log."
        )
    return response.json()


def _validated_output(entry: dict[str, Any]) -> tuple[dict[str, str], str]:
    filename, subfolder = str(entry.get("filename", "")), str(entry.get("subfolder", ""))
    if not filename or any(part in filename for part in ("/", "\\", "..")):
        raise ValueError("ComfyUI returned an invalid output filename.")
    folder = PurePosixPath(subfolder)
    if folder.is_absolute() or ".." in folder.parts or "\\" in subfolder:
        raise ValueError("ComfyUI returned an invalid output folder.")
    if entry.get("type") != "output":
        raise ValueError("ComfyUI returned an unexpected audio type.")
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in AUDIO_EXTENSIONS:
        raise ValueError(f"ComfyUI returned '{filename}', which is no supported audio file.")
    return {"filename": filename, "subfolder": subfolder, "type": "output"}, extension


def _audio_entries(outputs: dict[str, Any], output_node_id: str) -> list[dict[str, Any]]:
    if output_node_id:
        return list((outputs.get(output_node_id) or {}).get("audio") or [])
    for node_output in outputs.values():
        entries = (node_output or {}).get("audio") or []
        if entries:
            return list(entries)
    return []


def audio_parameters(job: dict[str, Any], output_node_id: str = "") -> Optional[tuple[dict, str]]:
    """Return the download parameters of the finished job, or None while it still runs."""
    status = job.get("status") or {}
    if status.get("status_str") == "error":
        raise ValueError("ComfyUI workflow execution failed. Check its server log.")
    entries = _audio_entries(job.get("outputs") or {}, output_node_id)
    if entries:
        return _validated_output(entries[0])
    if status.get("completed"):
        raise ValueError(
            "ComfyUI finished the workflow without audio. Does it end in a SaveAudio node?"
        )
    return None


async def _download(client: httpx.AsyncClient, parameters: dict[str, str]) -> bytes:
    data = bytearray()
    async with client.stream("GET", "/view", params=parameters) as response:
        response.raise_for_status()
        async for chunk in response.aiter_bytes():
            if len(data) + len(chunk) > MAX_AUDIO_BYTES:
                raise ValueError("ComfyUI audio exceeds the 96 MiB download limit.")
            data.extend(chunk)
    return bytes(data)


async def _run(
    client: httpx.AsyncClient, graph: dict, output_node_id: str, submitted: list[str]
) -> AudioResult:
    reply = await _request_json(
        client, "POST", "/prompt", json={"prompt": graph, "client_id": str(uuid4())}
    )
    prompt_id = str(reply.get("prompt_id", ""))
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", prompt_id):
        raise ValueError("ComfyUI did not return a valid job ID.")
    submitted.append(prompt_id)
    while True:
        history = await _request_json(client, "GET", f"/history/{prompt_id}")
        found = audio_parameters(history.get(prompt_id) or {}, output_node_id)
        if found:
            parameters, extension = found
            return AudioResult(await _download(client, parameters), extension)
        await asyncio.sleep(POLL_SECONDS)


async def render_music(
    graph: dict[str, Any], *, comfyui_url: str, timeout: int, output_node_id: str = ""
) -> AudioResult:
    """Run the already filled ``graph`` on ComfyUI and return the audio file."""
    url = validate_provider_url(comfyui_url).rstrip("/") + "/"
    submitted: list[str] = []
    async with httpx.AsyncClient(base_url=url, timeout=30, follow_redirects=False) as client:
        try:
            return await asyncio.wait_for(_run(client, graph, output_node_id, submitted), timeout)
        except (TimeoutError, asyncio.CancelledError) as exc:
            if submitted:
                with suppress(httpx.HTTPError, ValueError, asyncio.TimeoutError):
                    await asyncio.wait_for(
                        _request_json(client, "POST", "/queue", json={"delete": submitted}), 2
                    )
            if isinstance(exc, TimeoutError):
                raise TimeoutError(
                    f"ComfyUI exceeded the {timeout}-second music generation timeout."
                ) from exc
            raise
