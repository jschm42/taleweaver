"""Admin endpoints for managing the embedded MCP server settings and access tokens."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import get_current_admin
from backend.core.database import get_db
from backend.core.global_settings import get_server_settings_for_update, read_server_settings
from backend.core.mcp_settings import (
    MCP_FEATURE_KEYS,
    McpFeature,
    McpFeatureFlags,
    McpSettings,
    McpTokenStatus,
    generate_mcp_token,
    normalize_utc,
    public_mcp_settings,
    token_status,
)
from backend.models.base import utc_now
from backend.models.mcp_token import McpToken
from backend.models.user import User

router = APIRouter(prefix="/settings/mcp", tags=["Settings"])


class McpSettingsPayload(BaseModel):
    """Admin-editable MCP server configuration."""

    enabled: bool = False
    features: McpFeatureFlags = Field(default_factory=McpFeatureFlags)
    allow_destructive: bool = False
    allow_cross_user_access: bool = False


class CreateMcpTokenPayload(BaseModel):
    """Payload to issue a new MCP bearer access token."""

    name: str = Field(..., min_length=1, max_length=100)
    user_id: Optional[str] = Field(default=None, max_length=36)
    allowed_features: Optional[list[McpFeature]] = None
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=3650)


class McpTokenResponse(BaseModel):
    """Public token metadata (never includes the hash or secret)."""

    id: str
    name: str
    token_prefix: str
    user_id: str
    username: str
    user_role: str
    allowed_features: Optional[list[str]]
    status: McpTokenStatus
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    revoked_at: Optional[datetime]


class McpTokenCreatedResponse(BaseModel):
    """Returned once when a token is created; ``plain_token`` is never shown again."""

    token: McpTokenResponse
    plain_token: str


def _serialize_token(row: McpToken, username: str, user_role: str) -> McpTokenResponse:
    return McpTokenResponse(
        id=row.id,
        name=row.name,
        token_prefix=row.token_prefix,
        user_id=row.user_id,
        username=username,
        user_role=user_role,
        allowed_features=row.allowed_features,
        status=token_status(row.revoked_at, row.expires_at),
        created_at=normalize_utc(row.created_at) or utc_now(),
        expires_at=normalize_utc(row.expires_at),
        last_used_at=normalize_utc(row.last_used_at),
        revoked_at=normalize_utc(row.revoked_at),
    )


def _canonical_features(features: Optional[list[McpFeature]]) -> Optional[list[str]]:
    if features is None:
        return None
    requested = set(features)
    if not requested:
        raise HTTPException(
            status_code=400,
            detail="Select at least one feature or inherit server settings.",
        )
    return [key for key in MCP_FEATURE_KEYS if key in requested]


@router.get("")
async def get_mcp_settings(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """Return normalized server-wide MCP settings."""
    server = await read_server_settings(db)
    return public_mcp_settings(server.mcp_settings)


@router.post("")
async def update_mcp_settings(
    payload: McpSettingsPayload,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """Update server-wide MCP settings."""
    server = await get_server_settings_for_update(db)
    server.mcp_settings = McpSettings.model_validate(payload.model_dump()).model_dump()
    await db.commit()
    return public_mcp_settings(server.mcp_settings)


@router.get("/tokens", response_model=list[McpTokenResponse])
async def list_mcp_tokens(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> list[McpTokenResponse]:
    """List all issued MCP access tokens (active, expired, and revoked)."""
    stmt = (
        select(McpToken, User.username, User.role)
        .outerjoin(User, McpToken.user_id == User.id)
        .order_by(McpToken.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        _serialize_token(token, username or "Unknown", role or "user")
        for token, username, role in rows
    ]


@router.post("/tokens", response_model=McpTokenCreatedResponse, status_code=201)
async def create_mcp_token(
    payload: CreateMcpTokenPayload,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> McpTokenCreatedResponse:
    """Issue a new MCP bearer access token bound to a TaleWeaver user."""
    clean_name = payload.name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Token name must not be blank.")

    target_user_id = (payload.user_id or "").strip() or admin.id
    target_user = await db.get(User, target_user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail="Target user not found.")

    allowed_features = _canonical_features(payload.allowed_features)
    expires_at = (
        utc_now() + timedelta(days=payload.expires_in_days)
        if payload.expires_in_days is not None
        else None
    )
    plain_token, token_prefix, token_hash = generate_mcp_token()

    row = McpToken(
        name=clean_name,
        token_prefix=token_prefix,
        token_hash=token_hash,
        user_id=target_user.id,
        allowed_features=allowed_features,
        created_by_user_id=admin.id,
        expires_at=expires_at,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    return McpTokenCreatedResponse(
        token=_serialize_token(row, target_user.username, target_user.role),
        plain_token=plain_token,
    )


@router.delete("/tokens/{token_id}", response_model=McpTokenResponse)
async def revoke_mcp_token(
    token_id: str = Path(..., min_length=1, max_length=36),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> McpTokenResponse:
    """Revoke an MCP access token immediately."""
    row = await db.get(McpToken, token_id)
    if row is None:
        raise HTTPException(status_code=404, detail="MCP token not found.")

    if row.revoked_at is None:
        row.revoked_at = utc_now()
        await db.commit()
        await db.refresh(row)

    target_user = await db.get(User, row.user_id)
    return _serialize_token(
        row,
        target_user.username if target_user else "Unknown",
        target_user.role if target_user else "user",
    )
