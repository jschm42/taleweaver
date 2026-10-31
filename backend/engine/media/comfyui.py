"""ComfyUI queue transport. Submit once, poll only our job, download its output."""

import asyncio
import base64
import re
from contextlib import suppress
from pathlib import PurePosixPath
from typing import Any
from uuid import uuid4

import httpx

from backend.core.comfyui import ComfyTestOptions, build_workflow
from backend.utils.path_security import validate_provider_url

MAX_IMAGE_BYTES = 32 * 1024 * 1024


async def _json(client: httpx.AsyncClient, method: str, path: str, **kwargs: Any) -> Any:
    response = await client.request(method, path, **kwargs)
    if response.is_error:
        raise ValueError(
            f"ComfyUI rejected {method} {path} (HTTP {response.status_code}). Check its server log."
        )
    return response.json()


def _image_parameters(job: dict[str, Any]) -> dict[str, str] | None:
    status = job.get("status") or {}
    if status.get("status_str") == "error":
        raise ValueError(
            "ComfyUI workflow execution failed. Check its server log and checkpoint compatibility."
        )
    images = ((job.get("outputs") or {}).get("7") or {}).get("images") or []
    if not images:
        if status.get("completed"):
            raise ValueError("ComfyUI completed the workflow without an image.")
        return None
    image = images[0]
    filename, subfolder = str(image.get("filename", "")), str(image.get("subfolder", ""))
    if not filename or any(part in filename for part in ("/", "\\", "..")):
        raise ValueError("ComfyUI returned an invalid output filename.")
    if (
        PurePosixPath(subfolder).is_absolute()
        or ".." in PurePosixPath(subfolder).parts
        or "\\" in subfolder
    ):
        raise ValueError("ComfyUI returned an invalid output folder.")
    if image.get("type") != "output":
        raise ValueError("ComfyUI returned an unexpected image type.")
    return {"filename": filename, "subfolder": subfolder, "type": "output"}


async def _download(client: httpx.AsyncClient, parameters: dict[str, str]) -> bytes:
    data = bytearray()
    async with client.stream("GET", "/view", params=parameters) as response:
        response.raise_for_status()
        async for chunk in response.aiter_bytes():
            if len(data) + len(chunk) > MAX_IMAGE_BYTES:
                raise ValueError("ComfyUI image exceeds the 32 MiB download limit.")
            data.extend(chunk)
    return bytes(data)


async def _run(client: httpx.AsyncClient, graph: dict, submitted: list[str]) -> bytes:
    reply = await _json(
        client, "POST", "/prompt", json={"prompt": graph, "client_id": str(uuid4())}
    )
    prompt_id = str(reply.get("prompt_id", ""))
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", prompt_id):
        raise ValueError("ComfyUI did not return a valid job ID.")
    submitted.append(prompt_id)
    while True:
        history = await _json(client, "GET", f"/history/{prompt_id}")
        parameters = _image_parameters(history.get(prompt_id) or {})
        if parameters:
            return await _download(client, parameters)
        await asyncio.sleep(0.5)


async def render(prompt: str, model: str, options: dict[str, Any]) -> bytes:
    config = ComfyTestOptions.model_validate(options)
    url = validate_provider_url(config.comfyui_url).rstrip("/") + "/"
    graph = build_workflow(prompt, model, options)
    submitted: list[str] = []
    async with httpx.AsyncClient(base_url=url, timeout=30, follow_redirects=False) as client:
        try:
            return await asyncio.wait_for(_run(client, graph, submitted), config.comfyui_timeout)
        except (TimeoutError, asyncio.CancelledError) as exc:
            if submitted:
                # Delete this queued job only. Never interrupt another running workflow.
                with suppress(httpx.HTTPError, ValueError, asyncio.TimeoutError):
                    await asyncio.wait_for(
                        _json(client, "POST", "/queue", json={"delete": submitted}), 2
                    )
            if isinstance(exc, TimeoutError):
                raise TimeoutError(
                    f"ComfyUI exceeded its {config.comfyui_timeout}-second generation timeout. "
                    "A remotely running job may still finish; no replacement was submitted."
                ) from exc
            raise


async def generate_image(
    prompt: str,
    model: str,
    api_key: str | None,
    target_dir: str,
    filename: str | None,
    provider_options: dict[str, Any],
) -> str | None:
    from backend.engine.media.media_engine import MediaEngine

    data = await render(prompt, model, provider_options)
    return await MediaEngine._save_b64_image(
        base64.b64encode(data).decode("ascii"),
        target_dir,
        filename,
        image_format=provider_options.get("image_format") or "jpeg",
        quality=provider_options.get("image_quality") or 85,
    )
