"""Editor Music tab: the adventure's music library and the scenes' track choice.

Tracks are generated from a prompt (optionally suggested by the small LLM from the adventure's
tone and a reference scene) or uploaded. Rendering runs as a background job (``MusicJobs``)
the editor polls, because a render can take minutes; when it finishes, the job stores the file
in the adventure library and updates the track with its own DB session.
"""

from __future__ import annotations

import os
import secrets
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editor_music_tracks import (
    MAX_UPLOAD_BYTES,
    assign_scene_track,
    release_track,
    replace_file,
    require_track,
    sniff_audio,
    template_scenes,
    update_tracks,
)
from backend.core.auth import get_current_user
from backend.core.database import AsyncSessionLocal, get_db
from backend.core.global_settings import read_server_settings
from backend.core.llm_router import GameMasterLLM
from backend.core.music_settings import music_api_key, normalize_music_settings
from backend.engine.audio.music_assets import save_library_music
from backend.engine.audio.music_jobs import MusicJobs
from backend.engine.audio.music_library import (
    MAX_NAME_CHARS,
    MAX_PROMPT_CHARS,
    new_track_id,
    normalize_tracks,
    now_iso,
)
from backend.engine.audio.music_prompt_context import (
    MUSIC_PROMPT_SYSTEM_PROMPT,
    build_music_prompt_request,
    ensure_loopable,
)
from backend.engine.audio.music_providers import render_exclusive
from backend.engine.audio.music_test_runs import check_provider_ready
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User

router = APIRouter(prefix="/{template_id}/music", tags=["Editor"])

editor_jobs = MusicJobs(max_remembered=100)
# Replaced in tests; background jobs cannot use the request's session.
session_factory = AsyncSessionLocal

TRACK_PATH = Path(..., pattern=r"^[A-Za-z0-9_-]{1,50}$")


class SuggestPayload(BaseModel):
    reference_scene_id: Optional[str] = Field(default=None, max_length=50)


class TrackPayload(BaseModel):
    name: str = Field(default="", max_length=MAX_NAME_CHARS)
    prompt: str = Field(default="", max_length=MAX_PROMPT_CHARS)
    reference_scene_id: Optional[str] = Field(default=None, max_length=50)
    duration: Optional[int] = Field(default=None, ge=5, le=600)


class TrackUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=MAX_NAME_CHARS)
    prompt: Optional[str] = Field(default=None, max_length=MAX_PROMPT_CHARS)
    reference_scene_id: Optional[str] = Field(default=None, max_length=50)


class RenderPayload(BaseModel):
    duration: Optional[int] = Field(default=None, ge=5, le=600)


class SceneTrackPayload(BaseModel):
    track_id: Optional[str] = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,50}$")


async def _owned_adventure(db: AsyncSession, template_id: str, user: User) -> AdventureTemplate:
    adventure = await db.get(AdventureTemplate, template_id)
    if not adventure or adventure.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Adventure template not found")
    return adventure


def _job_overview(template_id: str) -> dict[str, dict[str, Any]]:
    """Latest render job per track (running, or finished but still remembered)."""
    jobs: dict[str, dict[str, Any]] = {}
    for meta, status in editor_jobs.matching(template_id=template_id):
        jobs[meta["track_id"]] = status
    return jobs


async def _library(db: AsyncSession, adventure: AdventureTemplate) -> dict[str, Any]:
    await db.refresh(adventure, ["music_tracks", "music_enabled", "title_track_id"])
    settings = normalize_music_settings((await read_server_settings(db)).music_settings)
    usage: dict[str, list[str]] = {}
    for scene in await template_scenes(db, adventure.id):
        if scene.music_track_id:
            usage.setdefault(scene.music_track_id, []).append(scene.id)
    return {
        "tracks": normalize_tracks(adventure.music_tracks, adventure.id),
        "scene_usage": usage,
        "jobs": _job_overview(adventure.id),
        "music_enabled": bool(adventure.music_enabled),
        "title_track_id": adventure.title_track_id,
        "generation": {"enabled": settings["enabled"], "provider": settings["provider"]},
    }


