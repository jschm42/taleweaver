"""Central MCP registry for tools, resources, resource templates, and workflow prompts."""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from backend.core.mcp_settings import McpFeature
from backend.mcp.context import McpPermissionError, McpRequestContext

logger = logging.getLogger(__name__)

ToolHandler = Callable[[McpRequestContext, Any], Awaitable[Any]]
ResourceReader = Callable[[McpRequestContext, dict[str, str]], Awaitable[tuple[str, str]]]
PromptBuilder = Callable[[McpRequestContext, dict[str, str]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ToolSpec:
    """Definition of one MCP tool and its required permissions."""

    name: str
    description: str
    feature: McpFeature
    input_model: type[BaseModel]
    handler: ToolHandler
    read_only: bool = True
    destructive: bool = False
    requires_destructive_flag: bool = False
    extra_features: tuple[McpFeature, ...] = ()


@dataclass(frozen=True)
class ResourceSpec:
    """Static MCP resource definition."""

    uri: str
    name: str
    description: str
    mime_type: str
    feature: McpFeature
    reader: ResourceReader


@dataclass(frozen=True)
class ResourceTemplateSpec:
    """Parameterized MCP resource URI template definition."""

    uri_template: str
    pattern: re.Pattern[str]
    name: str
    description: str
    mime_type: str
    feature: McpFeature
    reader: ResourceReader


@dataclass(frozen=True)
class PromptArgument:
    """One argument accepted by an MCP prompt."""

    name: str
    description: str
    required: bool = False


@dataclass(frozen=True)
class PromptSpec:
    """MCP prompt definition."""

    name: str
    description: str
    feature: McpFeature
    arguments: list[PromptArgument] = field(default_factory=list)
    builder: PromptBuilder = None  # type: ignore[assignment]


class McpRegistry:
    """Stores MCP tools, resources, and prompts with permission-filtered discovery and calls."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._resources: dict[str, ResourceSpec] = {}
        self._templates: list[ResourceTemplateSpec] = []
        self._prompts: dict[str, PromptSpec] = {}

    def register_tool(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def register_resource(self, spec: ResourceSpec) -> None:
        self._resources[spec.uri] = spec

    def register_resource_template(self, spec: ResourceTemplateSpec) -> None:
        if any(t.uri_template == spec.uri_template for t in self._templates):
            return
        self._templates.append(spec)

    def register_prompt(self, spec: PromptSpec) -> None:
        self._prompts[spec.name] = spec

    @staticmethod
    def _tool_allowed(ctx: McpRequestContext, spec: ToolSpec) -> bool:
        if not ctx.has_feature(spec.feature):
            return False
        if any(not ctx.has_feature(extra) for extra in spec.extra_features):
            return False
        return not (spec.requires_destructive_flag and not ctx.settings.get("allow_destructive"))

    def list_tools(self, ctx: McpRequestContext) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        for spec in self._tools.values():
            if not self._tool_allowed(ctx, spec):
                continue
            tools.append(
                {
                    "name": spec.name,
                    "description": spec.description,
                    "inputSchema": spec.input_model.model_json_schema(),
                    "annotations": {
                        "readOnlyHint": spec.read_only,
                        "destructiveHint": spec.destructive,
                        "idempotentHint": spec.read_only,
                    },
                }
            )
        return tools

    async def call_tool(
        self, ctx: McpRequestContext, name: str, raw_args: dict[str, Any] | None
    ) -> dict[str, Any]:
        spec = self._tools.get(name)
        if spec is None:
            raise KeyError(f"Unknown MCP tool '{name}'.")

        ctx.require_feature(spec.feature)
        for extra in spec.extra_features:
            ctx.require_feature(extra)
        if spec.requires_destructive_flag:
            ctx.require_destructive()

        parsed = spec.input_model.model_validate(raw_args or {})
        started = time.perf_counter()
        outcome = "ok"
        try:
            result = await spec.handler(ctx, parsed)
        except Exception:
            outcome = "error"
            raise
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            logger.info(
                "mcp.tool_call token_id=%s token_name=%s user=%s tool=%s status=%s duration_ms=%.1f",
                ctx.token.id,
                ctx.token.name,
                ctx.user.username,
                name,
                outcome,
                elapsed_ms,
            )

        structured = result if isinstance(result, dict) else {"result": result}
        text_payload = json.dumps(result, indent=2, ensure_ascii=False, default=str)
        return {
            "content": [{"type": "text", "text": text_payload}],
            "structuredContent": structured,
            "isError": False,
        }

    def list_resources(self, ctx: McpRequestContext) -> list[dict[str, Any]]:
        return [
            {
                "uri": spec.uri,
                "name": spec.name,
                "description": spec.description,
                "mimeType": spec.mime_type,
            }
            for spec in self._resources.values()
            if ctx.has_feature(spec.feature)
        ]

    def list_resource_templates(self, ctx: McpRequestContext) -> list[dict[str, Any]]:
        return [
            {
                "uriTemplate": spec.uri_template,
                "name": spec.name,
                "description": spec.description,
                "mimeType": spec.mime_type,
            }
            for spec in self._templates
            if ctx.has_feature(spec.feature)
        ]

    async def read_resource(self, ctx: McpRequestContext, uri: str) -> dict[str, Any]:
        static = self._resources.get(uri)
        if static is not None:
            ctx.require_feature(static.feature)
            text, mime_type = await static.reader(ctx, {})
            return {"uri": uri, "mimeType": mime_type, "text": text}

        for tmpl in self._templates:
            match = tmpl.pattern.fullmatch(uri)
            if match is None:
                continue
            ctx.require_feature(tmpl.feature)
            text, mime_type = await tmpl.reader(ctx, match.groupdict())
            return {"uri": uri, "mimeType": mime_type, "text": text}

        raise LookupError(f"Unknown MCP resource URI '{uri}'.")

    def list_prompts(self, ctx: McpRequestContext) -> list[dict[str, Any]]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "arguments": [
                    {
                        "name": arg.name,
                        "description": arg.description,
                        "required": arg.required,
                    }
                    for arg in spec.arguments
                ],
            }
            for spec in self._prompts.values()
            if ctx.has_feature(spec.feature)
        ]

    async def get_prompt(
        self, ctx: McpRequestContext, name: str, arguments: dict[str, str] | None
    ) -> dict[str, Any]:
        spec = self._prompts.get(name)
        if spec is None:
            raise LookupError(f"Unknown MCP prompt '{name}'.")
        ctx.require_feature(spec.feature)
        return await spec.builder(ctx, arguments or {})

    @staticmethod
    def permission_error_result(
        exc: McpPermissionError | LookupError | ValueError,
    ) -> dict[str, Any]:
        return {
            "content": [{"type": "text", "text": str(exc)}],
            "isError": True,
        }


mcp_registry = McpRegistry()
