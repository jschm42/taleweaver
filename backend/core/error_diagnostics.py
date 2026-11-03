"""Centralized error diagnostics for AI providers (LLM, Vision, TTS).

Translates technical exceptions (LiteLLM, Fernet, HTTP errors, connection failures)
into actionable, human-friendly error messages for the UI.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _check_encryption(lower: str, prov: str, **_) -> str | None:
    if any(
        kw in lower
        for kw in (
            "encryption_key",
            "invalidtoken",
            "invalidsignature",
            "signature did not match digest",
            "failed to decrypt",
        )
    ):
        return (
            f"Encryption key mismatch: Could not decrypt the saved API key for {prov}. "
            "The ENCRYPTION_KEY in your .env file may have changed. "
            "Please re-enter and save your API key in Settings."
        )
    return None


def _check_missing_key(lower: str, prov: str, **_) -> str | None:
    if any(
        kw in lower
        for kw in (
            "no api key configured",
            "api key not configured",
            "no api key found",
        )
    ):
        return f"No API key configured for {prov}. Please set your API key in Settings."
    return None


def _check_auth(lower: str, prov: str, exc: Exception, **_) -> str | None:
    auth_keywords = (
        "invalid authentication",
        "authenticationerror",
        "invalid_api_key",
        "incorrect api key",
        "unauthorized",
        "invalid x-api-key",
        "auth_subrequest_error",
        "status_code: 401",
        "code 401",
        "401 unauthorized",
    )
    if any(kw in lower for kw in auth_keywords) or getattr(exc, "status_code", None) == 401:
        return (
            f"Authentication failed for {prov} (401): "
            "The API key is invalid, inactive, or expired. Please check your API key in Settings."
        )
    return None


def _check_model_not_found(
    lower: str, prov: str, exc: Exception, model: str = "", **_
) -> str | None:
    not_found_keywords = (
        "notfounderror",
        "no endpoints found",
        "model not found",
        "does not exist",
        "unknown model",
        "model_not_found",
        "status_code: 404",
        "code 404",
        "404 not found",
    )
    if any(kw in lower for kw in not_found_keywords) or getattr(exc, "status_code", None) == 404:
        model_part = f" '{model}'" if model else ""
        return (
            f"Model{model_part} not found on {prov} (404). "
            "Please check the model ID or choose a different model in Settings."
        )
    return None


def _check_rate_limit(lower: str, prov: str, exc: Exception, model: str = "", **_) -> str | None:
    rate_keywords = (
        "ratelimiterror",
        "rate limit",
        "too many requests",
        "quota exceeded",
        "insufficient_quota",
        "credit balance",
        "out of credits",
        "temporarily rate-limited",
        "upstream_provider_shared_pool",
        "status_code: 429",
        "code 429",
        "429 too many requests",
    )
    if any(kw in lower for kw in rate_keywords) or getattr(exc, "status_code", None) == 429:
        if "temporarily rate-limited" in lower or "upstream_provider_shared_pool" in lower:
            model_part = f" '{model}'" if model else ""
            return (
                f"Model{model_part} is temporarily rate-limited by its upstream provider on {prov} (429). "
                "Please retry in a moment or select another model."
            )
        return (
            f"Quota or rate limit exceeded for {prov} (429). "
            "Please verify your account credits/balance or try again later."
        )
    return None


def _check_connection(lower: str, prov: str, **_) -> str | None:
    conn_keywords = (
        "connection refused",
        "connecterror",
        "connectionerror",
        "failed to connect",
        "cannot connect to host",
        "name resolution failure",
        "connection reset",
    )
    if any(kw in lower for kw in conn_keywords):
        return (
            f"Connection failed: Could not connect to {prov} server. "
            "Please verify the service is running, reachable, and the URL is configured correctly."
        )
    return None


def _check_timeout(lower: str, prov: str, **_) -> str | None:
    timeout_keywords = (
        "timeouterror",
        "timeout",
        "timed out",
        "read timeout",
        "connect timeout",
        "request timeout",
        "deadline exceeded",
        "status_code: 504",
    )
    if any(kw in lower for kw in timeout_keywords):
        return (
            f"Connection test failed: Request to {prov} timed out. "
            "The model took too long to respond. Please try again."
        )
    return None


def _check_context_length(lower: str, prov: str, **_) -> str | None:
    context_keywords = (
        "maximum context length",
        "context length exceeded",
        "context window",
        "prompt is too long",
        "too many tokens",
    )
    if any(kw in lower for kw in context_keywords):
        return (
            f"Context length exceeded on {prov}. "
            "The request or thinking token budget exceeds the maximum allowed token limit."
        )
    return None


_DIAGNOSTIC_CHECKS = (
    _check_encryption,
    _check_missing_key,
    _check_auth,
    _check_model_not_found,
    _check_rate_limit,
    _check_connection,
    _check_timeout,
    _check_context_length,
)


def diagnose_provider_error(
    exc: Exception,
    provider: str = "",
    model: str = "",
    context: str = "llm",
) -> str:
    """Analyze an exception from an AI provider and return a clear, user-friendly diagnostic message."""
    _ = context
    lower_text = str(exc or "").lower()
    prov_display = provider.capitalize() if provider else "Provider"

    for check in _DIAGNOSTIC_CHECKS:
        msg = check(lower=lower_text, prov=prov_display, exc=exc, model=model)
        if msg:
            return msg

    return (
        f"Connection test failed for {prov_display}. "
        "Please check your provider configuration, credentials, and server logs for details."
    )
