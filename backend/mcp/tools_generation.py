"""MCP tools for Story Idea suggestions, World-Builder generation, Region Builder, and AI fixes."""

from __future__ import annotations

import asyncio
from typing import Any, Literal, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field

import backend.api.routes.adventures.editing.validation as editing_validation
import backend.api.routes.adventures.templates as template_routes
from backend.api.routes.adventures import adventure_creation
from backend.api.routes.adventures.editing import ai_fix_suggest, section_generation
from backend.api.routes.adventures.editing.section_builder_models import SectionGenerateRequest
from backend.api.routes.adventures.schemas import (
    CreateAdventureTemplatePayload,
    StoryIdeaSuggestionRequest,
)
from backend.core.global_settings import apply_global_settings
from backend.engine.world.sections import normalize_sections
from backend.mcp.context import McpRequestContext
from backend.mcp.registry import ToolSpec, mcp_registry
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.schemas.validation import AIFixSuggestionsRequest, Severity
from backend.services.inspection_service import resolve_adventure_template

_GEN_TASKS: set[asyncio.Task[Any]] = set()


class SuggestStoryIdeaInput(BaseModel):
    title: str = Field(default="", max_length=100)
    story_idea: str = Field(default="", max_length=20_000)
    selected_tone: Optional[dict[str, Any]] = None
    rule_enforcement_mode: Literal["rpg", "story", "chat"] = "rpg"
    language: Optional[str] = Field(default=None, max_length=30)


class GenerateAdventureInput(BaseModel):
    title: str = Field(..., min_length=1, max_length=50)
    original_prompt: str = Field(..., min_length=1, max_length=50_000)
    language: Optional[str] = Field(default=None, max_length=30)
    rule_enforcement_mode: Literal["rpg", "story", "chat"] = "rpg"
    generation_strictness: Literal["strict", "creative"] = "creative"
    selected_tone: Optional[dict[str, Any]] = None
    selected_image_styles: Optional[list[dict[str, Any]]] = None
    scripts_generation_enabled: bool = True
    generate_scene_images: bool = False
    generate_npc_images: bool = False
    generate_item_images: bool = False
    auto_validate_and_fix: bool = True
    skip_generation: bool = False


class GenerationStatusInput(BaseModel):
    adventure: str = Field(
        ..., min_length=1, description="Template ID, origin_id, or title substring."
    )
    include_logs: bool = Field(default=False, description="Include detailed generation logs.")


class AdventureTargetInput(BaseModel):
    adventure: str = Field(
        ..., min_length=1, description="Template ID, origin_id, or title substring."
    )


class GenerateRegionInput(BaseModel):
    adventure: str = Field(
        ..., min_length=1, description="Template ID, origin_id, or title substring."
    )
    section_id: str = Field(
        ..., min_length=1, max_length=50, description="Planned section ID to build."
    )
    brief: Optional[str] = Field(default=None, max_length=20_000)
    mode: Literal["simple", "advanced"] = "simple"
    context: Optional[dict[str, Any]] = None
    options: Optional[dict[str, Any]] = None


class AiValidateOrFixInput(BaseModel):
    adventure: str = Field(
        ..., min_length=1, description="Template ID, origin_id, or title substring."
    )
    include_ai: bool = Field(
        default=True, description="Include LLM logic validation when validating."
    )
    finding_code: Optional[str] = Field(
        default=None, description="Finding code to generate fix proposals for."
    )
    finding_message: Optional[str] = Field(default=None, description="Finding message to fix.")
    finding_severity: Severity = "warn"
    finding_location: Optional[str] = None
    finding_context: Optional[dict[str, Any]] = None
    force_refresh: bool = False


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


async def _tool_suggest_story_idea(
    ctx: McpRequestContext, args: SuggestStoryIdeaInput
) -> dict[str, Any]:
    req = StoryIdeaSuggestionRequest(
        title=args.title,
        story_idea=args.story_idea,
        selected_tone=args.selected_tone,
        rule_enforcement_mode=args.rule_enforcement_mode,
        language=args.language,
    )
    try:
        res = await template_routes.suggest_story_idea(req, current_user=ctx.user)
    except HTTPException as exc:
        raise _convert_http_error(exc) from exc
    return res.model_dump()


async def _tool_generate_adventure(
    ctx: McpRequestContext, args: GenerateAdventureInput
) -> dict[str, Any]:
    payload = CreateAdventureTemplatePayload(
        title=args.title,
        original_prompt=args.original_prompt,
        language=args.language,
        rule_enforcement_mode=args.rule_enforcement_mode,
        generation_strictness=args.generation_strictness,
        selected_tone=args.selected_tone,
        selected_image_styles=args.selected_image_styles,
        scripts_generation_enabled=args.scripts_generation_enabled,
        generate_scene_images=args.generate_scene_images,
        generate_npc_images=args.generate_npc_images,
        generate_item_images=args.generate_item_images,
        auto_validate_and_fix=args.auto_validate_and_fix,
        skip_generation=args.skip_generation,
    )
    try:
        created = await adventure_creation.create_adventure_records(ctx.db, payload, ctx.user)
    except HTTPException as exc:
        raise _convert_http_error(exc) from exc

    if not args.skip_generation:
        job = adventure_creation.GenerationJob(
            payload=payload,
            user_id=ctx.user.id,
            template_id=created.template.id,
            session_id=created.session.id,
            selected_image_styles=created.template.selected_image_styles,
            cover=created.cover,
        )
        task = asyncio.create_task(adventure_creation.run_background_generation(job))
        _GEN_TASKS.add(task)
        task.add_done_callback(_GEN_TASKS.discard)

    return {
        "template_id": created.template.id,
        "session_id": created.session.id,
        "avatar_id": created.avatar.id,
        "status": "skipped" if args.skip_generation else "generating",
    }


