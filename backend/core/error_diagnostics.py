"""
Centralized error diagnostics for AI providers (LLM, Vision, TTS).

Translates technical exceptions (LiteLLM, Fernet, HTTP errors, connection failures)
into actionable, human-friendly error messages for the UI.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def diagnose_provider_error(
    exc: Exception,
    provider: str = "",
    model: str = "",
    context: str = "llm",
) -> str:
    """Analyze an exception from an AI provider and return a clear, user-friendly diagnostic message."""
    err_text = str(exc or "").strip()
    lower_text = err_text.lower()
    prov_display = provider.capitalize() if provider else "Provider"

    # 1. ENCRYPTION_KEY / Decryption Errors
    if any(
        kw in lower_text
        for kw in (
            "encryption_key",
            "invalidtoken",
            "invalidsignature",
            "signature did not match digest",
            "failed to decrypt",
        )
    ):
        return (
            f"Encryption key mismatch: Could not decrypt the saved API key for {prov_display}. "
            "The ENCRYPTION_KEY in your .env file may have changed. "
            "Please re-enter and save your API key in Settings."
        )

    # 2. Missing API Key
    if any(
        kw in lower_text
        for kw in (
            "no api key configured",
            "api key not configured",
            "no api key found",
        )
    ):
        return (
            f"No API key configured for {prov_display}. "
            "Please set your API key in Settings."
        )

    # 3. Authentication / Invalid API Key (401)
    if any(
        kw in lower_text
        for kw in (
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
    ) or getattr(exc, "status_code", None) == 401:
        return (
            f"Authentication failed for {prov_display} (401): "
            "The API key is invalid, inactive, or expired. Please check your API key in Settings."
        )

    # 4. Model Not Found / Unsupported Model / No Endpoints (404)
    if any(
        kw in lower_text
        for kw in (
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
    ) or getattr(exc, "status_code", None) == 404:
        model_part = f" '{model}'" if model else ""
        return (
            f"Model{model_part} not found on {prov_display} (404). "
            "Please check the model ID or choose a different model in Settings."
        )

    # 5. Rate Limit / Quota Exceeded / Out of Credits (429)
    if any(
        kw in lower_text
        for kw in (
            "ratelimiterror",
            "rate limit",
            "too many requests",
            "quota exceeded",
            "insufficient_quota",
            "credit balance",
            "out of credits",
            "status_code: 429",
            "code 429",
            "429 too many requests",
        )
    ) or getattr(exc, "status_code", None) == 429:
        return (
            f"Quota or rate limit exceeded for {prov_display} (429). "
            "Please verify your account credits/balance or try again later."
        )

    # 6. Connection Refused / Service Offline (Ollama, Stable Diffusion, local URLs)
    if any(
        kw in lower_text
        for kw in (
            "connection refused",
            "connecterror",
            "connectionerror",
            "failed to connect",
            "cannot connect to host",
            "name resolution failure",
            "connection reset",
        )
    ):
        return (
            f"Connection failed: Could not connect to {prov_display} server. "
            "Please verify the service is running, reachable, and the URL is configured correctly."
        )

    # 7. Timeout (504 / ReadTimeout)
    if any(
        kw in lower_text
        for kw in (
            "timeouterror",
            "timeout",
            "timed out",
            "read timeout",
            "connect timeout",
            "request timeout",
            "deadline exceeded",
            "status_code: 504",
        )
    ):
        return (
            f"Connection test failed: Request to {prov_display} timed out. "
            "The model took too long to respond. Please try again."
        )

    # 8. Token / Context Limit (400)
    if any(
        kw in lower_text
        for kw in (
            "maximum context length",
            "context length exceeded",
            "context window",
            "prompt is too long",
            "too many tokens",
        )
    ):
        return (
            f"Context length exceeded on {prov_display}. "
            "The request or thinking token budget exceeds the maximum allowed token limit."
        )

    # 9. Clean provider error message if available and informative
    if hasattr(exc, "message") and exc.message and isinstance(exc.message, str):
        msg = exc.message.strip()
        if len(msg) > 5 and not msg.startswith("{"):
            return f"Connection test failed for {prov_display}: {msg}"

    # Fallback with raw exception message if reasonably short and readable
    if err_text and len(err_text) < 200 and not err_text.startswith("{") and not "traceback" in lower_text:
        return f"Connection test failed for {prov_display}: {err_text}"

    return f"Connection test failed for {prov_display}. Please check provider settings and server logs."
