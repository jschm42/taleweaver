"""MCP tools for server-side visual generation, visual uploads, audio rendering, and thumbnails."""

from __future__ import annotations

import asyncio
import base64
import binascii
import secrets
import uuid
from typing import Any, Literal, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

import backend.api.routes.adventures.assets as visual_assets
import backend.core.database as core_database
from backend.api.routes.adventures import editor_audio
from backend.api.routes.adventures.editing import cutscene_routes
from backend.api.routes.adventures.editing.payload import _build_adventure_editor_assets
from backend.core.global_settings import apply_global_settings
from backend.engine.media.media_engine import MediaEngine
from backend.mcp.context import McpRequestContext
from backend.mcp.registry import ToolSpec, mcp_registry
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.user import User
from backend.services.inspection_service import resolve_adventure_template
from backend.utils.path_security import sanitize_path_component

_MAX_VISUAL_JOBS = 50
_VISUAL_JOBS: dict[str, dict[str, Any]] = {}
_VISUAL_TASKS: set[asyncio.Task[Any]] = set()

VisualTarget = Literal["cover", "protagonist", "scene", "npc", "object", "cutscene_slide"]
BatchVisualTarget = Literal["cover", "protagonist", "scene", "npc", "object"]


class GenerateVisualInput(BaseModel):
    adventure: str = Field(
        ..., min_length=1, description="Template ID, origin_id, or title substring."
    )
    target_type: VisualTarget
    target_id: Optional[str] = Field(
        default=None,
        description="Required for scene, npc, and object; optional for cover/protagonist.",
    )
    prompt: Optional[str] = Field(default=None, max_length=4000)
    image_style: str = Field(default="", max_length=200)
    use_advanced_model: bool = False
    apply_style: bool = True
    apply_appearance: bool = True
    use_tone: bool = False


class GenerateAdventureVisualsInput(BaseModel):
    adventure: str = Field(
        ..., min_length=1, description="Template ID, origin_id, or title substring."
    )
    targets: list[BatchVisualTarget] = Field(
        default_factory=lambda: ["cover", "protagonist", "scene", "npc", "object"]
    )
    only_missing: bool = Field(default=True, description="Skip targets that already have an image.")
    use_advanced_model: bool = False
    apply_style: bool = True
    apply_appearance: bool = True
    run_async: bool = Field(
        default=True, description="True starts a background job and returns job_id; False waits."
    )
    max_targets: int = Field(default=30, ge=1, le=100)


class VisualJobStatusInput(BaseModel):
    job_id: str = Field(..., min_length=1, max_length=32)


class UploadVisualInput(BaseModel):
    adventure: str = Field(
        ..., min_length=1, description="Template ID, origin_id, or title substring."
    )
    target_type: VisualTarget
    target_id: Optional[str] = Field(default=None, max_length=100)
    image_base64: str = Field(
        ..., min_length=4, description="Base64-encoded PNG, JPEG, or WEBP bytes."
    )
    mime_type: Literal["image/png", "image/jpeg", "image/webp"] = "image/png"


class RenderAudioInput(BaseModel):
    adventure: str = Field(
        ..., min_length=1, description="Template ID, origin_id, or title substring."
    )
    track_id: str = Field(..., min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]{1,50}$")
    duration: Optional[int] = Field(default=None, ge=5, le=600)


class AudioJobStatusInput(BaseModel):
    adventure: str = Field(
        ..., min_length=1, description="Template ID, origin_id, or title substring."
    )
    job_id: str = Field(..., min_length=16, max_length=16, pattern=r"^[a-f0-9]{16}$")


class RegenerateThumbnailsInput(BaseModel):
    adventure: Optional[str] = Field(
        default=None,
        description="Optional template identifier; omit to process all accessible templates.",
    )


async def _acting_owner(ctx: McpRequestContext, tpl: AdventureTemplate) -> User:
    if not tpl.owner_id or tpl.owner_id == ctx.user.id:
        return ctx.user
    owner = await ctx.db.get(User, tpl.owner_id)
    if owner is None:
        return ctx.user
    await apply_global_settings(ctx.db, owner)
    return owner


def _convert_http_error(exc: HTTPException) -> Exception:
    if exc.status_code == 404:
        return LookupError(str(exc.detail))
    return ValueError(str(exc.detail))


