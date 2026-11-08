"""Admin settings for audio generation (experimental ComfyUI workflow upload) and a test run."""

from __future__ import annotations

import json
import os
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Path, UploadFile
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.audio_settings import (
    MAX_WORKFLOW_BYTES,
    AudioSettings,
    audio_api_key,
    normalize_audio_settings,
    public_audio_settings,
    validate_audio_workflow,
)
from backend.core.auth import get_current_admin
from backend.core.database import get_db
from backend.core.global_settings import get_server_settings_for_update, read_server_settings
from backend.engine.audio.audio_test_runs import audio_test_status, start_test_run
from backend.models.user import User

router = APIRouter(prefix="/settings/audio", tags=["Settings"])


class AudioSettingsPayload(BaseModel):
    """Everything except the workflow, which has its own upload endpoint."""

    enabled: bool = False
    comfyui_url: str = "http://127.0.0.1:8188"
    comfyui_timeout: int = Field(default=900, ge=1, le=3600)
    comfyui_output_node_id: str = Field(default="", max_length=64)
    default_duration: int = Field(default=30, ge=5, le=300)
    max_duration: int = Field(default=120, ge=5, le=600)
    max_generations_per_session: int = Field(default=20, ge=0, le=500)
    provider: Literal["comfyui", "lyria"] = "comfyui"
    lyria_clip_model: str = Field(default="lyria-3-clip-preview", min_length=1, max_length=100)
    lyria_full_model: str = Field(default="lyria-3.5", min_length=1, max_length=100)
    lyria_timeout: int = Field(default=300, ge=10, le=1800)
    lyria_wav: bool = False


class AudioTestPayload(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=1000)
    duration: Optional[int] = Field(default=None, ge=5, le=600)


async def _store(db: AsyncSession, values: dict[str, Any]) -> dict[str, Any]:
    server = await get_server_settings_for_update(db)
    merged = {**normalize_audio_settings(server.audio_settings), **values}
    try:
        server.audio_settings = AudioSettings.model_validate(merged).model_dump()
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc.errors()[0]["msg"])) from exc
    await db.commit()
    return public_audio_settings(server.audio_settings)


@router.get("")
async def get_audio_settings(
    db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_admin)
) -> dict[str, Any]:
    return public_audio_settings((await read_server_settings(db)).audio_settings)


@router.post("")
async def update_audio_settings(
    payload: AudioSettingsPayload,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    return await _store(db, payload.model_dump())


@router.post("/workflow")
async def upload_audio_workflow(
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
        validate_audio_workflow(workflow)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="The file is not valid JSON.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    name = os.path.basename(file.filename or "workflow.json")[:200]
    return await _store(db, {"comfyui_workflow": workflow, "comfyui_workflow_name": name})


@router.delete("/workflow")
async def delete_audio_workflow(
    db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_admin)
) -> dict[str, Any]:
    return await _store(db, {"comfyui_workflow": None, "comfyui_workflow_name": ""})


@router.post("/test")
async def start_audio_test(
    payload: AudioTestPayload,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """Start rendering one clip with the stored workflow; poll ``GET /test/{id}`` for the result.

    The render runs in the background because it can take minutes (model loading on the first
    run), much longer than a browser request may stay open.
    """
    settings = normalize_audio_settings((await read_server_settings(db)).audio_settings)
    track = {"prompt": payload.prompt, "duration": payload.duration}
    try:
        return start_test_run(track, settings, audio_api_key(admin, settings))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/test/{run_id}")
async def get_audio_test(
    run_id: str = Path(..., pattern=r"^[a-f0-9]{16}$"),
    _admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """Status of a test run: running, done (url, bytes) or failed (error); plus elapsed seconds."""
    status = audio_test_status(run_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Test run not found (the server restarted?).")
    return status
