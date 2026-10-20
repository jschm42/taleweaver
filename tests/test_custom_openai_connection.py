"""The connection action tests the selected JSON capability, not just text generation."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.core import custom_openai


@pytest.mark.asyncio
async def test_connection_uses_structured_validation():
    router = SimpleNamespace(
        aexecute_complex_task=AsyncMock(
            return_value=custom_openai.ConnectionTestResult(message="ok")
        )
    )
    assert await custom_openai.test_connection(router, "vendor/model") == "ok"
    request = router.aexecute_complex_task.call_args.kwargs
    assert request["model"] == "vendor/model"
    assert request["response_model"] is custom_openai.ConnectionTestResult


@pytest.mark.asyncio
async def test_connection_rejects_schema_failure():
    router = SimpleNamespace(
        aexecute_complex_task=AsyncMock(side_effect=ValueError("Invalid JSON schema"))
    )
    with pytest.raises(ValueError, match="Invalid JSON schema"):
        await custom_openai.test_connection(router, "vendor/model")


@pytest.mark.asyncio
async def test_api_connection_uses_structured_path(auth_client, monkeypatch):
    from backend.api.routes import config_api

    router = SimpleNamespace(
        aexecute_complex_task=AsyncMock(
            return_value=custom_openai.ConnectionTestResult(message="ready")
        )
    )
    monkeypatch.setattr(config_api, "GameMasterLLM", lambda *args, **kwargs: router)
    response = await auth_client.post(
        "/api/settings/test-llm", json={"provider": "custom_openai", "model": "vendor/model"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["message"] == "ready"
    router.aexecute_complex_task.assert_awaited_once()
