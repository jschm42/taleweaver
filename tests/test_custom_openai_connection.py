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
    assert response.json()["message"].startswith("ready")
    assert response.json()["speed"]["rating"] in {"fast", "ok", "slow"}
    router.aexecute_complex_task.assert_awaited_once()


@pytest.mark.asyncio
async def test_api_connection_wizard_llm_story_uses_prose_path(auth_client, monkeypatch):
    from backend.api.routes import config_api

    captured: dict = {}
    router = SimpleNamespace(
        aexecute_simple_task=AsyncMock(return_value="TaleWeaver connection test successful!"),
        aexecute_complex_task=AsyncMock(),
    )

    def _fake_router(*args, **kwargs):
        captured["kwargs"] = kwargs
        return router

    monkeypatch.setattr(config_api, "GameMasterLLM", _fake_router)
    response = await auth_client.post(
        "/api/settings/test-llm",
        json={
            "provider": "custom_openai",
            "model": "vendor/model",
            "pass_key": "wizard-llm-story",
            "custom_openai_url": "http://127.0.0.1:8080/v1",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["message"].startswith("TaleWeaver connection test successful!")
    assert response.json()["speed"]["rating"] in {"fast", "ok", "slow"}
    assert captured["kwargs"]["model_category"] == "complex"
    router.aexecute_simple_task.assert_awaited_once()
    router.aexecute_complex_task.assert_not_awaited()