def _start_render(
    template_id: str, track_id: str, prompt: str, duration: Optional[int], settings: dict, key
) -> dict[str, Any]:
    async def work() -> dict[str, Any]:
        data, extension = await render_exclusive(
            {"prompt": prompt, "duration": duration}, settings, key
        )
        url = save_library_music(template_id, track_id, secrets.token_hex(4), data, extension)

        def store(tracks: list[dict[str, Any]]) -> None:
            track = require_track(tracks, track_id)
            replace_file(track, url, template_id)
            track["source"] = "generated"

        async with session_factory() as db:
            await update_tracks(db, template_id, store)
        return {"url": url, "bytes": len(data)}

    return editor_jobs.start(work, {"template_id": template_id, "track_id": track_id})


async def _render_settings(db: AsyncSession, user: User) -> tuple[dict, Optional[str]]:
    settings = normalize_music_settings((await read_server_settings(db)).music_settings)
    if not settings["enabled"]:
        raise HTTPException(status_code=400, detail="Music generation is switched off (Admin).")
    api_key = music_api_key(user, settings)
    try:
        check_provider_ready(settings, api_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return settings, api_key


@router.get("")
async def get_music_library(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return await _library(db, await _owned_adventure(db, template_id, current_user))


@router.post("/suggest-prompt")
async def suggest_music_prompt(
    template_id: str,
    payload: SuggestPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """AI prompt from the adventure's tone and the reference scene (or premise); loopable."""
    adventure = await _owned_adventure(db, template_id, current_user)
    scenes = {s.id: s for s in await template_scenes(db, template_id)}
    scene = scenes.get(payload.reference_scene_id or "")
    if payload.reference_scene_id and scene is None:
        raise HTTPException(status_code=404, detail="Scene not found")
    if scene is not None:
        name, description, kind = str(scene.label or scene.id), scene.description or "", "scene"
    else:
        name = adventure.title or ""
        description = adventure.plot or adventure.teaser or adventure.original_prompt or ""
        kind = "main theme"
    llm_settings = current_user.llm_settings or {}
    provider = (
        llm_settings.get("small_model_provider")
        or llm_settings.get("complex_model_provider")
        or llm_settings.get("preferred_provider")
        or "openai"
    )
    llm = GameMasterLLM(user=current_user, provider=provider, model_category="small")
    raw = await llm.aexecute_simple_task(
        system_prompt=MUSIC_PROMPT_SYSTEM_PROMPT,
        user_prompt=build_music_prompt_request(
            adventure, target_kind=kind, name=name, description=description
        ),
        model=llm_settings.get("small_model") or "gpt-4o-mini",
        adventure_id=template_id,
    )
    return {"suggested_prompt": ensure_loopable(raw)}


@router.post("/tracks")
async def create_generated_track(
    template_id: str,
    payload: TrackPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Add a track and start rendering it; poll ``GET /jobs/{id}``."""
    await _owned_adventure(db, template_id, current_user)
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Enter a music prompt first.")
    settings, api_key = await _render_settings(db, current_user)
    track = {
        "id": new_track_id(),
        "name": payload.name.strip() or prompt[:40],
        "prompt": prompt,
        "url": None,
        "source": "generated",
        "reference_scene_id": payload.reference_scene_id or None,
        "created_at": now_iso(),
    }
    await update_tracks(db, template_id, lambda tracks: tracks.append(track))
    job = _start_render(template_id, track["id"], prompt, payload.duration, settings, api_key)
    return {"track": track, "job": job}


@router.post("/tracks/{track_id}/render")
async def render_track_again(
    template_id: str,
    payload: RenderPayload,
    track_id: str = TRACK_PATH,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """(Re-)render a track from its prompt, e.g. a track the World-Builder planned."""
    adventure = await _owned_adventure(db, template_id, current_user)
    track = require_track(normalize_tracks(adventure.music_tracks, template_id), track_id)
    if not track["prompt"]:
        raise HTTPException(status_code=400, detail="This track has no prompt to render.")
    settings, api_key = await _render_settings(db, current_user)
    return _start_render(
        template_id, track_id, track["prompt"], payload.duration, settings, api_key
    )


@router.post("/tracks/upload")
async def upload_track(
    template_id: str,
    file: UploadFile = File(...),
    name: str = Form(default="", max_length=MAX_NAME_CHARS),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Add an uploaded audio file (MP3, WAV, OGG/Opus, FLAC, M4A; max 50 MB) to the library."""
    await _owned_adventure(db, template_id, current_user)
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="The audio file is larger than 50 MB.")
    original = os.path.basename(file.filename or "upload")
    extension = sniff_audio(data, original)
    track_id = new_track_id()
    url = save_library_music(template_id, track_id, secrets.token_hex(4), data, extension)
    track = {
        "id": track_id,
        "name": name.strip() or os.path.splitext(original)[0][:MAX_NAME_CHARS] or track_id,
        "prompt": "",
        "url": url,
        "source": "uploaded",
        "reference_scene_id": None,
        "created_at": now_iso(),
    }
    await update_tracks(db, template_id, lambda tracks: tracks.append(track))
    return {"track": track}


@router.patch("/tracks/{track_id}")
async def update_track(
    template_id: str,
    payload: TrackUpdate,
    track_id: str = TRACK_PATH,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    await _owned_adventure(db, template_id, current_user)
    changes = payload.model_dump(exclude_unset=True)

    def change(tracks: list[dict[str, Any]]) -> dict[str, Any]:
        track = require_track(tracks, track_id)
        for field, value in changes.items():
            track[field] = (value or "").strip() or (None if field != "name" else track["name"])
        return dict(track)

    return {"track": await update_tracks(db, template_id, change)}


@router.delete("/tracks/{track_id}")
async def delete_track(
    template_id: str,
    track_id: str = TRACK_PATH,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Delete the track and its file; scenes that used it become silent."""
    adventure = await _owned_adventure(db, template_id, current_user)

    def change(tracks: list[dict[str, Any]]) -> None:
        track = require_track(tracks, track_id)
        replace_file(track, "", template_id)
        tracks.remove(track)

    await update_tracks(db, template_id, change)
    await release_track(db, adventure, track_id)
    if adventure.title_track_id == track_id:
        adventure.title_track_id = None
        await db.commit()
    return await _library(db, adventure)


@router.get("/jobs/{job_id}")
async def get_music_job(
    template_id: str,
    job_id: str = Path(..., pattern=r"^[a-f0-9]{16}$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    await _owned_adventure(db, template_id, current_user)
    meta = editor_jobs.meta(job_id)
    if not meta or meta["template_id"] != template_id:
        raise HTTPException(status_code=404, detail="Music job not found (the server restarted?).")
    return {**(editor_jobs.status(job_id) or {}), "track_id": meta["track_id"]}


@router.post("/scenes/{scene_id}/track")
async def set_scene_track(
    template_id: str,
    payload: SceneTrackPayload,
    scene_id: str = Path(..., max_length=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Choose the scene's track (``null`` = silent scene)."""
    adventure = await _owned_adventure(db, template_id, current_user)
    scene = await assign_scene_track(db, adventure, scene_id, payload.track_id)
    return {"scene_id": scene.id, "music_track_id": scene.music_track_id}


@router.post("/title")
async def set_title_track(
    template_id: str,
    payload: SceneTrackPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Choose the title song played on the library tile (``null`` = no title song)."""
    adventure = await _owned_adventure(db, template_id, current_user)
    if payload.track_id:
        require_track(normalize_tracks(adventure.music_tracks, template_id), payload.track_id)
    adventure.title_track_id = payload.track_id or None
    await db.commit()
    return {"title_track_id": adventure.title_track_id}
