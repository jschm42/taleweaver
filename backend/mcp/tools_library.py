"""MCP tools for browsing the adventure library, templates, manifests, and change-set schemas."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.api.routes.adventures.editing.change_set import OPERATION_MODELS, OPERATIONS
from backend.mcp.context import McpRequestContext
from backend.mcp.registry import ToolSpec, mcp_registry
from backend.models.adventure_template import AdventureTemplate
from backend.services.adventure_library import (
    LibraryError,
    LibraryService,
    is_newer_version,
    is_version_at_least,
)
from backend.services.inspection_service import (
    export_adventure_manifest,
    get_adventure_details,
    get_adventure_summary,
    list_adventures,
    list_disk_adventures,
    resolve_adventure_template,
)

_library_service = LibraryService()

_OP_FIELDS_FALLBACK = {
    "set_init_script": ["code"],
    "append_init_script": ["code"],
    "delete_scene": ["scene_id"],
    "delete_exit": ["exit_id"],
    "delete_entity": ["entity_id"],
    "delete_script": ["script_id"],
    "delete_quest": ["quest_id"],
    "delete_award": ["award_key"],
}


class ListAdventuresInput(BaseModel):
    limit: int = Field(
        default=100, ge=1, le=500, description="Maximum number of templates to return."
    )


class ListLibraryCatalogInput(BaseModel):
    include_online: bool = Field(
        default=True, description="Include entries from the online adventure catalog."
    )
    include_disk: bool = Field(default=True, description="Include .adv/.adz files found on disk.")
    force_refresh: bool = Field(default=False, description="Bypass cached online library index.")


class AdventureIdentifierInput(BaseModel):
    adventure: str = Field(
        ..., min_length=1, description="Template ID, origin_id, or unique title substring."
    )


class AdventureDetailsInput(BaseModel):
    adventure: str = Field(
        ..., min_length=1, description="Template ID, origin_id, or unique title substring."
    )
    scene_id: Optional[str] = Field(
        default=None, description="Optional scene ID to return a focused scene slice."
    )
    section: Optional[str] = Field(
        default=None,
        description="Optional section: adventure, protagonist, scenes, npcs, objects, exits, quests, awards, scripts, cutscenes, audio_tracks, sections.",
    )
    compact: bool = Field(
        default=True, description="Omit empty fields and internal bookkeeping keys."
    )


class ListChangeSetOpsInput(BaseModel):
    op: Optional[str] = Field(
        default=None, description="Optional operation name to inspect in detail."
    )


async def _tool_list_adventures(
    ctx: McpRequestContext, args: ListAdventuresInput
) -> dict[str, Any]:
    items = await list_adventures(ctx.db, owner_id=ctx.scoped_owner_id, limit=args.limit)
    return {"count": len(items), "adventures": items}


async def _installed_versions(
    ctx: McpRequestContext, origin_ids: list[str]
) -> dict[str, str | None]:
    if not origin_ids:
        return {}
    stmt = select(AdventureTemplate.origin_id, AdventureTemplate.version).where(
        AdventureTemplate.origin_id.in_(origin_ids)
    )
    if ctx.scoped_owner_id is not None:
        stmt = stmt.where(AdventureTemplate.owner_id == ctx.scoped_owner_id)
    installed: dict[str, str | None] = {}
    for origin_id, version in (await ctx.db.execute(stmt)).all():
        current = installed.get(origin_id)
        if current is None or is_version_at_least(version or "", current):
            installed[origin_id] = version
    return installed


async def _tool_list_library_catalog(
    ctx: McpRequestContext, args: ListLibraryCatalogInput
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if args.include_disk:
        result["disk_adventures"] = await list_disk_adventures(ctx.db, owner_id=ctx.scoped_owner_id)
    if args.include_online:
        try:
            library = await _library_service.get_library(force_refresh=args.force_refresh)
            installed = await _installed_versions(ctx, [e.id for e in library.adventures])
            entries = [
                {
                    "id": entry.id,
                    "title": entry.title,
                    "version": entry.version,
                    "language": entry.language,
                    "teaser": entry.teaser,
                    "installed_version": installed.get(entry.id),
                    "update_available": is_newer_version(entry.version, installed.get(entry.id)),
                }
                for entry in sorted(library.adventures, key=lambda e: e.title.casefold())
            ]
            result["online_catalog"] = entries
        except LibraryError as exc:
            result["online_catalog"] = []
            result["online_error"] = str(exc)
    return result


async def _tool_get_adventure_summary(
    ctx: McpRequestContext, args: AdventureIdentifierInput
) -> dict[str, Any]:
    template = await resolve_adventure_template(
        ctx.db, args.adventure, owner_id=ctx.scoped_owner_id
    )
    return await get_adventure_summary(ctx.db, template.id)


async def _tool_get_adventure_details(
    ctx: McpRequestContext, args: AdventureDetailsInput
) -> dict[str, Any]:
    template = await resolve_adventure_template(
        ctx.db, args.adventure, owner_id=ctx.scoped_owner_id
    )
    return await get_adventure_details(
        ctx.db,
        template.id,
        scene_id=args.scene_id,
        section=args.section,
        compact=args.compact,
    )


async def _tool_export_manifest(
    ctx: McpRequestContext, args: AdventureIdentifierInput
) -> dict[str, Any]:
    template = await resolve_adventure_template(
        ctx.db, args.adventure, owner_id=ctx.scoped_owner_id
    )
    return await export_adventure_manifest(ctx.db, template.id)


async def _tool_list_change_set_ops(
    _ctx: McpRequestContext, args: ListChangeSetOpsInput
) -> dict[str, Any]:
    names = [args.op.strip()] if args.op else sorted(OPERATIONS)
    operations: dict[str, Any] = {}
    for name in names:
        if name not in OPERATIONS:
            raise ValueError(f"Unknown change-set operation '{name}'.")
        model = OPERATION_MODELS.get(name)
        if model is not None:
            operations[name] = {
                "fields": sorted(model.model_fields),
                "schema": model.model_json_schema() if args.op else None,
            }
        else:
            operations[name] = {"fields": _OP_FIELDS_FALLBACK.get(name, [])}
    return {"operations": operations}


def register_library_tools() -> None:
    """Register all ``read_adventures`` MCP tools."""
    mcp_registry.register_tool(
        ToolSpec(
            name="list_adventures",
            description="List adventure templates stored in the TaleWeaver database.",
            feature="read_adventures",
            input_model=ListAdventuresInput,
            handler=_tool_list_adventures,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="list_library_catalog",
            description="Browse online TaleWeaver library adventures and local .adv/.adz files on disk.",
            feature="read_adventures",
            input_model=ListLibraryCatalogInput,
            handler=_tool_list_library_catalog,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="get_adventure_summary",
            description="Get a compact ID index of an adventure's scenes, exits, NPCs, objects, scripts, quests, and regions.",
            feature="read_adventures",
            input_model=AdventureIdentifierInput,
            handler=_tool_get_adventure_summary,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="get_adventure_details",
            description="Inspect full editor data, a specific section, or a single scene slice with neighboring routes and entities.",
            feature="read_adventures",
            input_model=AdventureDetailsInput,
            handler=_tool_get_adventure_details,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="export_adventure_manifest",
            description="Export an adventure template as a complete TaleWeaver .adv JSON manifest.",
            feature="read_adventures",
            input_model=AdventureIdentifierInput,
            handler=_tool_export_manifest,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="list_change_set_operations",
            description="Inspect allowed operations and field schemas for transactional adventure change sets.",
            feature="read_adventures",
            input_model=ListChangeSetOpsInput,
            handler=_tool_list_change_set_ops,
        )
    )
