"""MCP tools for managing adventure cutscenes and audio track libraries."""

from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field

from backend.api.routes.adventures.editing.cutscene_routes import store_cutscenes
from backend.api.routes.adventures.editor_audio import editor_jobs
from backend.api.routes.adventures.editor_audio_tracks import (
    add_track_change,
    assign_scene_track,
    new_track_id_for,
    release_track,
    rename_track_references,
    renamed_track_id,
    replace_file,
    require_track,
    taken_track_ids,
    template_scenes,
    update_tracks,
)
from backend.engine.audio.audio_library import (
    MAX_EDITABLE_ID_CHARS,
    MAX_NAME_CHARS,
    MAX_PROMPT_CHARS,
    normalize_tracks,
    now_iso,
)
from backend.engine.cutscenes.library import cutscene_ref_or_none, normalize_cutscenes
from backend.mcp.context import McpRequestContext
from backend.mcp.registry import ToolSpec, mcp_registry
from backend.models.adventure_template import AdventureTemplate
from backend.services.inspection_service import resolve_adventure_template


class ManageCutscenesInput(BaseModel):
    adventure: str = Field(
        ..., min_length=1, description="Template ID, origin_id, or title substring."
    )
    action: Literal["get", "set"] = Field(default="get")
    cutscenes: Optional[list[dict[str, Any]]] = Field(
        default=None, description="Full normalized cutscene list when action='set'."
    )
    intro_cutscene_id: Optional[str] = Field(default=None, max_length=40)
    win_cutscene_id: Optional[str] = Field(default=None, max_length=40)
    game_over_cutscene_id: Optional[str] = Field(default=None, max_length=40)


class ManageAudioTracksInput(BaseModel):
    adventure: str = Field(
        ..., min_length=1, description="Template ID, origin_id, or title substring."
    )
    action: Literal["list", "create", "update", "delete", "assign_scene", "set_title"]
    track_id: Optional[str] = Field(default=None, max_length=MAX_EDITABLE_ID_CHARS)
    new_id: Optional[str] = Field(default=None, max_length=MAX_EDITABLE_ID_CHARS)
    name: Optional[str] = Field(default=None, max_length=MAX_NAME_CHARS)
    prompt: Optional[str] = Field(default=None, max_length=MAX_PROMPT_CHARS)
    reference_scene_id: Optional[str] = Field(default=None, max_length=50)
    scene_id: Optional[str] = Field(default=None, max_length=50)


async def _tool_manage_cutscenes(
    ctx: McpRequestContext, args: ManageCutscenesInput
) -> dict[str, Any]:
    adv = await resolve_adventure_template(ctx.db, args.adventure, owner_id=ctx.scoped_owner_id)
    if args.action == "get":
        return {
            "template_id": adv.id,
            "cutscenes": normalize_cutscenes(adv.cutscenes),
            "intro_cutscene_id": adv.intro_cutscene_id,
            "win_cutscene_id": adv.win_cutscene_id,
            "game_over_cutscene_id": adv.game_over_cutscene_id,
        }

    cutscenes = store_cutscenes(adv, args.cutscenes or [])
    adv.intro_cutscene_id = cutscene_ref_or_none(args.intro_cutscene_id, cutscenes)  # type: ignore[assignment]
    adv.win_cutscene_id = cutscene_ref_or_none(args.win_cutscene_id, cutscenes)  # type: ignore[assignment]
    adv.game_over_cutscene_id = cutscene_ref_or_none(args.game_over_cutscene_id, cutscenes)  # type: ignore[assignment]
    await ctx.db.commit()
    return {
        "template_id": adv.id,
        "cutscenes": cutscenes,
        "intro_cutscene_id": adv.intro_cutscene_id,
        "win_cutscene_id": adv.win_cutscene_id,
        "game_over_cutscene_id": adv.game_over_cutscene_id,
    }


async def _audio_list(
    ctx: McpRequestContext, adv: AdventureTemplate, _args: ManageAudioTracksInput
) -> dict[str, Any]:
    usage: dict[str, list[str]] = {}
    for scene in await template_scenes(ctx.db, adv.id):
        if scene.audio_track_id:
            usage.setdefault(scene.audio_track_id, []).append(scene.id)
    return {
        "template_id": adv.id,
        "tracks": normalize_tracks(adv.audio_tracks, adv.id),
        "title_track_id": adv.title_track_id,
        "audio_enabled": bool(adv.audio_enabled),
        "scene_usage": usage,
    }


