"""Editor music: scene loops and the adventure's main theme (prompt, AI suggestion, render).

Rendering runs as a background job (``MusicJobs``) the editor polls, because a render can take
minutes. When it finishes, the job writes the file into the adventure library and stores its
URL on the scene or template row with its own DB session, so closing the dialog does not lose
the track.
"""

from __future__ import annotations

import secrets
from copy import deepcopy
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.core.auth import get_current_user
from backend.core.database import AsyncSessionLocal, get_db
from backend.core.global_settings import read_server_settings
from backend.core.llm_router import GameMasterLLM
from backend.core.music_settings import music_api_key, normalize_music_settings
from backend.engine.audio.music_assets import delete_library_music, save_library_music
from backend.engine.audio.music_jobs import MusicJobs
from backend.engine.audio.music_prompt_context import (
    MAX_MUSIC_PROMPT_CHARS,
    MUSIC_PROMPT_SYSTEM_PROMPT,
    build_music_prompt_request,
    ensure_loopable,
)
from backend.engine.audio.music_providers import render_exclusive
from backend.engine.audio.music_test_runs import check_provider_ready
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldScene

router = APIRouter(prefix="/{template_id}/music", tags=["Editor"])

editor_jobs = MusicJobs(max_remembered=50)
# Replaced in tests; background jobs cannot use the request's session.
session_factory = AsyncSessionLocal

TargetType = Literal["scene", "theme"]


class MusicTarget(BaseModel):
    target_type: TargetType
    target_id: Optional[str] = Field(default=None, max_length=50)


class MusicPromptPayload(MusicTarget):
    prompt: str = Field(default="", max_length=MAX_MUSIC_PROMPT_CHARS)


class MusicGeneratePayload(MusicPromptPayload):
    duration: Optional[int] = Field(default=None, ge=5, le=600)


async def _owned_adventure(db: AsyncSession, template_id: str, user: User) -> AdventureTemplate:
    adventure = await db.get(AdventureTemplate, template_id)
    if not adventure or adventure.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Adventure template not found")
    return adventure


async def _target_row(db: AsyncSession, template_id: str, target: MusicTarget) -> Any:
    if target.target_type == "theme":
        return await db.get(AdventureTemplate, template_id)
    scene = (
        await db.execute(
            select(WorldScene).where(
                WorldScene.template_id == template_id,
                WorldScene.session_id.is_(None),
                WorldScene.id == target.target_id,
            )
        )
    ).scalar_one_or_none()
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene not found")
    return scene


def _music_fields(row: Any) -> dict[str, Any]:
    return {"music_prompt": row.music_prompt, "music_url": row.music_url}


async def _mirror_to_manifest(
    db: AsyncSession, template_id: str, target: MusicTarget, row: Any
) -> None:
    """Keep ``original_manifest`` in step, so a template reset does not drop the music."""
    adventure = (
        row if target.target_type == "theme" else await db.get(AdventureTemplate, template_id)
    )
    if adventure is None or not isinstance(adventure.original_manifest, dict):
        return
    manifest = deepcopy(adventure.original_manifest)
    if target.target_type == "theme":
        entry = manifest
    else:
        scenes = manifest.get("scenes") if isinstance(manifest.get("scenes"), list) else []
        entry = next((s for s in scenes if isinstance(s, dict) and s.get("id") == row.id), None)
    if entry is None:
        return
    entry.update(_music_fields(row))
    adventure.original_manifest = manifest
    flag_modified(adventure, "original_manifest")


async def _store_track(template_id: str, target: MusicTarget, prompt: str, url: str) -> None:
    async with session_factory() as db:
        row = await _target_row(db, template_id, target)
        old = row.music_url
        row.music_url = url
        row.music_prompt = prompt
        await _mirror_to_manifest(db, template_id, target, row)
        await db.commit()
    if old and old != url:
        delete_library_music(old, template_id)


@router.post("/suggest-prompt")
async def suggest_music_prompt(
    template_id: str,
    payload: MusicTarget,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """AI music prompt from the adventure's tone and the scene (or premise), always loopable."""
    adventure = await _owned_adventure(db, template_id, current_user)
    if payload.target_type == "scene":
        scene = await _target_row(db, template_id, payload)
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


@router.post("/prompt")
async def save_music_prompt(
    template_id: str,
    payload: MusicPromptPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    await _owned_adventure(db, template_id, current_user)
    row = await _target_row(db, template_id, payload)
    row.music_prompt = payload.prompt.strip() or None
    await _mirror_to_manifest(db, template_id, payload, row)
    await db.commit()
    return _music_fields(row)


@router.post("/generate")
async def generate_music(
    template_id: str,
    payload: MusicGeneratePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Start rendering the loop; poll ``GET /jobs/{id}``. The track is stored when done."""
    await _owned_adventure(db, template_id, current_user)
    await _target_row(db, template_id, payload)
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Enter a music prompt first.")
    settings = normalize_music_settings((await read_server_settings(db)).music_settings)
    if not settings["enabled"]:
        raise HTTPException(status_code=400, detail="Music generation is switched off (Admin).")
    api_key = music_api_key(current_user, settings)
    try:
        check_provider_ready(settings, api_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    target = MusicTarget(target_type=payload.target_type, target_id=payload.target_id)
    track = {"prompt": prompt, "duration": payload.duration}
    stem = payload.target_id if payload.target_type == "scene" else "theme"

    async def work() -> dict[str, Any]:
        data, extension = await render_exclusive(track, settings, api_key)
        url = save_library_music(template_id, str(stem), secrets.token_hex(4), data, extension)
        await _store_track(template_id, target, prompt, url)
        return {"url": url, "bytes": len(data)}

    meta = {"owner_id": current_user.id, "template_id": template_id}
    return editor_jobs.start(work, meta)


@router.get("/jobs/{job_id}")
async def get_music_job(
    template_id: str,
    job_id: str = Path(..., pattern=r"^[a-f0-9]{16}$"),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    meta = editor_jobs.meta(job_id)
    if not meta or meta["owner_id"] != current_user.id or meta["template_id"] != template_id:
        raise HTTPException(status_code=404, detail="Music job not found (the server restarted?).")
    return editor_jobs.status(job_id) or {}


@router.post("/remove")
async def remove_music(
    template_id: str,
    payload: MusicTarget,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Delete the rendered track (the prompt stays)."""
    await _owned_adventure(db, template_id, current_user)
    row = await _target_row(db, template_id, payload)
    old = row.music_url
    row.music_url = None
    await _mirror_to_manifest(db, template_id, payload, row)
    await db.commit()
    delete_library_music(old, template_id)
    return _music_fields(row)
