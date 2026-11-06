"""Who pays for a provider: server keys, personal keys and the per-provider key policy.

The admin sets a policy per provider (``ServerSettings.api_key_policy``) and may override it
per user (``User.api_key_policy_overrides``):

* ``server`` (default): the server key (env or stored) is used; players cannot enter one.
* ``user_optional``: the player's personal key if stored, else the server key.
* ``user_required``: only the player's personal key; without it the provider is unavailable.
* ``disabled``: the provider is unavailable.

``build_effective_keys`` turns this into the key dict a user works with. The dict remembers
the source of every provider (``EffectiveKeys.sources``), so ``resolve_api_key`` can apply the
policy even where only the dict travels (image generation, TTS). An env key counts as a server
key: it never replaces a personal key and is never used for ``user_required`` / ``disabled``.
"""

import logging
from collections.abc import Mapping
from typing import Any, Optional

from backend.core.config import settings
from backend.core.models_config import IMAGE_PROVIDERS, LLM_PROVIDERS, TTS_PROVIDERS
from backend.core.security import encryption_util

logger = logging.getLogger(__name__)

POLICY_SERVER = "server"
POLICY_USER_OPTIONAL = "user_optional"
POLICY_USER_REQUIRED = "user_required"
POLICY_DISABLED = "disabled"
KEY_POLICIES: tuple[str, ...] = (
    POLICY_SERVER,
    POLICY_USER_OPTIONAL,
    POLICY_USER_REQUIRED,
    POLICY_DISABLED,
)
# Policies under which a player may store a personal key.
PERSONAL_KEY_POLICIES = frozenset((POLICY_USER_OPTIONAL, POLICY_USER_REQUIRED))

SOURCE_SERVER = "server"
SOURCE_PERSONAL = "personal"
SOURCE_MISSING = "missing"
SOURCE_DISABLED = "disabled"

# Local providers never use a key, so they are always server-provided.
KEYLESS_PROVIDERS = frozenset(("ollama", "stable_diffusion", "comfyui", "qwen"))
MAX_API_KEY_LENGTH = 512


def key_providers() -> list[dict[str, str]]:
    """Providers that take an API key: ``[{"id", "name"}]``, LLM first, without duplicates."""
    seen: dict[str, str] = {}
    for provider in (*LLM_PROVIDERS, *IMAGE_PROVIDERS, *TTS_PROVIDERS):
        if provider["id"] not in KEYLESS_PROVIDERS:
            seen.setdefault(provider["id"], provider["name"])
    return [{"id": pid, "name": name} for pid, name in seen.items()]


KEY_PROVIDER_IDS = frozenset(p["id"] for p in key_providers())


class PersonalKeyRequiredError(ValueError):
    """A provider is unavailable for this user: no personal key, or disabled by the admin."""

    def __init__(self, provider: str, reason: str) -> None:
        self.provider = provider
        self.reason = reason
        super().__init__(personal_key_message(provider, reason))


class EffectiveKeys(dict):
    """Encrypted keys of one user, plus the source of every provider (``sources``)."""

    def __init__(self, keys: Optional[Mapping[str, str]] = None, sources: Optional[dict] = None):
        super().__init__(keys or {})
        self.sources: dict[str, str] = dict(sources or {})


def provider_name(provider: str) -> str:
    names = {p["id"]: p["name"] for p in key_providers()}
    return names.get(provider, provider)


def personal_key_message(provider: str, reason: str) -> str:
    """User-facing explanation why a provider cannot be used."""
    name = provider_name(provider)
    if reason == SOURCE_DISABLED:
        return f"{name} is disabled on this server. Ask the administrator to enable it."
    return (
        f"This server requires your own {name} API key. "
        "Add it in your profile under Account → API keys."
    )


def normalize_policy_map(raw: Any) -> dict[str, str]:
    """Keep known providers with valid policies; ``server`` entries are implied and dropped."""
    if not isinstance(raw, Mapping):
        return {}
    return {
        str(provider).lower(): policy
        for provider, policy in raw.items()
        if str(provider).lower() in KEY_PROVIDER_IDS
        and policy in KEY_POLICIES
        and policy != POLICY_SERVER
    }


