"""Safe diagnostics for failures before and during a custom endpoint test."""

from fastapi import HTTPException

from backend.core.error_diagnostics import diagnose_provider_error

_URL_ERRORS = {
    "URL must be a non-empty string.": (
        "No OpenAI-compatible Base URL is saved. Enter the Base URL ending in /v1, "
        "save endpoint settings, then test again."
    ),
    "Base URL must end in /v1 (for example http://127.0.0.1:8080/v1).": (
        "The saved OpenAI-compatible Base URL must end in /v1. "
        "Correct it and save endpoint settings before testing."
    ),
    "URL scheme must be http or https.": (
        "The saved Base URL must start with http:// or https:// and end in /v1."
    ),
    "URL must include a hostname.": "The saved Base URL is missing its hostname.",
    "Could not resolve hostname.": "Could not resolve the saved Base URL's hostname.",
    "Could not resolve endpoint hostname.": "Could not resolve the saved Base URL's hostname.",
    "URL points to a private/loopback address. Set ALLOW_PRIVATE_NETWORK_MODELS=true to allow local providers.": (
        "The saved Base URL points to a local or private address. "
        "For an intended local provider, set ALLOW_PRIVATE_NETWORK_MODELS=true "
        "in the backend environment and restart it."
    ),
    "Base URL must not contain credentials, a query, or a fragment.": (
        "Remove credentials, query parameters and fragments from the Base URL. "
        "Store an optional API key in Provider Vault."
    ),
    "Endpoint port must be between 1 and 65535.": "The saved Base URL has an invalid port.",
    "Metadata, link-local, reserved and multicast endpoints are forbidden.": (
        "The saved Base URL is blocked by the endpoint security policy."
    ),
}


def connection_test_diagnostic(exc: Exception, *, stage: str, model: str) -> str:
    """Use fixed messages only: exceptions can include credentials and model output."""
    if isinstance(exc, HTTPException) and exc.status_code == 400:
        detail = exc.detail if isinstance(exc.detail, str) else ""
        if detail in _URL_ERRORS:
            return "No generation request was sent. " + _URL_ERRORS[detail]
    if stage == "configuration":
        return (
            "OpenAI-compatible configuration failed before sending a generation request. "
            "Check the saved Base URL (ending in /v1), optional API key and backend log. "
            "Test Model uses saved endpoint settings."
        )
    text = str(exc)
    if isinstance(exc, ValueError) and text.startswith(
        (
            "Failed to parse LLM response as JSON.",
            "LLM returned JSON that does not match expected schema",
        )
    ):
        return (
            "The server responded, but the model did not return the JSON required by this test. "
            "Check Structured output support; try Prompt only for widest compatibility. "
            "For structured tasks, use a model that reliably follows JSON instructions."
        )
    if isinstance(exc, ValueError) and text.startswith("No content returned from LLM"):
        return "The server returned an empty model response. Check the server log and generation settings."
    if getattr(exc, "status_code", None) == 400:
        return (
            "The API rejected the generation request (HTTP 400). Check the model ID, "
            "output token budget and Structured output support. Try Prompt only if the "
            "server does not support response_format. See the backend log for the rejected parameter."
        )
    return diagnose_provider_error(exc, provider="custom_openai", model=model, context="llm")
