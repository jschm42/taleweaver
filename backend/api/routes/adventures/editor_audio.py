"""Editor Audio tab: the adventure's audio library and the scenes' track choice.

Tracks are generated from a prompt (optionally suggested by the small LLM from the adventure's
tone and a reference scene) or uploaded. Rendering runs as a background job (``AudioJobs``)
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

from backend.api.routes.adventures.editor_audio_tracks import (
    MAX_UPLOAD_BYTES,
    add_track_change,
    assign_scene_track,
    new_track_id_for,
    release_track,
    rename_track_references,
    renamed_track_id,
    replace_file,
    require_track,
    sniff_audio,
    taken_track_ids,
    template_scenes,
    update_tracks,
)
from backend.core.audio_settings import audio_api_key, normalize_audio_settings
from backend.core.auth import get_current_user
from backend.core.database import AsyncSessionLocal, get_db
from backend.core.global_settings import read_server_settings
from backend.core.llm_router import GameMasterLLM
from backend.engine.audio.audio_assets import save_library_audio
from backend.engine.audio.audio_jobs import AudioJobs
from backend.engine.audio.audio_library import (
    MAX_EDITABLE_ID_CHARS,
    MAX_NAME_CHARS,
    MAX_PROMPT_CHARS,
    normalize_tracks,
    now_iso,
)
from backend.engine.audio.audio_prompt_context import (
    AUDIO_PROMPT_SYSTEM_PROMPT,
    build_audio_prompt_request,
    ensure_loopable,
)
from backend.engine.audio.audio_providers import render_exclusive
from backend.engine.audio.audio_test_runs import check_provider_ready
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User

router = APIRouter(prefix="/{template_id}/audio", tags=["Editor"])

editor_jobs = AudioJobs(max_remembered=100)
# Replaced in tests; background jobs cannot use the request's session.
session_factory = AsyncSessionLocal

TRACK_PATH = Path(..., pattern=r"^[A-Za-z0-9_-]{1,50}$")


class SuggestPayload(BaseModel):
    reference_scene_id: Optional[str] = Field(default=None, max_length=50)


class TrackPayload(BaseModel):
    # Optional: suggested from the name when empty (e.g. CRYPT_THEME).
    id: Optional[str] = Field(default=None, max_length=MAX_EDITABLE_ID_CHARS)
    name: str = Field(default="", max_length=MAX_NAME_CHARS)
    prompt: str = Field(default="", max_length=MAX_PROMPT_CHARS)
    reference_scene_id: Optional[str] = Field(default=None, max_length=50)
    duration: Optional[int] = Field(default=None, ge=5, le=600)


class TrackUpdate(BaseModel):
    id: Optional[str] = Field(default=None, max_length=MAX_EDITABLE_ID_CHARS)
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
    await db.refresh(adventure, ["audio_tracks", "audio_enabled", "title_track_id"])
    settings = normalize_audio_settings((await read_server_settings(db)).audio_settings)
    usage: dict[str, list[str]] = {}
    for scene in await template_scenes(db, adventure.id):
        if scene.audio_track_id:
            usage.setdefault(scene.audio_track_id, []).append(scene.id)
    return {
        "tracks": normalize_tracks(adventure.audio_tracks, adventure.id),
        "scene_usage": usage,
        "jobs": _job_overview(adventure.id),
        "audio_enabled": bool(adventure.audio_enabled),
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
        url = save_library_audio(template_id, track_id, secrets.token_hex(4), data, extension)

        def store(tracks: list[dict[str, Any]]) -> None:
            track = require_track(tracks, track_id)
            replace_file(track, url, template_id)
            track["source"] = "generated"

        async with session_factory() as db:
            await update_tracks(db, template_id, store)
        return {"url": url, "bytes": len(data)}

    return editor_jobs.start(work, {"template_id": template_id, "track_id": track_id})


async def _render_settings(db: AsyncSession, user: User) -> tuple[dict, Optional[str]]:
    settings = normalize_audio_settings((await read_server_settings(db)).audio_settings)
    if not settings["enabled"]:
        raise HTTPException(status_code=400, detail="Audio generation is switched off (Admin).")
    api_key = audio_api_key(user, settings)
    try:
        check_provider_ready(settings, api_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return settings, api_key


@router.get("")
async def get_audio_library(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return await _library(db, await _owned_adventure(db, template_id, current_user))


@router.post("/suggest-prompt")
async def suggest_audio_prompt(
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
        system_prompt=AUDIO_PROMPT_SYSTEM_PROMPT,
        user_prompt=build_audio_prompt_request(
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
    adventure = await _owned_adventure(db, template_id, current_user)
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Enter a prompt first.")
    name = payload.name.strip() or prompt[:40]
    track_id = new_track_id_for(payload.id, name, taken_track_ids(adventure))
    settings, api_key = await _render_settings(db, current_user)
    track = {
        "id": track_id,
        "name": name,
        "prompt": prompt,
        "url": None,
        "source": "generated",
        "reference_scene_id": payload.reference_scene_id or None,
        "created_at": now_iso(),
    }
    await update_tracks(db, template_id, add_track_change(track, bool(payload.id), name))
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
    track = require_track(normalize_tracks(adventure.audio_tracks, template_id), track_id)
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
    track_id: str = Form(default="", max_length=MAX_EDITABLE_ID_CHARS),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Add an uploaded audio file (MP3, WAV, OGG/Opus, FLAC, M4A; max 50 MB) to the library."""
    adventure = await _owned_adventure(db, template_id, current_user)
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="The audio file is larger than 50 MB.")
    original = os.path.basename(file.filename or "upload")
    extension = sniff_audio(data, original)
    stem = os.path.splitext(original)[0]
    new_id = new_track_id_for(track_id, stem, taken_track_ids(adventure))
    url = save_library_audio(template_id, new_id, secrets.token_hex(4), data, extension)
    track = {
        "id": new_id,
        "name": name.strip() or stem[:MAX_NAME_CHARS] or new_id,
        "prompt": "",
        "url": url,
        "source": "uploaded",
        "reference_scene_id": None,
        "created_at": now_iso(),
    }
    await update_tracks(db, template_id, add_track_change(track, bool(track_id.strip()), stem))
    return {"track": track}