def resolve_policy(
    provider: str,
    server_policy: Optional[Mapping[str, str]],
    overrides: Optional[Mapping[str, str]] = None,
) -> str:
    """User override → server policy → ``server``. Keyless providers are always ``server``."""
    provider = (provider or "").lower()
    if provider not in KEY_PROVIDER_IDS:
        return POLICY_SERVER
    for source in (overrides, server_policy):
        policy = (source or {}).get(provider)
        if policy in KEY_POLICIES:
            return policy
    return POLICY_SERVER


def _provider_source(policy: str, has_personal: bool) -> str:
    if policy == POLICY_DISABLED:
        return SOURCE_DISABLED
    if policy in PERSONAL_KEY_POLICIES and has_personal:
        return SOURCE_PERSONAL
    if policy == POLICY_USER_REQUIRED:
        return SOURCE_MISSING
    return SOURCE_SERVER


def build_effective_keys(
    server_keys: Optional[Mapping[str, str]],
    server_policy: Optional[Mapping[str, str]],
    personal_keys: Optional[Mapping[str, str]] = None,
    overrides: Optional[Mapping[str, str]] = None,
) -> EffectiveKeys:
    """The encrypted keys a user works with, following the key policy."""
    keys: dict[str, str] = {}
    sources: dict[str, str] = {}
    personal_keys = personal_keys or {}
    for provider in KEY_PROVIDER_IDS:
        policy = resolve_policy(provider, server_policy, overrides)
        source = _provider_source(policy, bool(personal_keys.get(provider)))
        sources[provider] = source
        if source == SOURCE_PERSONAL:
            keys[provider] = personal_keys[provider]
        elif source == SOURCE_SERVER and (server_keys or {}).get(provider):
            keys[provider] = server_keys[provider]
    return EffectiveKeys(keys, sources)


def key_source(keys: Optional[Mapping[str, str]], provider: str) -> str:
    """Where ``provider``'s key comes from; plain dicts (server row, tests) mean ``server``."""
    sources = getattr(keys, "sources", None) or {}
    return sources.get((provider or "").lower(), SOURCE_SERVER)


def is_blocked(keys: Optional[Mapping[str, str]], provider: str) -> bool:
    """Whether ``provider`` is unavailable (personal key missing, or disabled)."""
    return key_source(keys, provider) in (SOURCE_MISSING, SOURCE_DISABLED)


def _decrypt(encrypted: Optional[str], provider: str) -> Optional[str]:
    if not encrypted:
        return None
    try:
        return encryption_util.decrypt_key(encrypted)
    except (ValueError, TypeError, KeyError):
        logger.error("Failed to decrypt API key for provider '%s'", provider)
        return None


def resolve_api_key(keys: Optional[Mapping[str, str]], provider: str) -> Optional[str]:
    """Plain API key for ``provider``, following the policy recorded in ``keys``.

    Raises ``PersonalKeyRequiredError`` when the provider is unavailable for this user.
    """
    provider = (provider or "").lower()
    source = key_source(keys, provider)
    if source in (SOURCE_MISSING, SOURCE_DISABLED):
        raise PersonalKeyRequiredError(provider, source)
    if source == SOURCE_PERSONAL:
        return _decrypt((keys or {}).get(provider), provider)
    env_key = settings.get_env_api_key(provider)
    if env_key:
        return env_key
    return _decrypt((keys or {}).get(provider), provider)


def has_api_key(keys: Optional[Mapping[str, str]], provider: str) -> bool:
    """Whether ``provider`` can be used with ``keys`` (no decryption)."""
    provider = (provider or "").lower()
    source = key_source(keys, provider)
    if source in (SOURCE_MISSING, SOURCE_DISABLED):
        return False
    if source == SOURCE_PERSONAL:
        return True
    return bool(settings.get_env_api_key(provider)) or bool((keys or {}).get(provider))


def unavailable_providers(keys: Optional[Mapping[str, str]], providers: list[str]) -> list[str]:
    """Those of ``providers`` the user cannot use (missing personal key or disabled)."""
    blocked = (SOURCE_MISSING, SOURCE_DISABLED)
    return [p for p in dict.fromkeys(providers) if p and key_source(keys, p) in blocked]
