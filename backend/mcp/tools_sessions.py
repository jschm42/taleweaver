"""Read-only MCP tools for inspecting game sessions, chat history, checkpoints, and integrity."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from backend.mcp.context import McpRequestContext
from backend.mcp.registry import ToolSpec, mcp_registry
from backend.services.inspection_service import (
    check_session_integrity,
    get_session_chat,
    get_session_checkpoints,
    get_session_state,
    list_sessions,
    resolve_adventure_template,
)


class ListSessionsInput(BaseModel):
    adventure: Optional[str] = Field(
        default=None, description="Optional template ID, origin_id, or title substring filter."
    )
    limit: int = Field(
        default=20, ge=1, le=200, description="Maximum number of sessions to return."
    )


class SessionStateInput(BaseModel):
    session_id: str = Field(..., min_length=1, description="Game session ID or unique prefix.")
    include_entities: bool = Field(
        default=True, description="Include merged world entities and overrides."
    )
    hidden_only: bool = Field(
        default=False, description="When include_entities is true, return only hidden entities."
    )


class SessionChatInput(BaseModel):
    session_id: str = Field(..., min_length=1, description="Game session ID or unique prefix.")
    limit: int = Field(
        default=30, ge=1, le=200, description="Maximum number of messages to return."
    )
    offset: int = Field(
        default=0, ge=0, description="Pagination offset from the start of chat history."
    )


class SessionIdInput(BaseModel):
    session_id: str = Field(..., min_length=1, description="Game session ID or unique prefix.")


async def _tool_list_sessions(ctx: McpRequestContext, args: ListSessionsInput) -> dict[str, Any]:
    template_id: Optional[str] = None
    if args.adventure:
        tpl = await resolve_adventure_template(ctx.db, args.adventure, owner_id=ctx.scoped_owner_id)
        template_id = tpl.id
    sessions = await list_sessions(
        ctx.db, owner_id=ctx.scoped_owner_id, template_id=template_id, limit=args.limit
    )
    return {"count": len(sessions), "sessions": sessions}


async def _tool_get_session_state(
    ctx: McpRequestContext, args: SessionStateInput
) -> dict[str, Any]:
    return await get_session_state(
        ctx.db,
        args.session_id,
        owner_id=ctx.scoped_owner_id,
        include_entities=args.include_entities,
        hidden_only=args.hidden_only,
    )


async def _tool_get_session_chat(ctx: McpRequestContext, args: SessionChatInput) -> dict[str, Any]:
    return await get_session_chat(
        ctx.db,
        args.session_id,
        owner_id=ctx.scoped_owner_id,
        limit=args.limit,
        offset=args.offset,
    )


async def _tool_get_session_checkpoints(
    ctx: McpRequestContext, args: SessionIdInput
) -> dict[str, Any]:
    checkpoints = await get_session_checkpoints(
        ctx.db, args.session_id, owner_id=ctx.scoped_owner_id
    )
    return {"count": len(checkpoints), "checkpoints": checkpoints}


async def _tool_check_session_integrity(
    ctx: McpRequestContext, args: SessionIdInput
) -> dict[str, Any]:
    return await check_session_integrity(ctx.db, args.session_id, owner_id=ctx.scoped_owner_id)


def register_session_tools() -> None:
    """Register all ``read_sessions`` MCP tools."""
    mcp_registry.register_tool(
        ToolSpec(
            name="list_sessions",
            description="List recent TaleWeaver game sessions with player, scene, and status metadata.",
            feature="read_sessions",
            input_model=ListSessionsInput,
            handler=_tool_list_sessions,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="get_session_state",
            description="Inspect full runtime session state: avatar stats, inventory, overrides, quests, and pending expansions.",
            feature="read_sessions",
            input_model=SessionStateInput,
            handler=_tool_get_session_state,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="get_session_chat",
            description="Read paginated User, Assistant, and System conversation turns for a game session.",
            feature="read_sessions",
            input_model=SessionChatInput,
            handler=_tool_get_session_chat,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="get_session_checkpoints",
            description="List saved Chronicles Timeline checkpoints for a game session.",
            feature="read_sessions",
            input_model=SessionIdInput,
            handler=_tool_get_session_checkpoints,
        )
    )
    mcp_registry.register_tool(
        ToolSpec(
            name="check_session_integrity",
            description="Verify session avatar inventory/equipment fields against template object definitions.",
            feature="read_sessions",
            input_model=SessionIdInput,
            handler=_tool_check_session_integrity,
        )
    )