@router.patch("/tracks/{track_id}")
async def update_track(
    template_id: str,
    payload: TrackUpdate,
    track_id: str = TRACK_PATH,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    adventure = await _owned_adventure(db, template_id, current_user)
    changes = payload.model_dump(exclude_unset=True)
    new_id = renamed_track_id(
        editor_jobs, template_id, track_id, changes.pop("id", None), taken_track_ids(adventure)
    )

    def change(tracks: list[dict[str, Any]]) -> dict[str, Any]:
        track = require_track(tracks, track_id)
        for field, value in changes.items():
            track[field] = (value or "").strip() or (None if field != "name" else track["name"])
        if new_id and any(t["id"] == new_id for t in tracks):
            raise HTTPException(status_code=409, detail=f"The track ID '{new_id}' is already used.")
        if new_id:
            track["id"] = new_id
        return dict(track)

    track = await update_tracks(db, template_id, change)
    if new_id:
        await rename_track_references(db, adventure, track_id, new_id)
    return {"track": track}


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
async def get_audio_job(
    template_id: str,
    job_id: str = Path(..., pattern=r"^[a-f0-9]{16}$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    await _owned_adventure(db, template_id, current_user)
    meta = editor_jobs.meta(job_id)
    if not meta or meta["template_id"] != template_id:
        raise HTTPException(status_code=404, detail="Audio job not found (the server restarted?).")
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
    return {"scene_id": scene.id, "audio_track_id": scene.audio_track_id}


@router.post("/title")
async def set_title_track(
    template_id: str,
    payload: SceneTrackPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Choose the title track played on the library tile (``null`` = no title track)."""
    adventure = await _owned_adventure(db, template_id, current_user)
    if payload.track_id:
        require_track(normalize_tracks(adventure.audio_tracks, template_id), payload.track_id)
    adventure.title_track_id = payload.track_id or None
    await db.commit()
    return {"title_track_id": adventure.title_track_id}
