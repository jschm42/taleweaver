"""Check before a chat turn that the player may use the providers of its LLM passes.

A provider with policy ``user_required`` (and no personal key) or ``disabled`` would fail in
the middle of the turn. Checking up front keeps the turn fail-safe: it is rejected before any
message is stored or any state changes.
"""

from typing import Any, Optional

from fastapi import HTTPException

from backend.core.api_keys import (
    SOURCE_DISABLED,
    SOURCE_MISSING,
    key_source,
    personal_key_message,
    unavailable_providers,
)
from backend.models.user import User

PERSONAL_KEY_REQUIRED_CODE = "personal_key_required"
# Passes every chat turn runs (mechanics and narration).
TURN_PASS_PROVIDER_FIELDS = ("small_model_provider", "complex_model_provider")


def turn_providers(llm_settings: Optional[dict[str, Any]]) -> list[str]:
    settings = llm_settings or {}
    return [str(settings.get(field) or "openai").lower() for field in TURN_PASS_PROVIDER_FIELDS]


def ensure_turn_providers_available(user: User) -> None:
    """Raise HTTP 403 (``detail.code = personal_key_required``) when a pass is blocked."""
    blocked = unavailable_providers(user.encrypted_api_keys, turn_providers(user.llm_settings))
    if not blocked:
        return
    provider = blocked[0]
    reason = key_source(user.encrypted_api_keys, provider)
    reason = reason if reason in (SOURCE_MISSING, SOURCE_DISABLED) else SOURCE_MISSING
    raise HTTPException(
        status_code=403,
        detail={
            "code": PERSONAL_KEY_REQUIRED_CODE,
            "provider": provider,
            "reason": reason,
            "message": personal_key_message(provider, reason),
        },
    )


def missing_turn_keys(user: User) -> list[dict[str, str]]:
    """Blocked providers of the chat passes, for the portal banner: ``[{id, reason, message}]``."""
    keys = user.encrypted_api_keys
    return [
        {
            "id": provider,
            "reason": key_source(keys, provider),
            "message": personal_key_message(provider, key_source(keys, provider)),
        }
        for provider in unavailable_providers(keys, turn_providers(user.llm_settings))
    ]
