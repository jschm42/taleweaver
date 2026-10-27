"""Connection tests distinguish local configuration from model output failures."""

import ipaddress
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from backend.api.routes import config_api
from backend.core import custom_openai
from backend.core.custom_openai_diagnostics import connection_test_diagnostic
from backend.models.user import User

SECRET = "private-example-token-do-not-display"


@pytest.mark.parametrize(
    "detail,expected",
    [
        ("URL must be a non-empty string.", "No OpenAI-compatible Base URL is saved"),
        (
            "Base URL must end in /v1 (for example http://127.0.0.1:8080/v1).",
            "must end in /v1",
        ),
        (
            "URL points to a private/loopback address. Set ALLOW_PRIVATE_NETWORK_MODELS=true to allow local providers.",
            "ALLOW_PRIVATE_NETWORK_MODELS=true",
        ),
        ("Could not resolve hostname.", "Could not resolve"),
    ],
)
def test_preflight_configuration_messages(detail, expected):
    message = connection_test_diagnostic(
        HTTPException(400, detail), stage="configuration", model="local-model"
    )
    assert "No generation request was sent" in message
    assert expected in message


@pytest.mark.parametrize(
    "exc,stage",
    [
        (HTTPException(400, SECRET), "configuration"),
        (HTTPException(400, {"unsafe": SECRET}), "configuration"),
        (RuntimeError(SECRET), "configuration"),
        (RuntimeError(SECRET), "request_or_response"),
    ],
)
def test_unknown_exceptions_do_not_expose_raw_details(exc, stage):
    message = connection_test_diagnostic(exc, stage=stage, model="local-model")
    assert SECRET not in message


@pytest.mark.parametrize(
    "error",
    [
        "Failed to parse LLM response as JSON. Preview: " + SECRET,
        "LLM returned JSON that does not match expected schema Result. Preview: " + SECRET,
    ],
)
def test_bad_json_is_not_reported_as_no_connection(error):
    message = connection_test_diagnostic(
        ValueError(error), stage="request_or_response", model="local-model"
    )
    assert "server responded" in message
    assert "JSON" in message
    assert "No generation request" not in message
    assert SECRET not in message


def test_http_400_identifies_api_rejection_without_echoing_body():
    message = connection_test_diagnostic(
        HTTPException(400, SECRET), stage="request_or_response", model="local-model"
    )
    assert "API rejected" in message
    assert "HTTP 400" in message
    assert "No generation request" not in message
    assert SECRET not in message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base,expected",
    [("", "No OpenAI-compatible Base URL is saved"), ("https://example.test", "must end in /v1")],
)
async def test_real_router_validation_prevents_generation(auth_client, monkeypatch, base, expected):
    owner = User(
        username="diagnostic-owner",
        llm_settings={"custom_openai_url": base},
        encrypted_api_keys={},
    )
    original_settings = owner.llm_settings
    monkeypatch.setattr(config_api, "_resolve_global_settings_owner", AsyncMock(return_value=owner))
    addresses = [ipaddress.ip_address("8.8.8.8")]
    monkeypatch.setattr("backend.utils.path_security._resolve_host_ips", lambda _: addresses)
    monkeypatch.setattr(custom_openai, "_resolve_host_ips", lambda _: addresses)
    generate = AsyncMock(side_effect=AssertionError("No generation is allowed during preflight"))
    monkeypatch.setattr(custom_openai, "test_connection", generate)

    response = await auth_client.post(
        "/api/settings/test-llm",
        json={"provider": "custom_openai", "model": "koboldcpp/local-model", "role": "generator"},
    )

    assert response.json()["status"] == "error"
    assert expected in response.json()["message"]
    assert "No generation request was sent" in response.json()["message"]
    generate.assert_not_awaited()
    assert owner.llm_settings is original_settings


@pytest.mark.asyncio
async def test_api_reports_json_failure_after_generation(auth_client, monkeypatch):
    router = SimpleNamespace(
        aexecute_complex_task=AsyncMock(
            side_effect=ValueError("Failed to parse LLM response as JSON. Preview: " + SECRET)
        )
    )
    monkeypatch.setattr(config_api, "GameMasterLLM", lambda *args, **kwargs: router)

    response = await auth_client.post(
        "/api/settings/test-llm", json={"provider": "custom_openai", "model": "local-model"}
    )

    router.aexecute_complex_task.assert_awaited_once()
    assert response.json()["status"] == "error"
    assert "server responded" in response.json()["message"]
    assert SECRET not in response.text
