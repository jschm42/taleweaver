"""Server-wide MCP configuration and access token helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, ValidationError

MCP_ENDPOINT_PATH = "/mcp"
MCP_BEARER_PREFIX = "tw_mcp_"

McpFeature = Literal[
    "read_adventures",
    "read_sessions",
    "edit_adventures",
    "generate_adventures",
    "generate_media",
    "diagnostics",
]

MCP_FEATURE_KEYS: tuple[McpFeature, ...] = (
    "read_adventures",
    "read_sessions",
    "edit_adventures",
    "generate_adventures",
    "generate_media",
    "diagnostics",
)

McpTokenStatus = Literal["active", "expired", "revoked"]


class McpFeatureFlags(BaseModel):
    """Granular feature toggles for the embedded MCP server."""

    read_adventures: bool = True
    read_sessions: bool = True
    edit_adventures: bool = False
    generate_adventures: bool = False
    generate_media: bool = False
    diagnostics: bool = True


class McpSettings(BaseModel):
    """Admin settings for the MCP endpoint (``ServerSettings.mcp_settings``)."""

    enabled: bool = False
    features: McpFeatureFlags = Field(default_factory=McpFeatureFlags)
    allow_destructive: bool = False
    allow_cross_user_access: bool = False


def normalize_mcp_settings(raw: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Return stored MCP settings merged with defaults; invalid payloads fall back cleanly."""
    try:
        return McpSettings.model_validate(dict(raw or {})).model_dump()
    except ValidationError:
        return McpSettings().model_dump()


def public_mcp_settings(raw: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Return normalized MCP settings enriched with the mount path for the admin UI."""
    data = normalize_mcp_settings(raw)
    data["endpoint_path"] = MCP_ENDPOINT_PATH
    return data


def hash_mcp_token(plain_token: str) -> str:
    """Return the SHA-256 hex digest of a raw MCP bearer token."""
    return hashlib.sha256(plain_token.encode("utf-8")).hexdigest()


def generate_mcp_token() -> tuple[str, str, str]:
    """Generate a new MCP bearer token and return ``(plain_token, prefix, sha256_hash)``."""
    plain = f"{MCP_BEARER_PREFIX}{secrets.token_urlsafe(32)}"
    prefix = plain[:14]
    return plain, prefix, hash_mcp_token(plain)


def verify_mcp_token_hash(plain_token: str, expected_hash: str) -> bool:
    """Constant-time comparison between a presented bearer token and its stored SHA-256 hash."""
    if not plain_token or not expected_hash:
        return False
    return hmac.compare_digest(hash_mcp_token(plain_token), expected_hash)


def effective_mcp_features(
    raw_settings: Optional[dict[str, Any]], token_allowed: Optional[list[str]] = None
) -> set[str]:
    """Compute effective feature keys as ``server_enabled ∩ token_allowed``."""
    settings = normalize_mcp_settings(raw_settings)
    if not settings["enabled"]:
        return set()
    server_enabled = {key for key, on in settings["features"].items() if on}
    if token_allowed is None:
        return server_enabled
    return server_enabled & set(token_allowed)


def normalize_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Attach UTC timezone to naive datetimes returned by SQLite."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def token_status(
    revoked_at: Optional[datetime],
    expires_at: Optional[datetime],
    now: Optional[datetime] = None,
) -> McpTokenStatus:
    """Determine lifecycle status of an MCP token."""
    if revoked_at is not None:
        return "revoked"
    exp = normalize_utc(expires_at)
    current = normalize_utc(now) or datetime.now(UTC)
    if exp is not None and exp <= current:
        return "expired"
    return "active"