async def _tool_get_generation_status(
    ctx: McpRequestContext, args: GenerationStatusInput
) -> dict[str, Any]:
    tpl = await resolve_adventure_template(ctx.db, args.adventure, owner_id=ctx.scoped_owner_id)
    sections = [
        {
            "id": s.get("id"),
            "label": s.get("label"),
            "status": s.get("status"),
            "generation_error": s.get("generation_error") or None,
        }
        for s in normalize_sections(tpl.world_sections)
    ]
    payload: dict[str, Any] = {
        "template_id": tpl.id,
        "title": tpl.title,
        "status": tpl.creation_status or "Unknown",
        "is_ready": bool(tpl.is_ready),
        "error": tpl.creation_error,
        "sections": sections,
    }
    if args.include_logs:
        payload["logs"] = tpl.generation_logs or []
    return payload


async def _tool_cancel_generation(
    ctx: McpRequestContext, args: AdventureTargetInput
) -> dict[str, Any]:
    tpl = await resolve_adventure_template(ctx.db, args.adventure, owner_id=ctx.scoped_owner_id)
    was_ready = bool(tpl.is_ready)
    if not was_ready:
        tpl.creation_status = "Cancelled"
        await ctx.db.commit()
    return {"template_id": tpl.id, "status": "cancelled", "was_ready": was_ready}


async def _tool_generate_region(
    ctx: McpRequestContext, args: GenerateRegionInput
) -> dict[str, Any]:
    tpl = await resolve_adventure_template(ctx.db, args.adventure, owner_id=ctx.scoped_owner_id)
    owner = await _acting_owner(ctx, tpl)
    req_data: dict[str, Any] = {"brief": args.brief, "mode": args.mode}
    if args.context is not None:
        req_data["context"] = args.context
    if args.options is not None:
        req_data["options"] = args.options
    req = SectionGenerateRequest.model_validate(req_data)
    try:
        res = await section_generation.start_section_generation(
            tpl.id, args.section_id, req, db=ctx.db, current_user=owner
        )
    except HTTPException as exc:
        raise _convert_http_error(exc) from exc
    return {"template_id": tpl.id, "section_id": res["section_id"], "status": res["status"]}


async def _tool_ai_validate_and_fix(
    ctx: McpRequestContext, args: AiValidateOrFixInput
) -> dict[str, Any]:
    tpl = await resolve_adventure_template(ctx.db, args.adventure, owner_id=ctx.scoped_owner_id)
    owner = await _acting_owner(ctx, tpl)
    try:
        if args.finding_code and args.finding_message:
            req = AIFixSuggestionsRequest(
                finding_code=args.finding_code,
                finding_message=args.finding_message,
                finding_severity=args.finding_severity,
                finding_location=args.finding_location,
                finding_context=args.finding_context,
            )
            resp = await ai_fix_suggest.ai_suggest_fix_for_finding(
                tpl.id,
                req,
                force_refresh=args.force_refresh,
                db=ctx.db,
                current_user=owner,
            )
            return {"mode": "suggest_fix", "template_id": tpl.id, **resp.model_dump()}

        run = await editing_validation.execute_validation_run(
            ctx.db, tpl.id, owner, args.include_ai
        )
    except HTTPException as exc:
        raise _convert_http_error(exc) from exc
    return {
        "mode": "validate",
        "template_id": tpl.id,
        "structural_findings": [f.model_dump() for f in run.structural_findings],
        "ai_findings": [f.model_dump() for f in run.ai_findings],
        "ai_skipped_reason": run.ai_skipped_reason,
    }


def register_generation_tools() -> None:
    """Register all ``generate_adventures`` MCP tools."""
    mcp_registry.register_tool(
        ToolSpec(
            name="suggest_story_idea",
            description="Generate or refine an adventure title and Story Idea using the configured small LLM.",
            feature="generate_adventures",
            input_model=SuggestStoryIdeaInput,
            handler=_tool_suggest_story_idea,
            read_only=True,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="generate_adventure",
            description="Start asynchronous World-Builder adventure generation from a Story Idea or tagged blueprint.",
            feature="generate_adventures",
            input_model=GenerateAdventureInput,
            handler=_tool_generate_adventure,
            read_only=False,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="get_generation_status",
            description="Poll adventure or region generation progress, status, errors, and optional logs.",
            feature="generate_adventures",
            input_model=GenerationStatusInput,
            handler=_tool_get_generation_status,
            read_only=True,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="cancel_generation",
            description="Cancel an in-progress adventure generation job.",
            feature="generate_adventures",
            input_model=AdventureTargetInput,
            handler=_tool_cancel_generation,
            read_only=False,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="generate_region",
            description="Start asynchronous Region Builder generation for a planned world section.",
            feature="generate_adventures",
            input_model=GenerateRegionInput,
            handler=_tool_generate_region,
            read_only=False,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="ai_validate_and_suggest_fixes",
            description="Run AI logic validation on an adventure, or request reviewable fix proposals for a finding.",
            feature="generate_adventures",
            input_model=AiValidateOrFixInput,
            handler=_tool_ai_validate_and_fix,
            read_only=True,
        )
    )
