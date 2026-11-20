"""OpenRouter route reports of the admin model test (backend/core/openrouter_route_report.py)."""

from types import SimpleNamespace

from backend.core.openrouter_route_report import (
    FALLBACK_UNRESTRICTED,
    route_payload,
    route_report,
)

_PINNED = {"extra_body": {"provider": {"order": ["Groq"], "allow_fallbacks": False}}}


def test_served_by_the_pinned_provider_is_a_plain_note():
    # Act
    report = route_report(_PINNED, SimpleNamespace(provider="Groq"))

    # Assert
    assert report.note() == "Served by Groq via OpenRouter."


def test_other_provider_without_fallback_is_reported():
    # Act
    report = route_report(_PINNED, SimpleNamespace(provider="DeepInfra"))

    # Assert
    assert "Requested provider 'Groq', but OpenRouter used DeepInfra" in report.note()


def test_fallback_names_the_provider_and_the_fix():
    # Act
    report = route_report(_PINNED, SimpleNamespace(provider="Google"), FALLBACK_UNRESTRICTED)

    # Assert
    note = report.note()
    assert "'Groq' does not serve this model" in note
    assert "fell back to Google" in note


def test_route_payload_prefers_the_fallback_over_the_last_call():
    # Arrange
    ok = route_report(_PINNED, SimpleNamespace(provider="Groq"))
    fell_back = route_report(_PINNED, SimpleNamespace(provider="Google"), FALLBACK_UNRESTRICTED)
    gm = SimpleNamespace(last_route=ok, route_fallback=fell_back)

    # Act
    payload = route_payload(gm)

    # Assert
    assert payload["fallback"] == FALLBACK_UNRESTRICTED
    assert payload["served"] == "Google"


def test_no_openrouter_call_gives_no_routing_block():
    assert route_payload(SimpleNamespace()) is None