async def _resolve_visual_target_id(
    ctx: McpRequestContext, tpl: AdventureTemplate, target_type: str, target_id: Optional[str]
) -> str:
    clean = (target_id or "").strip()
    if target_type == "cover":
        return clean or tpl.id
    if target_type == "protagonist":
        if clean:
            return clean
        avatar = (
            (
                await ctx.db.execute(
                    select(Avatar)
                    .where(Avatar.template_id == tpl.id)
                    .order_by(Avatar.created_at.asc(), Avatar.id.asc())
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
        if avatar is None:
            raise LookupError("Protagonist avatar not found for this adventure.")
        return avatar.id
    if not clean:
        raise ValueError(f"target_id is required when target_type is '{target_type}'.")
    return clean


async def _tool_generate_visual(
    ctx: McpRequestContext, args: GenerateVisualInput
) -> dict[str, Any]:
    tpl = await resolve_adventure_template(ctx.db, args.adventure, owner_id=ctx.scoped_owner_id)
    owner = await _acting_owner(ctx, tpl)

    try:
        if args.target_type == "cutscene_slide":
            prompt = (args.prompt or "").strip()
            if not prompt:
                raise ValueError("prompt is required for target_type='cutscene_slide'.")
            req = cutscene_routes.SlideImageRequest(
                prompt=prompt,
                image_style=args.image_style,
                use_style=args.apply_style,
                use_tone=args.use_tone,
                quality="advanced" if args.use_advanced_model else "simple",
            )
            res = await cutscene_routes.generate_slide_image(
                tpl.id, req, db=ctx.db, current_user=owner
            )
            return {
                "template_id": tpl.id,
                "target_type": "cutscene_slide",
                "image_url": res["url"],
            }

        target_id = await _resolve_visual_target_id(ctx, tpl, args.target_type, args.target_id)
        vis_req = visual_assets.RegenerateVisualRequest(
            target_type=args.target_type,
            target_id=target_id,
            prompt=args.prompt,
            use_advanced_model=args.use_advanced_model,
            apply_style=args.apply_style,
            apply_appearance=args.apply_appearance,
        )
        res = await visual_assets.regenerate_visual(tpl.id, vis_req, db=ctx.db, current_user=owner)
    except HTTPException as exc:
        raise _convert_http_error(exc) from exc

    return {
        "template_id": tpl.id,
        "target_type": args.target_type,
        "target_id": target_id,
        "image_url": res.get("image_url"),
    }


def _collect_visual_jobs(
    assets: dict[str, Any], template_id: str, allowed: set[str], only_missing: bool
) -> list[tuple[BatchVisualTarget, str, str]]:
    jobs: list[tuple[BatchVisualTarget, str, str]] = []
    adv = assets.get("adventure") or {}
    if "cover" in allowed and not (
        only_missing and (adv.get("cover_image_url") or adv.get("image_url"))
    ):
        jobs.append(("cover", template_id, str(adv.get("title") or "Cover")))

    protag = assets.get("protagonist") or {}
    if (
        "protagonist" in allowed
        and protag.get("id")
        and not (only_missing and protag.get("profile_image"))
    ):
        jobs.append(("protagonist", str(protag["id"]), str(protag.get("name") or "Protagonist")))

    collections: tuple[tuple[BatchVisualTarget, str, str], ...] = (
        ("scene", "scenes", "label"),
        ("npc", "npcs", "name"),
        ("object", "objects", "name"),
    )
    for kind, key, label_key in collections:
        if kind not in allowed:
            continue
        for entry in assets.get(key) or []:
            eid = entry.get("id")
            if not eid or (only_missing and entry.get("image_url")):
                continue
            if kind == "object" and str(entry.get("item_type") or "").upper() == "CONSTRUCTABLE":
                continue
            jobs.append((kind, str(eid), str(entry.get(label_key) or eid)))
    return jobs


async def _run_visual_batch(
    db: Any,
    template_id: str,
    owner: User,
    jobs: list[tuple[BatchVisualTarget, str, str]],
    args: GenerateAdventureVisualsInput,
    job_state: dict[str, Any],
) -> None:
    for target_type, target_id, label in jobs:
        req = visual_assets.RegenerateVisualRequest(
            target_type=target_type,
            target_id=target_id,
            use_advanced_model=args.use_advanced_model,
            apply_style=args.apply_style,
            apply_appearance=args.apply_appearance,
        )
        try:
            res = await visual_assets.regenerate_visual(template_id, req, db=db, current_user=owner)
            job_state["completed"] += 1
            job_state["results"].append(
                {
                    "target_type": target_type,
                    "target_id": target_id,
                    "label": label,
                    "status": "ok",
                    "image_url": res.get("image_url"),
                }
            )
        except Exception as exc:
            detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
            job_state["failed"] += 1
            job_state["results"].append(
                {
                    "target_type": target_type,
                    "target_id": target_id,
                    "label": label,
                    "status": "failed",
                    "error": str(detail),
                }
            )
    job_state["status"] = "done"


def _remember_visual_job(job_state: dict[str, Any]) -> None:
    _VISUAL_JOBS[job_state["job_id"]] = job_state
    while len(_VISUAL_JOBS) > _MAX_VISUAL_JOBS:
        oldest = next(iter(_VISUAL_JOBS))
        _VISUAL_JOBS.pop(oldest, None)


async def _tool_generate_adventure_visuals(
    ctx: McpRequestContext, args: GenerateAdventureVisualsInput
) -> dict[str, Any]:
    tpl = await resolve_adventure_template(ctx.db, args.adventure, owner_id=ctx.scoped_owner_id)
    owner = await _acting_owner(ctx, tpl)
    assets = (await _build_adventure_editor_assets(tpl.id, ctx.db)).model_dump()
    jobs = _collect_visual_jobs(assets, tpl.id, set(args.targets), args.only_missing)[
        : args.max_targets
    ]
    job_id = secrets.token_hex(8)
    job_state: dict[str, Any] = {
        "job_id": job_id,
        "template_id": tpl.id,
        "owner_id": tpl.owner_id or ctx.user.id,
        "status": "running" if jobs else "done",
        "total": len(jobs),
        "completed": 0,
        "failed": 0,
        "results": [],
    }
    if not jobs:
        return {k: v for k, v in job_state.items() if k != "owner_id"}

    if not args.run_async:
        await _run_visual_batch(ctx.db, tpl.id, owner, jobs, args, job_state)
        return {k: v for k, v in job_state.items() if k != "owner_id"}

    _remember_visual_job(job_state)
    owner_id = owner.id

    async def worker() -> None:
        async with core_database.AsyncSessionLocal() as bg_db:
            bg_owner = await apply_global_settings(bg_db, await bg_db.get(User, owner_id))
            if bg_owner is None:
                job_state["status"] = "failed"
                return
            await _run_visual_batch(bg_db, tpl.id, bg_owner, jobs, args, job_state)

    task = asyncio.create_task(worker())
    _VISUAL_TASKS.add(task)
    task.add_done_callback(_VISUAL_TASKS.discard)
    return {
        "job_id": job_id,
        "template_id": tpl.id,
        "status": "running",
        "total": len(jobs),
    }


async def _tool_get_visual_job_status(
    ctx: McpRequestContext, args: VisualJobStatusInput
) -> dict[str, Any]:
    job = _VISUAL_JOBS.get(args.job_id)
    if job is None:
        raise LookupError(f"Visual batch job '{args.job_id}' not found.")
    if ctx.scoped_owner_id is not None and job.get("owner_id") != ctx.scoped_owner_id:
        raise LookupError(f"Visual batch job '{args.job_id}' not found.")
    return {k: v for k, v in job.items() if k != "owner_id"}


def _decode_image_b64(raw: str) -> bytes:
    payload = raw.strip()
    if "," in payload and payload.lower().startswith("data:"):
        payload = payload.split(",", 1)[1]
    try:
        return base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Invalid base64 image payload.") from exc


async def _tool_upload_visual(ctx: McpRequestContext, args: UploadVisualInput) -> dict[str, Any]:
    tpl = await resolve_adventure_template(ctx.db, args.adventure, owner_id=ctx.scoped_owner_id)
    content = _decode_image_b64(args.image_base64)
    val_type = "cutscene" if args.target_type == "cutscene_slide" else args.target_type

    try:
        visual_assets._validate_upload_content(content, args.mime_type, val_type)
        if args.target_type == "cutscene_slide":
            url = visual_assets._store_uploaded_visual(
                tpl.id, "cutscene", args.mime_type, f"slide_{uuid.uuid4().hex[:12]}", content
            )
            return {
                "status": "uploaded",
                "template_id": tpl.id,
                "target_type": "cutscene_slide",
                "image_url": url,
            }

        target_id = await _resolve_visual_target_id(ctx, tpl, args.target_type, args.target_id)
        if sanitize_path_component(target_id) != target_id:
            raise ValueError("Invalid target_id format.")
        target = await visual_assets._resolve_upload_target(
            ctx.db, tpl.id, args.target_type, target_id
        )
        url = visual_assets._store_uploaded_visual(
            tpl.id,
            args.target_type,
            args.mime_type,
            target.id if target is not None else None,
            content,
        )
    except HTTPException as exc:
        raise _convert_http_error(exc) from exc

    if target is None:
        tpl.image_url = url
    elif args.target_type == "protagonist":
        target.profile_image = url
    else:
        target.image_url = url
    await ctx.db.commit()
    return {
        "status": "uploaded",
        "template_id": tpl.id,
        "target_type": args.target_type,
        "target_id": target_id,
        "image_url": url,
    }


async def _tool_render_audio_track(
    ctx: McpRequestContext, args: RenderAudioInput
) -> dict[str, Any]:
    tpl = await resolve_adventure_template(ctx.db, args.adventure, owner_id=ctx.scoped_owner_id)
    owner = await _acting_owner(ctx, tpl)
    try:
        job = await editor_audio.render_track_again(
            tpl.id,
            editor_audio.RenderPayload(duration=args.duration),
            track_id=args.track_id,
            db=ctx.db,
            current_user=owner,
        )
    except HTTPException as exc:
        raise _convert_http_error(exc) from exc
    return {"template_id": tpl.id, "track_id": args.track_id, "job": job}


async def _tool_get_audio_job_status(
    ctx: McpRequestContext, args: AudioJobStatusInput
) -> dict[str, Any]:
    tpl = await resolve_adventure_template(ctx.db, args.adventure, owner_id=ctx.scoped_owner_id)
    owner = await _acting_owner(ctx, tpl)
    try:
        return await editor_audio.get_audio_job(tpl.id, args.job_id, db=ctx.db, current_user=owner)
    except HTTPException as exc:
        raise _convert_http_error(exc) from exc


async def _tool_regenerate_thumbnails(
    ctx: McpRequestContext, args: RegenerateThumbnailsInput
) -> dict[str, Any]:
    if args.adventure:
        tpl = await resolve_adventure_template(ctx.db, args.adventure, owner_id=ctx.scoped_owner_id)
        ids = [tpl.id]
    else:
        stmt = select(AdventureTemplate.id)
        if ctx.scoped_owner_id is not None:
            stmt = stmt.where(AdventureTemplate.owner_id == ctx.scoped_owner_id)
        ids = [tid for tid in (await ctx.db.execute(stmt)).scalars().all() if tid]
    for tid in ids:
        await MediaEngine.ensure_thumbnails(tid)
    return {"processed_count": len(ids), "template_ids": ids}


def register_media_tools() -> None:
    """Register all ``generate_media`` MCP tools."""
    mcp_registry.register_tool(
        ToolSpec(
            name="generate_visual",
            description="Generate or regenerate one visual (cover, protagonist, scene, npc, object, or cutscene_slide) via MediaEngine.",
            feature="generate_media",
            input_model=GenerateVisualInput,
            handler=_tool_generate_visual,
            read_only=False,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="generate_adventure_visuals",
            description="Batch-generate missing or selected visual assets for an adventure (async by default).",
            feature="generate_media",
            input_model=GenerateAdventureVisualsInput,
            handler=_tool_generate_adventure_visuals,
            read_only=False,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="get_visual_job_status",
            description="Poll the progress and results of a batch generate_adventure_visuals job.",
            feature="generate_media",
            input_model=VisualJobStatusInput,
            handler=_tool_get_visual_job_status,
            read_only=True,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="upload_visual",
            description="Upload a base64 PNG/JPEG/WEBP image for a cover, protagonist, scene, npc, object, or cutscene_slide.",
            feature="generate_media",
            input_model=UploadVisualInput,
            handler=_tool_upload_visual,
            read_only=False,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="render_audio_track",
            description="Render an audio library track using the configured audio provider (Google Lyria or ComfyUI).",
            feature="generate_media",
            input_model=RenderAudioInput,
            handler=_tool_render_audio_track,
            read_only=False,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="get_audio_job_status",
            description="Poll the status of a render_audio_track background job.",
            feature="generate_media",
            input_model=AudioJobStatusInput,
            handler=_tool_get_audio_job_status,
            read_only=True,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="regenerate_thumbnails",
            description="Generate missing web thumbnails for one adventure or all accessible adventures.",
            feature="generate_media",
            input_model=RegenerateThumbnailsInput,
            handler=_tool_regenerate_thumbnails,
            read_only=False,
        )
    )
