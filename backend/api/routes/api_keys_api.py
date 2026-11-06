"""Personal API keys of a player and the admin's key policy (who pays for which provider).

Players manage only their own keys (``/users/me/api-keys``). Keys are stored encrypted and
never returned; responses only say whether a key exists and where the effective key comes
from. Admins set the server-wide policy and per-user overrides.
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.api_keys import (
    KEY_POLICIES,
    KEY_PROVIDER_IDS,
    MAX_API_KEY_LENGTH,
    PERSONAL_KEY_POLICIES,
    key_providers,
    key_source,
    normalize_policy_map,
    resolve_policy,
)
from backend.core.auth import get_current_admin, get_current_user
from backend.core.database import get_db
from backend.core.global_settings import (
    apply_global_settings,
    get_server_settings_for_update,
    read_server_settings,
)
from backend.core.security import encryption_util
from backend.models.user import User
from backend.services.model_discovery.service import verify_api_key

logger = logging.getLogger(__name__)
router = APIRouter(tags=["API Keys"])

USER_DEP = Depends(get_current_user)
ADMIN_DEP = Depends(get_current_admin)
DB_DEP = Depends(get_db)


class PersonalKeyPayload(BaseModel):
    api_key: str = Field(min_length=1, max_length=MAX_API_KEY_LENGTH)


class KeyPolicyPayload(BaseModel):
    """``{provider: policy}``; providers left out (or set to ``server``) use the server key."""

    policy: dict[str, str] = Field(default_factory=dict)


def _known_provider(provider: str) -> str:
    provider = (provider or "").lower()
    if provider not in KEY_PROVIDER_IDS:
        raise HTTPException(status_code=404, detail=f"Unknown provider '{provider}'.")
    return provider


def _validated_policy_map(raw: dict[str, str]) -> dict[str, str]:
    """Reject unknown providers or policies instead of dropping them silently."""
    for provider, policy in raw.items():
        _known_provider(provider)
        if policy not in KEY_POLICIES:
            raise HTTPException(status_code=422, detail=f"Unknown key policy '{policy}'.")
    return normalize_policy_map(raw)


def _clean_key(raw: str) -> str:
    """Trim whitespace and one pair of surrounding quotes (pasted from a .env file)."""
    key = raw.strip()
    if len(key) >= 2 and key[0] == key[-1] and key[0] in {'"', "'"}:
        key = key[1:-1].strip()
    if not key:
        raise HTTPException(status_code=400, detail="API key cannot be empty.")
    return key


def _provider_rows(user: User, server_policy: Optional[dict[str, str]]) -> list[dict[str, Any]]:
    personal = user.personal_api_keys or {}
    overrides = user.api_key_policy_overrides or {}
    rows = []
    for provider in key_providers():
        pid = provider["id"]
        policy = resolve_policy(pid, server_policy, overrides)
        rows.append(
            {
                "id": pid,
                "name": provider["name"],
                "policy": policy,
                "can_store_key": policy in PERSONAL_KEY_POLICIES,
                "has_personal_key": bool(personal.get(pid)),
                "source": key_source(user.encrypted_api_keys, pid),
            }
        )
    return rows


async def _my_keys_response(db: AsyncSession, user: User) -> dict[str, Any]:
    server = await read_server_settings(db)
    await apply_global_settings(db, user)
    rows = _provider_rows(user, server.api_key_policy)
    return {"providers": rows, "personal_keys_allowed": any(r["can_store_key"] for r in rows)}


# --- Player -------------------------------------------------------------------------------


@router.get("/users/me/api-keys")
async def list_my_api_keys(current_user: User = USER_DEP, db: AsyncSession = DB_DEP):
    """Per provider: policy, whether a personal key is stored, and the effective key source."""
    return await _my_keys_response(db, current_user)


@router.put("/users/me/api-keys/{provider}")
async def store_my_api_key(
    provider: str,
    payload: PersonalKeyPayload,
    current_user: User = USER_DEP,
    db: AsyncSession = DB_DEP,
):
    """Store a personal key; it is checked with a free model-list call where possible."""
    provider = _known_provider(provider)
    server = await read_server_settings(db)
    policy = resolve_policy(provider, server.api_key_policy, current_user.api_key_policy_overrides)
    if policy not in PERSONAL_KEY_POLICIES:
        raise HTTPException(
            status_code=403, detail="This server does not accept personal keys for this provider."
        )
    key = _clean_key(payload.api_key)
    verified, error = await verify_api_key(provider, key)
    if error:
        raise HTTPException(status_code=400, detail=f"Your key was rejected: {error}")

    current_user.personal_api_keys = {
        **(current_user.personal_api_keys or {}),
        provider: encryption_util.encrypt_key(key),
    }
    await db.commit()
    logger.info("User %s stored a personal key for %s", current_user.id, provider)
    return {**await _my_keys_response(db, current_user), "verified": verified}


@router.delete("/users/me/api-keys/{provider}")
async def delete_my_api_key(
    provider: str, current_user: User = USER_DEP, db: AsyncSession = DB_DEP
):
    """Remove a personal key; the provider falls back to what the policy allows."""
    provider = _known_provider(provider)
    keys = dict(current_user.personal_api_keys or {})
    if provider not in keys:
        raise HTTPException(status_code=404, detail="No personal key stored for this provider.")
    del keys[provider]
    current_user.personal_api_keys = keys or None
    await db.commit()
    logger.info("User %s removed the personal key for %s", current_user.id, provider)
    return await _my_keys_response(db, current_user)


# --- Admin --------------------------------------------------------------------------------


@router.get("/settings/key-policy")
async def get_key_policy(_admin: User = ADMIN_DEP, db: AsyncSession = DB_DEP):
    """Server-wide key policy and the providers it applies to."""
    server = await read_server_settings(db)
    return {
        "policy": normalize_policy_map(server.api_key_policy),
        "providers": key_providers(),
        "policies": list(KEY_POLICIES),
    }


@router.put("/settings/key-policy")
async def update_key_policy(
    payload: KeyPolicyPayload, _admin: User = ADMIN_DEP, db: AsyncSession = DB_DEP
):
    server = await get_server_settings_for_update(db)
    server.api_key_policy = _validated_policy_map(payload.policy) or None
    await db.commit()
    return {"status": "success", "policy": normalize_policy_map(server.api_key_policy)}


@router.put("/users/{user_id}/key-policy")
async def update_user_key_policy(
    user_id: str, payload: KeyPolicyPayload, _admin: User = ADMIN_DEP, db: AsyncSession = DB_DEP
):
    """Per-user overrides of the key policy (e.g. ``server`` for family members)."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalars().first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    overrides = {
        provider.lower(): policy
        for provider, policy in payload.policy.items()
        if _known_provider(provider) and policy in KEY_POLICIES
    }
    if len(overrides) != len(payload.policy):
        raise HTTPException(status_code=422, detail="Unknown key policy.")
    # Overrides may say "server" explicitly, so keep them unfiltered.
    user.api_key_policy_overrides = overrides or None
    await db.commit()
    return {"status": "success", "overrides": overrides}
