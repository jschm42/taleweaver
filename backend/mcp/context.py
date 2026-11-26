"""Authentication, acting-user hydration, and feature-scope enforcement for MCP requests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.global_settings import apply_global_settings, read_server_settings
from backend.core.mcp_settings import (
    McpFeature,
    effective_mcp_features,
    hash_mcp_token,
    normalize_mcp_settings,
    token_status,
    verify_mcp_token_hash,
)
from backend.models.base import utc_now
from backend.models.mcp_token import McpToken
from backend.models.user import User


class McpPermissionError(Exception):
    """Raised when an MCP token lacks permission for a requested tool, resource, or prompt."""


@dataclass
class McpRequestContext:
    """Resolved request context bound to an authenticated MCP token and acting user."""

    db: AsyncSession
    user: User
    token: McpToken
    settings: dict[str, Any]
    effective_features: set[str]

    @property
    def can_access_all_users(self) -> bool:
        return bool(self.settings.get("allow_cross_user_access")) and self.user.role == "admin"

    @property
    def scoped_owner_id(self) -> Optional[str]:
        return None if self.can_access_all_users else self.user.id

    def has_feature(self, feature: McpFeature) -> bool:
        return feature in self.effective_features

    def require_feature(self, feature: McpFeature) -> None:
        if not self.has_feature(feature):
            raise McpPermissionError(
                f"Feature '{feature}' is not enabled for this server or token."
            )

    def require_destructive(self) -> None:
        self.require_feature("edit_adventures")
        if not self.settings.get("allow_destructive"):
            raise McpPermissionError(
                "Destructive template deletion is disabled in server MCP settings."
            )


def _extract_bearer(auth_header: Optional[str]) -> str:
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header; expected Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token.strip()


async def authenticate_mcp_request(
    db: AsyncSession, auth_header: Optional[str]
) -> McpRequestContext:
    """Validate server enablement, Bearer token hash, expiry/revocation, and acting user."""
    server = await read_server_settings(db)
    mcp_cfg = normalize_mcp_settings(server.mcp_settings)
    if not mcp_cfg["enabled"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP endpoint is disabled by the server administrator.",
        )

    raw_token = _extract_bearer(auth_header)
    token_hash = hash_mcp_token(raw_token)
    row = (
        await db.execute(select(McpToken).where(McpToken.token_hash == token_hash))
    ).scalar_one_or_none()
    if row is None or not verify_mcp_token_hash(raw_token, row.token_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MCP access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if token_status(row.revoked_at, row.expires_at) != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="MCP access token is revoked or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    acting_user = await db.get(User, row.user_id)
    if acting_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Acting user for MCP token no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    await apply_global_settings(db, acting_user)
    row.last_used_at = utc_now()
    await db.commit()

    effective = effective_mcp_features(mcp_cfg, row.allowed_features)
    return McpRequestContext(
        db=db,
        user=acting_user,
        token=row,
        settings=mcp_cfg,
        effective_features=effective,
    )
