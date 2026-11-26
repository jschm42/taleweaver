"""Registers all MCP tools, resources, and prompts and exposes ``mcp_router``."""

from __future__ import annotations

from backend.mcp.prompts import register_prompts
from backend.mcp.resources import register_resources
from backend.mcp.tools_diagnostics import register_diagnostics_tools
from backend.mcp.tools_editor import register_editor_tools
from backend.mcp.tools_editor_media import register_editor_media_tools
from backend.mcp.tools_library import register_library_tools
from backend.mcp.tools_sessions import register_session_tools
from backend.mcp.transport import router as mcp_router

_INIT_STATE = {"done": False}


def init_mcp_server() -> None:
    """Populate the MCP registry once at import/startup."""
    if _INIT_STATE["done"]:
        return
    register_library_tools()
    register_session_tools()
    register_diagnostics_tools()
    register_editor_tools()
    register_editor_media_tools()
    register_resources()
    register_prompts()
    _INIT_STATE["done"] = True


init_mcp_server()

__all__ = ["init_mcp_server", "mcp_router"]
