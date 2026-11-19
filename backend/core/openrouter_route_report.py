"""Which OpenRouter provider actually served a request, and whether the configured one was dropped.

A pass can pin OpenRouter providers (`<pass>_openrouter_provider`, e.g. "Groq"). When none of them
serves the model, `GameMasterLLM` retries with the providers OpenRouter offers or without any
restriction, so the call still succeeds, but on another provider. This module records that, so
the admin model test can show it instead of hiding it in the server log.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# Fallback kinds set by GameMasterLLM's OpenRouter retry branches.
FALLBACK_AVAILABLE_ORDER = "available_providers"
FALLBACK_UNRESTRICTED = "unrestricted"


@dataclass
class RouteReport:
    requested: list[str] = field(default_factory=list)
    served: str = ""
    fallback: str = ""

    def note(self) -> str:
        """One line for the test result; empty when nothing is worth saying."""
        wanted = ", ".join(self.requested)
        served = self.served or "an unknown provider"
        if self.fallback:
            return (
                f"OpenRouter provider '{wanted}' does not serve this model; the request fell back to "
                f"{served}. Pick a model that '{wanted}' hosts, or clear the provider field."
            )
        if self.requested and self.served and not _matches(self.served, self.requested):
            return f"Requested provider '{wanted}', but OpenRouter used {served}."
        if self.served:
            return f"Served by {served} via OpenRouter."
        return ""

    def payload(self) -> dict[str, Any]:
        return {**asdict(self), "note": self.note()}


def _matches(served: str, requested: list[str]) -> bool:
    key = served.strip().lower()
    return any(key == wanted.strip().lower() for wanted in requested)


def requested_providers(kwargs: dict) -> list[str]:
    """The provider order sent with the original request (empty without one)."""
    provider_block = (kwargs.get("extra_body") or {}).get("provider") or {}
    return [str(p) for p in provider_block.get("order") or []]


def served_provider(response: Any) -> str:
    """OpenRouter's `provider` response field; LiteLLM keeps unknown fields as attributes."""
    value = getattr(response, "provider", None)
    return value if isinstance(value, str) else ""


def route_report(kwargs: dict, response: Any, fallback: str = "") -> RouteReport:
    return RouteReport(requested_providers(kwargs), served_provider(response), fallback)


def route_payload(gm: Any) -> dict[str, Any] | None:
    """The `routing` block of an admin test response: the first fallback, else the last call."""
    report = getattr(gm, "route_fallback", None) or getattr(gm, "last_route", None)
    return report.payload() if report else None
