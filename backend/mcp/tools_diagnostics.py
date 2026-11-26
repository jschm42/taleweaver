"""MCP tools for database diagnostics and LLM latency telemetry."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from backend.mcp.context import McpRequestContext
from backend.mcp.registry import ToolSpec, mcp_registry
from backend.services.inspection_service import get_db_status
from backend.services.telemetry_service import analyze_llm_telemetry


class EmptyInput(BaseModel):
    pass


class TelemetryInput(BaseModel):
    log_name: Optional[str] = Field(
        default=None,
        description="Optional .jsonl filename inside data/logs/ (defaults to llm_debug.jsonl or llm_telemetry.jsonl).",
    )
    since_minutes: int = Field(
        default=0,
        ge=0,
        le=10080,
        description="Only analyze events within N minutes of the latest event (0 = all).",
    )
    split_ts: Optional[str] = Field(
        default=None,
        description="Optional ISO timestamp to compute before/after p50 latency deltas.",
    )
    limit: int = Field(
        default=20, ge=0, le=200, description="Max rows per section (0 = unlimited)."
    )


async def _tool_get_db_status(ctx: McpRequestContext, _args: EmptyInput) -> dict[str, Any]:
    return await get_db_status(ctx.db)


async def _tool_get_llm_telemetry(_ctx: McpRequestContext, args: TelemetryInput) -> dict[str, Any]:
    return analyze_llm_telemetry(
        log_name=args.log_name,
        since_minutes=args.since_minutes,
        split_ts=args.split_ts,
        limit=args.limit,
    )


def register_diagnostics_tools() -> None:
    """Register all ``diagnostics`` MCP tools."""
    mcp_registry.register_tool(
        ToolSpec(
            name="get_db_status",
            description="Inspect database health, SQLite journal mode, table record counts, and data/ disk usage.",
            feature="diagnostics",
            input_model=EmptyInput,
            handler=_tool_get_db_status,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="get_llm_telemetry",
            description="Analyze LLM turn pipeline and request/response latency percentiles (p50/p90/p95) from runtime logs.",
            feature="diagnostics",
            input_model=TelemetryInput,
            handler=_tool_get_llm_telemetry,
        )
    )
