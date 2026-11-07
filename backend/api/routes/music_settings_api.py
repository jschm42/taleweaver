"""Admin settings for music generation (experimental ComfyUI workflow upload) and a test run."""

from __future__ import annotations

import json
import os
import secrets
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import get_current_admin
from backend.core.database import get_db
from backend.core.global_settings import get_server_settings_for_update, read_server_settings
from backend.core.music_settings import (
    MAX_WORKFLOW_BYTES,
    MusicSettings,
    normalize_music_settings,
    public_music_settings,
    validate_music_workflow,
)
from backend.engine.audio.music_generation import render_track
from backend.models.user import User
from backend.utils.path_security import (
    assert_within_data_dir,
    local_path_to_data_url,
    safe_data_path,
)

router = APIRouter(prefix="/settings/music", tags=["Settings"])


class MusicSettingsPayload(BaseModel):
    """Everything except the workflow, which has its own upload endpoint."""

    enabled: bool = False
    comfyui_url: str = "http://127.0.0.1:8188"
    comfyui_timeout: int = Field(default=900, ge=1, le=3600)
    comfyui_output_node_id: str = Field(default="", max_length=64)
    default_duration: int = Field(default=30, ge=5, le=300)
    max_duration: int = Field(default=120, ge=5, le=600)
    max_generations_per_session: int = Field(default=20, ge=0, le=500)


class MusicTestPayload(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=1000)
    duration: Optional[int] = Field(default=None, ge=5, le=600)


async def _store(db: AsyncSession, values: dict[str, Any]) -> dict[str, Any]:
    server = await get_server_settings_for_update(db)
    merged = {**normalize_music_settings(server.music_settings), **values}
    try:
        server.music_settings = MusicSettings.model_validate(merged).model_dump()
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc.errors()[0]["msg"])) from exc
    await db.commit()
    return public_music_settings(server.music_settings)


@router.get("")
async def get_music_settings(
    db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_admin)
) -> dict[str, Any]:
    return public_music_settings((await read_server_settings(db)).music_settings)


@router.post("")
async def update_music_settings(
    payload: MusicSettingsPayload,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    return await _store(db, payload.model_dump())


@router.post("/workflow")
async def upload_music_workflow(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """Store an API-format ComfyUI workflow (JSON file) with a {{prompt}} placeholder."""
    raw = await file.read(MAX_WORKFLOW_BYTES + 1)
    if len(raw) > MAX_WORKFLOW_BYTES:
        raise HTTPException(status_code=400, detail="The workflow is larger than 512 KiB.")
    try:
        workflow = json.loads(raw.decode("utf-8"))
        validate_music_workflow(workflow)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="The file is not valid JSON.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    name = os.path.basename(file.filename or "workflow.json")[:200]
    return await _store(db, {"comfyui_workflow": workflow, "comfyui_workflow_name": name})


@router.delete("/workflow")
async def delete_music_workflow(
    db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_admin)
) -> dict[str, Any]:
    return await _store(db, {"comfyui_workflow": None, "comfyui_workflow_name": ""})


@router.post("/test")
async def test_music_generation(
    payload: MusicTestPayload,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """Render one clip with the stored workflow and return its URL (waits for ComfyUI)."""
    settings = normalize_music_settings((await read_server_settings(db)).music_settings)
    track = {"prompt": payload.prompt, "duration": payload.duration}
    try:
        data, extension = await render_track(track, settings)
    except (ValueError, TimeoutError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"ComfyUI is not reachable: {exc}") from exc
    folder = safe_data_path("scratch", "music_test")
    os.makedirs(folder, exist_ok=True)
    target = assert_within_data_dir(os.path.join(folder, f"{secrets.token_hex(8)}.{extension}"))
    with open(target, "wb") as handle:
        handle.write(data)
    return {"url": local_path_to_data_url(target), "bytes": len(data)}
