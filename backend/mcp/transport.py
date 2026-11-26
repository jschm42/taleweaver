"""Stateless Streamable HTTP JSON-RPC 2.0 transport for TaleWeaver MCP."""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.mcp.context import McpPermissionError, McpRequestContext, authenticate_mcp_request
from backend.mcp.registry import mcp_registry

SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
DEFAULT_PROTOCOL_VERSION = "2025-06-18"

router = APIRouter(tags=["MCP"])


def _jsonrpc_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _jsonrpc_result(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _negotiate_protocol_version(requested: Optional[str]) -> str:
    if requested in SUPPORTED_PROTOCOL_VERSIONS:
        return requested
    return DEFAULT_PROTOCOL_VERSION


async def _handle_initialize(ctx: McpRequestContext, params: dict[str, Any]) -> dict[str, Any]:
    capabilities: dict[str, Any] = {}
    if mcp_registry.list_tools(ctx):
        capabilities["tools"] = {"listChanged": False}
    if mcp_registry.list_resources(ctx) or mcp_registry.list_resource_templates(ctx):
        capabilities["resources"] = {"subscribe": False, "listChanged": False}
    if mcp_registry.list_prompts(ctx):
        capabilities["prompts"] = {"listChanged": False}

    return {
        "protocolVersion": _negotiate_protocol_version(params.get("protocolVersion")),
        "capabilities": capabilities,
        "serverInfo": {
            "name": "taleweaver",
            "title": "TaleWeaver MCP Server",
            "version": settings.APP_VERSION,
        },
        "instructions": (
            "Use TaleWeaver MCP tools to inspect adventures and sessions, read live docs, "
            "or run enabled authoring and diagnostics workflows."
        ),
    }


async def _handle_ping(_ctx: McpRequestContext, _params: dict[str, Any]) -> dict[str, Any]:
    return {}


async def _handle_tools_list(ctx: McpRequestContext, _params: dict[str, Any]) -> dict[str, Any]:
    return {"tools": mcp_registry.list_tools(ctx)}


async def _handle_resources_list(ctx: McpRequestContext, _params: dict[str, Any]) -> dict[str, Any]:
    return {"resources": mcp_registry.list_resources(ctx)}


async def _handle_resource_templates_list(
    ctx: McpRequestContext, _params: dict[str, Any]
) -> dict[str, Any]:
    return {"resourceTemplates": mcp_registry.list_resource_templates(ctx)}


async def _handle_prompts_list(ctx: McpRequestContext, _params: dict[str, Any]) -> dict[str, Any]:
    return {"prompts": mcp_registry.list_prompts(ctx)}


async def _handle_tools_call(ctx: McpRequestContext, params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name")
    if not isinstance(name, str) or not name.strip():
        raise _InvalidParamsError("tools/call requires a non-empty string 'name'.")
    arguments = params.get("arguments")
    if arguments is not None and not isinstance(arguments, dict):
        raise _InvalidParamsError("tools/call 'arguments' must be an object.")
    try:
        return await mcp_registry.call_tool(ctx, name, arguments)
    except KeyError as exc:
        raise _InvalidParamsError(str(exc)) from exc
    except (McpPermissionError, LookupError, ValueError, ValidationError) as exc:
        return mcp_registry.permission_error_result(
            exc
            if isinstance(exc, (McpPermissionError, LookupError, ValueError))
            else ValueError(str(exc))
        )


async def _handle_resources_read(ctx: McpRequestContext, params: dict[str, Any]) -> dict[str, Any]:
    uri = params.get("uri")
    if not isinstance(uri, str) or not uri.strip():
        raise _InvalidParamsError("resources/read requires a non-empty string 'uri'.")
    content = await mcp_registry.read_resource(ctx, uri.strip())
    return {"contents": [content]}


async def _handle_prompts_get(ctx: McpRequestContext, params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name")
    if not isinstance(name, str) or not name.strip():
        raise _InvalidParamsError("prompts/get requires a non-empty string 'name'.")
    raw_args = params.get("arguments")
    if raw_args is not None and not isinstance(raw_args, dict):
        raise _InvalidParamsError("prompts/get 'arguments' must be an object.")
    str_args = {str(k): str(v) for k, v in (raw_args or {}).items() if v is not None}
    return await mcp_registry.get_prompt(ctx, name.strip(), str_args)


class _InvalidParamsError(Exception):
    """Maps directly to JSON-RPC -32602 Invalid params."""


_METHOD_HANDLERS = {
    "initialize": _handle_initialize,
    "ping": _handle_ping,
    "tools/list": _handle_tools_list,
    "tools/call": _handle_tools_call,
    "resources/list": _handle_resources_list,
    "resources/templates/list": _handle_resource_templates_list,
    "resources/read": _handle_resources_read,
    "prompts/list": _handle_prompts_list,
    "prompts/get": _handle_prompts_get,
}


async def _dispatch_method(ctx: McpRequestContext, method: str, params: dict[str, Any]) -> Any:
    handler = _METHOD_HANDLERS.get(method)
    if handler is None:
        raise LookupError(f"Method not found: {method}")
    return await handler(ctx, params)


async def _execute_rpc(
    ctx: McpRequestContext, req_id: Any, method: str, params: dict[str, Any]
) -> dict[str, Any]:
    try:
        return _jsonrpc_result(req_id, await _dispatch_method(ctx, method, params))
    except _InvalidParamsError as exc:
        return _jsonrpc_error(req_id, -32602, str(exc))
    except McpPermissionError as exc:
        return _jsonrpc_error(req_id, -32003, str(exc))
    except LookupError as exc:
        code = -32601 if str(exc).startswith("Method not found:") else -32602
        return _jsonrpc_error(req_id, code, str(exc))
    except ValueError as exc:
        return _jsonrpc_error(req_id, -32602, str(exc))


async def _process_message(ctx: McpRequestContext, msg: Any) -> Optional[dict[str, Any]]:
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return _jsonrpc_error(None, -32600, "Invalid JSON-RPC 2.0 request object.")
    req_id = msg.get("id")
    is_notification = "id" not in msg
    method = msg.get("method")
    if not isinstance(method, str):
        return None if is_notification else _jsonrpc_error(req_id, -32600, "Missing method.")
    if is_notification or method.startswith("notifications/"):
        return None

    params = msg.get("params") or {}
    if not isinstance(params, dict):
        return _jsonrpc_error(req_id, -32602, "Params must be a JSON object.")
    return await _execute_rpc(ctx, req_id, method, params)


@router.post("/mcp")
async def mcp_post(request: Request, db: AsyncSession = Depends(get_db)) -> Response:
    """Stateless Streamable HTTP MCP JSON-RPC 2.0 endpoint."""
    ctx = await authenticate_mcp_request(db, request.headers.get("authorization"))
    proto = _negotiate_protocol_version(request.headers.get("mcp-protocol-version"))
    headers = {"MCP-Protocol-Version": proto}

    try:
        payload = json.loads(await request.body())
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JSONResponse(
            status_code=400,
            content=_jsonrpc_error(None, -32700, "Parse error: invalid JSON body."),
            headers=headers,
        )

    if isinstance(payload, list):
        if not payload:
            return JSONResponse(
                status_code=400,
                content=_jsonrpc_error(None, -32600, "Invalid empty JSON-RPC batch."),
                headers=headers,
            )
        responses = [
            resp for item in payload if (resp := await _process_message(ctx, item)) is not None
        ]
        if not responses:
            return Response(status_code=202, headers=headers)
        return JSONResponse(status_code=200, content=responses, headers=headers)

    response_obj = await _process_message(ctx, payload)
    if response_obj is None:
        return Response(status_code=202, headers=headers)
    return JSONResponse(status_code=200, content=response_obj, headers=headers)


@router.get("/mcp")
async def mcp_get() -> Response:
    """SSE standalone stream is omitted in stateless mode; clients use POST /mcp."""
    return JSONResponse(
        status_code=405,
        content={
            "detail": "GET SSE stream is not supported; send JSON-RPC requests via POST /mcp."
        },
        headers={"Allow": "POST, DELETE"},
    )


@router.delete("/mcp")
async def mcp_delete(request: Request, db: AsyncSession = Depends(get_db)) -> Response:
    """Acknowledge MCP session termination in stateless mode."""
    await authenticate_mcp_request(db, request.headers.get("authorization"))
    return Response(status_code=204)
