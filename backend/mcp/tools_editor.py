"""MCP tools for blueprint validation, transactional change sets, manifest import, and deletion."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

import backend.core.database as core_database
from backend.api.routes.adventures.editing.change_set import (
    MAX_OPERATIONS,
    ChangeSetError,
    DeferredCommitSession,
    apply_change_set,
    structural_findings,
)
from backend.api.routes.adventures.editing.validation import execute_validation_run
from backend.api.routes.adventures.logic import AdventureLogic
from backend.core.config import PROJECT_ROOT
from backend.engine.adventures.adventure_importer import (
    AdventureConflictError,
    AdventureTemplateImporter,
)
from backend.engine.blueprint import analyze_blueprint, has_blueprint_tags
from backend.mcp.context import McpRequestContext
from backend.mcp.registry import ToolSpec, mcp_registry
from backend.models.adventure_template import AdventureTemplate
from backend.services.adventure_library import (
    AdventureInstallError,
    LibraryError,
    LibraryService,
    install_entry,
)
from backend.services.inspection_service import resolve_adventure_template

_MAX_BLUEPRINT_CHARS = 100_000


class BlueprintValidateInput(BaseModel):
    text: str = Field(..., min_length=1, max_length=_MAX_BLUEPRINT_CHARS)


class ValidateAdventureInput(BaseModel):
    adventure: str = Field(
        ..., min_length=1, description="Template ID, origin_id, or title substring."
    )
    include_ai: bool = Field(
        default=False,
        description="Run AI logic validation in addition to structural checks (requires generate_adventures).",
    )


class ApplyChangesInput(BaseModel):
    adventure: str = Field(
        ..., min_length=1, description="Template ID, origin_id, or title substring."
    )
    operations: list[dict[str, Any]] = Field(
        ...,
        min_length=1,
        max_length=MAX_OPERATIONS,
        description="Ordered list of editor operations.",
    )
    commit: bool = Field(
        default=False,
        description="False (default) runs a dry run and rolls back; True persists changes.",
    )
    allow_errors: bool = Field(
        default=False,
        description="Commit even when the change set introduces new error-level validation findings.",
    )


class ImportAdventureInput(BaseModel):
    manifest: Optional[dict[str, Any]] = Field(
        default=None, description="Complete TaleWeaver .adv JSON manifest object."
    )
    library_id: Optional[str] = Field(
        default=None, min_length=1, max_length=200, description="Online adventure library entry ID."
    )
    overwrite: bool = Field(
        default=False, description="Overwrite an existing template with the same title/origin."
    )
    validate_after: bool = Field(
        default=True, description="Run structural validation after import."
    )


class DeleteAdventureInput(BaseModel):
    adventure: str = Field(
        ..., min_length=1, description="Template ID, origin_id, or title substring."
    )
    confirm_title: str = Field(
        ..., min_length=1, description="Exact title of the adventure to confirm permanent deletion."
    )


def _reject_file_refs(value: Any) -> None:
    if isinstance(value, dict):
        if "$file" in value:
            raise ValueError(
                "'$file' disk references are not allowed over MCP; pass script code inline."
            )
        for child in value.values():
            _reject_file_refs(child)
        return
    if isinstance(value, list):
        for item in value:
            _reject_file_refs(item)


async def _tool_validate_blueprint(
    _ctx: McpRequestContext, args: BlueprintValidateInput
) -> dict[str, Any]:
    if not has_blueprint_tags(args.text):
        return {"has_tags": False, "errors": [], "warnings": [], "counts": {}}
    blueprint, _missing = analyze_blueprint(args.text)
    counts: dict[str, int] = {}
    for block in blueprint.blocks:
        counts[block.kind] = counts.get(block.kind, 0) + 1
    return {
        "has_tags": True,
        "errors": [issue.as_dict() for issue in blueprint.errors],
        "warnings": [issue.as_dict() for issue in blueprint.warnings],
        "counts": counts,
    }


async def _tool_validate_adventure(
    ctx: McpRequestContext, args: ValidateAdventureInput
) -> dict[str, Any]:
    if args.include_ai:
        ctx.require_feature("generate_adventures")
    tpl = await resolve_adventure_template(ctx.db, args.adventure, owner_id=ctx.scoped_owner_id)
    try:
        run = await execute_validation_run(ctx.db, tpl.id, ctx.user, args.include_ai)
    except HTTPException as exc:
        raise ValueError(str(exc.detail)) from exc
    all_findings = run.structural_findings + run.ai_findings
    return {
        "template_id": tpl.id,
        "title": tpl.title,
        "structural_findings": [f.model_dump() for f in run.structural_findings],
        "ai_findings": [f.model_dump() for f in run.ai_findings],
        "ai_skipped_reason": run.ai_skipped_reason,
        "error_count": sum(1 for f in all_findings if f.severity == "error"),
        "warning_count": sum(1 for f in all_findings if f.severity == "warn"),
    }


async def _tool_apply_changes(ctx: McpRequestContext, args: ApplyChangesInput) -> dict[str, Any]:
    _reject_file_refs(args.operations)
    tpl = await resolve_adventure_template(ctx.db, args.adventure, owner_id=ctx.scoped_owner_id)
    template_id = tpl.id
    title = tpl.title

    tx_factory = async_sessionmaker(
        bind=core_database.AsyncSessionLocal.kw["bind"],
        class_=DeferredCommitSession,
        expire_on_commit=False,
    )
    committed = False
    blocked_by_errors = False
    async with tx_factory() as tx_db:
        try:
            result = await apply_change_set(
                tx_db, template_id, args.operations, base_dir=PROJECT_ROOT
            )
        except ChangeSetError as exc:
            await tx_db.rollback()
            raise ValueError(str(exc)) from exc

        if not args.commit:
            await tx_db.rollback()
        elif result.new_errors and not args.allow_errors:
            await tx_db.rollback()
            blocked_by_errors = True
        else:
            await tx_db.commit_for_real()
            committed = True

    return {
        "template_id": template_id,
        "title": title,
        "dry_run": not args.commit,
        "committed": committed,
        "blocked_by_errors": blocked_by_errors,
        "applied": result.applied,
        "refs": result.refs,
        "new_error_count": len(result.new_errors),
        "new_findings": [f.model_dump() for f in result.new_findings],
    }


async def _import_from_manifest(
    ctx: McpRequestContext, manifest: dict[str, Any], overwrite: bool
) -> AdventureTemplate:
    payload = dict(manifest)
    payload.setdefault("format", "TaleWeaver")
    adv_block = payload.get("adventure") if isinstance(payload.get("adventure"), dict) else {}
    if not payload.get("title") and adv_block.get("title"):
        payload["title"] = adv_block["title"]
    try:
        ok = await AdventureTemplateImporter.import_adv_manifest(
            ctx.db, payload, owner_id=ctx.user.id, overwrite=overwrite
        )
    except AdventureConflictError as exc:
        raise ValueError(
            f"Adventure '{exc.title}' already exists (template_id={exc.template_id}, "
            f"existing_version={exc.existing_version}). Set overwrite=true to replace."
        ) from exc
    if not ok:
        raise ValueError("Import failed or manifest is invalid.")

    title = str(payload.get("title") or "").strip()
    stmt = (
        select(AdventureTemplate)
        .where(AdventureTemplate.owner_id == ctx.user.id)
        .order_by(AdventureTemplate.created_at.desc())
        .limit(1)
    )
    if title:
        stmt = stmt.where(AdventureTemplate.title == title)
    tpl = (await ctx.db.execute(stmt)).scalars().first()
    if tpl is None:
        raise LookupError("Adventure imported, but template record could not be located.")
    return tpl


async def _import_from_library(ctx: McpRequestContext, library_id: str) -> AdventureTemplate:
    service = LibraryService()
    try:
        library = await service.get_library()
        entry = service.resolve_entry(library, library_id.strip())
        if entry is None:
            raise LookupError(f"Unknown library entry '{library_id}'.")
        installed = await install_entry(ctx.db, entry, ctx.user.id)
    except (LibraryError, AdventureInstallError) as exc:
        raise ValueError(str(exc)) from exc
    except AdventureConflictError as exc:
        raise ValueError(
            f"Adventure '{exc.title}' already exists (template_id={exc.template_id})."
        ) from exc
    if isinstance(installed, AdventureTemplate):
        return installed
    tpl = await ctx.db.get(AdventureTemplate, str(installed))
    if tpl is None:
        raise LookupError("Installed adventure template not found.")
    return tpl


async def _tool_import_adventure(
    ctx: McpRequestContext, args: ImportAdventureInput
) -> dict[str, Any]:
    if (args.manifest is None) == (args.library_id is None):
        raise ValueError("Provide exactly one of 'manifest' or 'library_id'.")

    tpl = (
        await _import_from_manifest(ctx, args.manifest, args.overwrite)
        if args.manifest is not None
        else await _import_from_library(ctx, args.library_id or "")
    )
    findings = (
        [f.model_dump() for f in await structural_findings(ctx.db, tpl.id)]
        if args.validate_after
        else []
    )
    return {
        "template_id": tpl.id,
        "title": tpl.title,
        "origin_id": tpl.origin_id,
        "validation_error_count": sum(1 for f in findings if f.get("severity") == "error"),
        "validation_findings": findings,
    }


async def _tool_delete_adventure(
    ctx: McpRequestContext, args: DeleteAdventureInput
) -> dict[str, Any]:
    tpl = await resolve_adventure_template(ctx.db, args.adventure, owner_id=ctx.scoped_owner_id)
    if args.confirm_title.strip().casefold() != (tpl.title or "").strip().casefold():
        raise ValueError(
            f"confirm_title does not match adventure title '{tpl.title}'; deletion aborted."
        )
    await AdventureLogic.delete_adventure(ctx.db, tpl.id)
    return {"status": "deleted", "template_id": tpl.id, "title": tpl.title}


def register_editor_tools() -> None:
    """Register blueprint, validation, change-set, import, and delete tools."""
    mcp_registry.register_tool(
        ToolSpec(
            name="validate_blueprint",
            description="Validate a tagged Story Idea / Markdown blueprint before generation.",
            feature="edit_adventures",
            input_model=BlueprintValidateInput,
            handler=_tool_validate_blueprint,
            read_only=True,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="validate_adventure",
            description="Run structural (and optional AI) validation on an existing adventure template.",
            feature="edit_adventures",
            input_model=ValidateAdventureInput,
            handler=_tool_validate_adventure,
            read_only=True,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="apply_adventure_changes",
            description=(
                "Apply a transactional change set to an adventure template. "
                "Defaults to commit=false (dry run) and blocks commits that introduce errors unless allow_errors=true."
            ),
            feature="edit_adventures",
            input_model=ApplyChangesInput,
            handler=_tool_apply_changes,
            read_only=False,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="import_adventure_manifest",
            description="Import a complete .adv manifest JSON or install an entry from the online library.",
            feature="edit_adventures",
            input_model=ImportAdventureInput,
            handler=_tool_import_adventure,
            read_only=False,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="delete_adventure",
            description="Permanently delete an adventure template and all its scenes, entities, and maps.",
            feature="edit_adventures",
            input_model=DeleteAdventureInput,
            handler=_tool_delete_adventure,
            read_only=False,
            destructive=True,
            requires_destructive_flag=True,
        )
    )
