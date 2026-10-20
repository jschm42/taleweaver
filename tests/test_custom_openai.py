"""Custom endpoints stay explicit, optional-auth, and isolated from cloud routing."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException
from litellm import APIError
from pydantic import BaseModel

from backend.api.routes import config_api
from backend.core import custom_openai
from backend.core.config import settings
from backend.core.llm_provider_config import normalize_model
from backend.core.llm_router import GameMasterLLM
from backend.core.security import encryption_util
from backend.models.user import User

BASE = "http://127.0.0.1:8080/v1"


@pytest.mark.parametrize("legacy", [None, {"small_model": "existing-model"}])
def test_extracted_normalizer_adds_custom_defaults_to_existing_settings(legacy):
    normalized = config_api._normalize_llm_settings(legacy)
    assert normalized["custom_openai_url"] == ""
    assert normalized["custom_openai_timeout"] == 300
    assert normalized["custom_openai_response_format"] == "prompt"
    if legacy:
        assert normalized["complex_model"] == "existing-model"


def test_custom_settings_preserve_upstream_personality_and_model_fallbacks():
    normalized = config_api._normalize_llm_settings(
        {
            "small_model": "vendor/model",
            "small_model_provider": "custom_openai",
            "custom_openai_url": BASE,
            "custom_openai_timeout": 600,
            "custom_openai_response_format": "json_schema",
            "play_agent_personality": "Bürokrat",
            "play_agent_custom_personality": "Review the evidence.",
        }
    )
    assert normalized["custom_openai_timeout"] == 600
    assert normalized["custom_openai_response_format"] == "json_schema"
    assert normalized["complex_model"] == "vendor/model"
    assert normalized["generator_model_provider"] == "custom_openai"
    assert normalized["play_agent_personality"] == "bureaucrat"
    assert normalized["play_agent_custom_personality"] == "Review the evidence."


@pytest.fixture
def local_policy(monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_PRIVATE_NETWORK_MODELS", True)
    monkeypatch.setattr(
        settings,
        "__pydantic_fields_set__",
        settings.model_fields_set | {"ALLOW_PRIVATE_NETWORK_MODELS"},
    )


def make_router(key=None):
    keys = {"custom_openai": encryption_util.encrypt_key(key)} if key else {}
    return GameMasterLLM(
        User(username="custom", llm_settings={"custom_openai_url": BASE}, encrypted_api_keys=keys),
        provider="custom_openai",
    )


@pytest.mark.parametrize(
    "model", ["local-model", "vendor/model", "openai/model", "openrouter/vendor/model"]
)
def test_adapter_preserves_wire_model(model):
    import litellm

    normalized = normalize_model("custom_openai", model)
    resolved, provider, _, base = litellm.get_llm_provider(
        model=normalized, custom_llm_provider="openai", api_base=BASE
    )
    assert resolved == model
    assert provider == "openai"
    assert base == BASE


@pytest.mark.parametrize("key", [None, "sk-or-v1-fake-custom-token"])
def test_sync_and_structured_routing(monkeypatch, local_policy, key):
    router = make_router(key)
    captured = {}

    def completion(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))], model_dump=lambda: {}
        )

    monkeypatch.setattr(router._get_litellm(), "completion", completion)
    assert router.execute_simple_task("sys", "hello", "vendor/model") == "ok"
    assert captured["model"] == "openai/vendor/model"
    assert captured["api_base"] == BASE
    assert captured["custom_llm_provider"] == "openai"
    assert captured["api_key"] == (key or "local-no-key")
    assert not captured["client"]._client.follow_redirects
    assert "extra_body" not in captured

    class Answer(BaseModel):
        value: int

    request = router._build_structured_request("sys", "hello", Answer, "vendor/model")
    assert "response_format" not in request.kwargs
    assert request.json_mode
    assert "SCHEMA:" in request.system_prompt
    assert request.kwargs["api_base"] == BASE


@pytest.mark.asyncio
async def test_async_and_streaming_routing(monkeypatch, local_policy):
    router = make_router()
    captured = []

    async def chunks():
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(delta=SimpleNamespace(content="hello", reasoning_content=None))
            ]
        )

    async def completion(**kwargs):
        captured.append(kwargs)
        if kwargs.get("stream"):
            return chunks()
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))], model_dump=lambda: {}
        )

    monkeypatch.setattr(router._get_litellm(), "acompletion", completion)
    assert await router.aexecute_simple_task("sys", "hello", "vendor/model") == "ok"
    stream = await router.stream_simple_task("sys", "hello", "vendor/model")
    result = [chunk async for chunk in stream]
    assert "hello" in "".join(chunk.choices[0].delta.content or "" for chunk in result)
    assert len(captured) == 2
    assert all(call["api_base"] == BASE for call in captured)
    assert all(call["custom_llm_provider"] == "openai" for call in captured)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://169.254.169.254/v1",
        "http://0.0.0.0/v1",
        "http://user:secret@127.0.0.1/v1",
        BASE + "?token=x",
        BASE + "#fragment",
    ],
)
def test_unsafe_urls_rejected(local_policy, url):
    with pytest.raises(HTTPException):
        custom_openai.validate_custom_url(url)


def test_private_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_PRIVATE_NETWORK_MODELS", False)
    with pytest.raises(HTTPException, match="private/loopback"):
        custom_openai.validate_custom_url(BASE)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 401, 404, 302])
@pytest.mark.parametrize("key", [None, "protected-key"])
async def test_discovery(monkeypatch, local_policy, status, key):
    real_client = httpx.AsyncClient
    seen = []

    def respond(request):
        seen.append(request)
        return httpx.Response(
            status,
            json={"data": [{"id": "vendor/model"}]},
            headers={"location": "http://169.254.169.254/v1/models"},
        )

    monkeypatch.setattr(
        custom_openai.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    if status == 200:
        assert await custom_openai.discover_models(BASE, key) == ["vendor/model"]
    else:
        with pytest.raises(HTTPException) as error:
            await custom_openai.discover_models(BASE, key)
        assert error.value.status_code == 502
    assert len(seen) == 1
    assert seen[0].headers.get("authorization") == (f"Bearer {key}" if key else None)
    assert str(seen[0].url) == BASE + "/models"


@pytest.mark.asyncio
async def test_discovery_timeout(monkeypatch, local_policy):
    real_client = httpx.AsyncClient

    def timeout(request):
        raise httpx.ReadTimeout("timeout", request=request)

    monkeypatch.setattr(
        custom_openai.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(timeout), **kwargs),
    )
    with pytest.raises(HTTPException) as error:
        await custom_openai.discover_models(BASE, "protected")
    assert error.value.status_code == 504


@pytest.mark.asyncio
async def test_settings_round_trip(auth_client, monkeypatch, local_policy):
    response = await auth_client.get("/api/settings")
    assert response.status_code == 200
    payload = response.json()["llm_settings"]
    key = "custom-protected-api-key-for-test"
    response = await auth_client.post(
        "/api/settings/keys", json={"provider": "custom_openai", "api_key": key}
    )
    assert response.status_code == 200
    public_settings = (await auth_client.get("/api/settings")).json()
    assert key not in json.dumps(public_settings)
    assert "custom_openai" in public_settings["keys"]
    payload.update(
        custom_openai_url=BASE,
        custom_openai_timeout=600,
        custom_openai_response_format="json_schema",
        small_model_provider="custom_openai",
        small_model="vendor/model",
    )
    response = await auth_client.post("/api/settings/llm", json=payload)
    assert response.status_code == 200
    restored = (await auth_client.get("/api/settings")).json()["llm_settings"]
    assert restored["custom_openai_url"] == BASE
    assert restored["custom_openai_timeout"] == 600
    assert restored["custom_openai_response_format"] == "json_schema"
    assert restored["small_model"] == "vendor/model"
    assert "api_key" not in json.dumps(restored)
    monkeypatch.setattr(
        config_api, "_resolve_provider_api_key_for_models", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(custom_openai, "discover_models", AsyncMock(return_value=["vendor/model"]))
    response = await auth_client.get(
        "/api/settings/llm-models", params={"provider": "custom_openai"}
    )
    assert response.json()["models"] == ["vendor/model"]
    payload["custom_openai_url"] = "http://169.254.169.254/v1"
    assert (await auth_client.post("/api/settings/llm", json=payload)).status_code == 400


@pytest.mark.asyncio
async def test_discovery_requires_auth(client):
    response = await client.get(
        "/api/settings/llm-models", params={"provider": "custom_openai", "api_base": BASE}
    )
    assert response.status_code in (401, 403)


def test_real_adapter_wire_contract(monkeypatch, local_policy):
    """Run LiteLLM and the SDK against a mocked transport, including vendor slashes."""
    seen = []

    def handle(_transport, request):
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "id": "test",
                "object": "chat.completion",
                "created": 1,
                "model": "openai/vendor/model",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handle)
    router = make_router("sk-or-v1-fake-custom-token")
    assert router.execute_simple_task("sys", "hello", "openai/vendor/model") == "ok"
    assert len(seen) == 1
    assert str(seen[0].url) == BASE + "/chat/completions"
    assert json.loads(seen[0].content)["model"] == "openai/vendor/model"
    assert seen[0].headers["authorization"] == "Bearer sk-or-v1-fake-custom-token"


@pytest.mark.asyncio
async def test_structured_calls_validate_schema(monkeypatch, local_policy):
    router = make_router()

    class Answer(BaseModel):
        value: int

    def response(content):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content=content), finish_reason="stop")
            ],
            model_dump=lambda: {},
        )

    monkeypatch.setattr(
        router._get_litellm(), "completion", lambda **kwargs: response('{"value": 42}')
    )
    monkeypatch.setattr(
        router._get_litellm(), "acompletion", AsyncMock(return_value=response('{"value": 42}'))
    )
    assert router.execute_complex_task("sys", "hello", Answer, "vendor/model").value == 42
    assert (await router.aexecute_complex_task("sys", "hello", Answer, "vendor/model")).value == 42
    monkeypatch.setattr(
        router._get_litellm(), "completion", lambda **kwargs: response('{"value": "invalid"}')
    )
    with pytest.raises(ValueError):
        router.execute_complex_task("sys", "hello", Answer, "vendor/model")


def test_private_default_is_not_an_opt_in(monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_PRIVATE_NETWORK_MODELS", True)
    monkeypatch.setattr(
        settings,
        "__pydantic_fields_set__",
        settings.model_fields_set - {"ALLOW_PRIVATE_NETWORK_MODELS"},
    )
    with pytest.raises(HTTPException):
        custom_openai.validate_custom_url(BASE)


@pytest.mark.asyncio
async def test_only_admin_can_configure_or_discover(auth_client):
    from sqlalchemy import update

    from tests.conftest import TestSessionLocal

    payload = (await auth_client.get("/api/settings")).json()["llm_settings"]
    async with TestSessionLocal() as session:
        await session.execute(update(User).where(User.username == "test_user").values(role="user"))
        await session.commit()
    assert (await auth_client.post("/api/settings/llm", json=payload)).status_code == 403
    response = await auth_client.get(
        "/api/settings/llm-models", params={"provider": "custom_openai", "api_base": BASE}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_async_wire_and_sse(monkeypatch, local_policy):
    seen = []

    async def handle(_transport, request):
        seen.append(request)
        payload = json.loads(request.content)
        if payload.get("stream"):
            chunk = {
                "id": "test",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "vendor/model",
                "choices": [{"index": 0, "delta": {"content": "hello"}, "finish_reason": None}],
            }
            return httpx.Response(
                200,
                content=("data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n").encode(),
                headers={"content-type": "text/event-stream"},
            )
        return httpx.Response(
            200,
            json={
                "id": "test",
                "object": "chat.completion",
                "created": 1,
                "model": "vendor/model",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", handle)
    router = make_router()
    assert await router.aexecute_simple_task("sys", "hello", "vendor/model") == "ok"
    stream = await router.stream_simple_task("sys", "hello", "vendor/model")
    result = [chunk async for chunk in stream]
    assert "hello" in "".join(chunk.choices[0].delta.content or "" for chunk in result)
    assert len(seen) == 2
    assert all(str(request.url) == BASE + "/chat/completions" for request in seen)
    assert all(json.loads(request.content)["model"] == "vendor/model" for request in seen)


def test_inference_does_not_follow_redirect(monkeypatch, local_policy):
    seen = []

    def handle(_transport, request):
        seen.append(request)
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"})

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handle)
    with pytest.raises(APIError):
        make_router().execute_simple_task("sys", "hello", "vendor/model")
    assert len(seen) == 1
    assert str(seen[0].url) == BASE + "/chat/completions"


@pytest.mark.parametrize("mode", ["prompt", "json_object", "json_schema"])
def test_explicit_structured_output_capability(local_policy, mode):
    router = make_router()
    router.custom_response_format = mode

    class Answer(BaseModel):
        value: int

    request = router._build_structured_request("sys", "hello", Answer, "vendor/model")
    assert "SCHEMA:" in request.system_prompt
    if mode == "prompt":
        assert "response_format" not in request.kwargs
        return
    assert request.kwargs["response_format"]["type"] == mode
    if mode == "json_schema":
        assert (
            request.kwargs["response_format"]["json_schema"]["schema"] == Answer.model_json_schema()
        )