async def _audio_create(
    ctx: McpRequestContext, adv: AdventureTemplate, args: ManageAudioTracksInput
) -> dict[str, Any]:
    prompt = (args.prompt or "").strip()
    name = (args.name or "").strip() or prompt[:40]
    if not name:
        raise ValueError("Provide a track name or prompt when creating an audio track.")
    track_id = new_track_id_for(args.track_id, name, taken_track_ids(adv))
    track = {
        "id": track_id,
        "name": name,
        "prompt": prompt,
        "url": None,
        "source": "planned",
        "reference_scene_id": args.reference_scene_id or None,
        "created_at": now_iso(),
    }
    await update_tracks(ctx.db, adv.id, add_track_change(track, bool(args.track_id), name))
    return {"template_id": adv.id, "track": track}


async def _audio_update(
    ctx: McpRequestContext, adv: AdventureTemplate, args: ManageAudioTracksInput
) -> dict[str, Any]:
    track_id = (args.track_id or "").strip()
    if not track_id:
        raise ValueError("track_id is required for action='update'.")
    new_id = renamed_track_id(editor_jobs, adv.id, track_id, args.new_id, taken_track_ids(adv))

    def change(tracks: list[dict[str, Any]]) -> dict[str, Any]:
        track = require_track(tracks, track_id)
        if args.name is not None:
            track["name"] = args.name.strip() or track["name"]
        if args.prompt is not None:
            track["prompt"] = args.prompt.strip()
        if args.reference_scene_id is not None:
            track["reference_scene_id"] = args.reference_scene_id.strip() or None
        if new_id and any(t["id"] == new_id for t in tracks):
            raise ValueError(f"Track ID '{new_id}' is already used.")
        if new_id:
            track["id"] = new_id
        return dict(track)

    updated = await update_tracks(ctx.db, adv.id, change)
    if new_id:
        await rename_track_references(ctx.db, adv, track_id, new_id)
    return {"template_id": adv.id, "track": updated}


async def _audio_delete(
    ctx: McpRequestContext, adv: AdventureTemplate, args: ManageAudioTracksInput
) -> dict[str, Any]:
    track_id = (args.track_id or "").strip()
    if not track_id:
        raise ValueError("track_id is required for action='delete'.")

    def change(tracks: list[dict[str, Any]]) -> None:
        track = require_track(tracks, track_id)
        replace_file(track, "", adv.id)
        tracks.remove(track)

    await update_tracks(ctx.db, adv.id, change)
    await release_track(ctx.db, adv, track_id)
    if adv.title_track_id == track_id:
        adv.title_track_id = None  # type: ignore[assignment]
        await ctx.db.commit()
    return {"template_id": adv.id, "deleted_track_id": track_id}


async def _audio_assign_scene(
    ctx: McpRequestContext, adv: AdventureTemplate, args: ManageAudioTracksInput
) -> dict[str, Any]:
    scene_id = (args.scene_id or "").strip()
    if not scene_id:
        raise ValueError("scene_id is required for action='assign_scene'.")
    scene = await assign_scene_track(ctx.db, adv, scene_id, args.track_id or None)
    return {"template_id": adv.id, "scene_id": scene.id, "audio_track_id": scene.audio_track_id}


async def _audio_set_title(
    ctx: McpRequestContext, adv: AdventureTemplate, args: ManageAudioTracksInput
) -> dict[str, Any]:
    if args.track_id:
        require_track(normalize_tracks(adv.audio_tracks, adv.id), args.track_id)
    adv.title_track_id = args.track_id or None  # type: ignore[assignment]
    await ctx.db.commit()
    return {"template_id": adv.id, "title_track_id": adv.title_track_id}


_AUDIO_HANDLERS = {
    "list": _audio_list,
    "create": _audio_create,
    "update": _audio_update,
    "delete": _audio_delete,
    "assign_scene": _audio_assign_scene,
    "set_title": _audio_set_title,
}


async def _tool_manage_audio_tracks(
    ctx: McpRequestContext, args: ManageAudioTracksInput
) -> dict[str, Any]:
    adv = await resolve_adventure_template(ctx.db, args.adventure, owner_id=ctx.scoped_owner_id)
    handler = _AUDIO_HANDLERS[args.action]
    try:
        return await handler(ctx, adv, args)
    except HTTPException as exc:
        if exc.status_code == 404:
            raise LookupError(str(exc.detail)) from exc
        raise ValueError(str(exc.detail)) from exc


def register_editor_media_tools() -> None:
    """Register cutscene and audio-library authoring tools."""
    mcp_registry.register_tool(
        ToolSpec(
            name="manage_cutscenes",
            description="Read or replace an adventure's cutscenes and intro/win/game-over cutscene IDs.",
            feature="edit_adventures",
            input_model=ManageCutscenesInput,
            handler=_tool_manage_cutscenes,
            read_only=False,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="manage_audio_tracks",
            description="List, create, update, delete, or assign planned audio tracks (including Suno/Stable Audio prompts).",
            feature="edit_adventures",
            input_model=ManageAudioTracksInput,
            handler=_tool_manage_audio_tracks,
            read_only=False,
        )
    )
