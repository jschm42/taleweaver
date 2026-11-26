"""Live MCP resources for TaleWeaver docs, server catalogs, adventures, and sessions."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote

from backend.core.catalog_defaults import DEFAULT_IMAGE_STYLES, DEFAULT_TONES
from backend.core.config import PROJECT_ROOT
from backend.core.global_settings import read_server_settings
from backend.core.narrator_voices import DEFAULT_NARRATOR_VOICES
from backend.mcp.context import McpRequestContext
from backend.mcp.registry import ResourceSpec, ResourceTemplateSpec, mcp_registry
from backend.services.inspection_service import (
    get_adventure_summary,
    get_session_state,
    resolve_adventure_template,
)

_DOC_RESOURCES: tuple[tuple[str, str, str, Path], ...] = (
    (
        "taleweaver://docs/world-builder-syntax",
        "World-Builder Blueprint Syntax",
        "Full key reference for World-Builder Story Idea blueprint tags.",
        PROJECT_ROOT / "docs" / "world-builder-syntax.md",
    ),
    (
        "taleweaver://docs/blueprint-manual",
        "World-Builder Blueprint Manual",
        "Workflow, tag overview, and puzzle design advice for Story Idea blueprints.",
        PROJECT_ROOT / "docs" / "world-builder-blueprint-manual.md",
    ),
    (
        "taleweaver://docs/scripting-engine",
        "TaleWeaver Scripting Engine",
        "Sandboxed Python tw.* scripting API reference and triggers.",
        PROJECT_ROOT / "docs" / "scripting_engine.md",
    ),
    (
        "taleweaver://docs/adventure-format",
        "Adventure Manifest Format",
        "Specification of .adv and .adz adventure bundle formats.",
        PROJECT_ROOT / "docs" / "specs" / "adventure_format.md",
    ),
)


def _doc_reader(path: Path):
    async def read(_ctx: McpRequestContext, _params: dict[str, str]) -> tuple[str, str]:
        if not path.is_file():
            raise LookupError(f"Documentation file not found: {path.name}")
        return path.read_text(encoding="utf-8"), "text/markdown"

    return read


def _catalog_reader(field: str, fallback: object):
    async def read(ctx: McpRequestContext, _params: dict[str, str]) -> tuple[str, str]:
        server = await read_server_settings(ctx.db)
        data = getattr(server, field, None) or fallback
        return json.dumps(data, indent=2, ensure_ascii=False), "application/json"

    return read


async def _read_adventure_summary(
    ctx: McpRequestContext, params: dict[str, str]
) -> tuple[str, str]:
    ident = unquote(params["template_id"])
    tpl = await resolve_adventure_template(ctx.db, ident, owner_id=ctx.scoped_owner_id)
    summary = await get_adventure_summary(ctx.db, tpl.id)
    return json.dumps(summary, indent=2, ensure_ascii=False, default=str), "application/json"


async def _read_session_state(ctx: McpRequestContext, params: dict[str, str]) -> tuple[str, str]:
    sid = unquote(params["session_id"])
    state = await get_session_state(ctx.db, sid, owner_id=ctx.scoped_owner_id)
    return json.dumps(state, indent=2, ensure_ascii=False, default=str), "application/json"


def register_resources() -> None:
    """Register static and parameterized MCP resources."""
    for uri, name, desc, path in _DOC_RESOURCES:
        mcp_registry.register_resource(
            ResourceSpec(
                uri=uri,
                name=name,
                description=desc,
                mime_type="text/markdown",
                feature="read_adventures",
                reader=_doc_reader(path),
            )
        )

    catalogs = (
        (
            "taleweaver://catalogs/styles",
            "Image Styles Catalog",
            "Configured server image styles catalog.",
            "image_styles_catalog",
            DEFAULT_IMAGE_STYLES,
        ),
        (
            "taleweaver://catalogs/tones",
            "Narrative Tones Catalog",
            "Configured server narrative tones catalog.",
            "tone_catalog",
            DEFAULT_TONES,
        ),
        (
            "taleweaver://catalogs/narrator-voices",
            "Narrator Voices Catalog",
            "Configured server narrator persona voices catalog.",
            "narrator_voice_catalog",
            DEFAULT_NARRATOR_VOICES,
        ),
    )
    for uri, name, desc, field, fallback in catalogs:
        mcp_registry.register_resource(
            ResourceSpec(
                uri=uri,
                name=name,
                description=desc,
                mime_type="application/json",
                feature="read_adventures",
                reader=_catalog_reader(field, fallback),
            )
        )

    mcp_registry.register_resource_template(
        ResourceTemplateSpec(
            uri_template="taleweaver://adventures/{template_id}/summary",
            pattern=re.compile(r"^taleweaver://adventures/(?P<template_id>[^/]+)/summary$"),
            name="Adventure Summary",
            description="Compact ID index of an adventure template.",
            mime_type="application/json",
            feature="read_adventures",
            reader=_read_adventure_summary,
        )
    )
    mcp_registry.register_resource_template(
        ResourceTemplateSpec(
            uri_template="taleweaver://sessions/{session_id}/state",
            pattern=re.compile(r"^taleweaver://sessions/(?P<session_id>[^/]+)/state$"),
            name="Game Session State",
            description="Full runtime state snapshot of a TaleWeaver game session.",
            mime_type="application/json",
            feature="read_sessions",
            reader=_read_session_state,
        )
    )
