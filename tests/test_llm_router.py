"""Tests for strict provider routing behavior in GameMasterLLM."""
import pytest
from pydantic import BaseModel

from backend.core.llm_router import GameMasterLLM
from backend.models.user import User


def _make_user(llm_settings=None, encrypted_api_keys=None):
    return User(
        username="tester",
        llm_settings=llm_settings or {},
        encrypted_api_keys=encrypted_api_keys or {},
    )


def test_ollama_rejects_cloud_prefixed_model():
    user = _make_user(llm_settings={"ollama_url": "http://localhost:11434"})
    router = GameMasterLLM(user, provider="ollama")

    with pytest.raises(ValueError, match="Provider is 'ollama' but model"):
        router.execute_simple_task(
            system_prompt="sys",
            user_prompt="hello",
            model="openai/gpt-4o-mini",
        )


def test_ollama_simple_task_uses_local_base_without_api_key(monkeypatch):
    user = _make_user(llm_settings={"ollama_url": "http://localhost:11434"})
    router = GameMasterLLM(user, provider="ollama")

    captured = {}

    class _Msg:
        content = "ok"

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

        @staticmethod
        def model_dump():
            return {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _Resp()

    monkeypatch.setattr("backend.core.llm_router.litellm.completion", fake_completion)

    out = router.execute_simple_task(
        system_prompt="sys",
        user_prompt="hello",
        model="llama3.2",
    )

    assert out == "ok"
    assert captured["custom_llm_provider"] == "ollama"
    assert captured["api_base"] == "http://localhost:11434"
    assert "api_key" not in captured


def test_openrouter_normalizes_prefixed_model(monkeypatch):
    user = _make_user(
        llm_settings={"ollama_url": "http://localhost:11434"},
        encrypted_api_keys={"openrouter": "encrypted-placeholder"},
    )

    monkeypatch.setattr("backend.core.llm_router.GameMasterLLM._get_decrypted_key", lambda self, provider: "sk-or-v1-test")

    router = GameMasterLLM(user, provider="openrouter")

    captured = {}

    class _Msg:
        content = "ok"

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

        @staticmethod
        def model_dump():
            return {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _Resp()

    monkeypatch.setattr("backend.core.llm_router.litellm.completion", fake_completion)

    out = router.execute_simple_task(
        system_prompt="sys",
        user_prompt="hello",
        model="openai/gpt-5.4",
    )

    assert out == "ok"
    assert captured["model"] == "openai/gpt-5.4"
    assert captured["api_base"] == "https://openrouter.ai/api/v1"
    assert captured["api_key"] == "sk-or-v1-test"


def test_kimi_routes_via_moonshot_openai_compatible_endpoint(monkeypatch):
    user = _make_user(
        llm_settings={},
        encrypted_api_keys={"kimi": "encrypted-placeholder"},
    )

    monkeypatch.setattr("backend.core.llm_router.GameMasterLLM._get_decrypted_key", lambda self, provider: "sk-kimi-test")
    router = GameMasterLLM(user, provider="kimi")

    captured = {}

    class _Msg:
        content = "ok"

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

        @staticmethod
        def model_dump():
            return {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _Resp()

    monkeypatch.setattr("backend.core.llm_router.litellm.completion", fake_completion)

    out = router.execute_simple_task(
        system_prompt="sys",
        user_prompt="hello",
        model="moonshot-v1-8k",
    )

    assert out == "ok"
    assert captured["model"] == "moonshot-v1-8k"
    assert captured["custom_llm_provider"] == "openai"
    assert captured["api_base"] == "https://api.moonshot.ai/v1"
    assert captured["api_key"] == "sk-kimi-test"


def test_openrouter_retries_with_available_providers_on_provider_mismatch(monkeypatch):
    user = _make_user(
        llm_settings={},
        encrypted_api_keys={"openrouter": "encrypted-placeholder"},
    )
    monkeypatch.setattr("backend.core.llm_router.GameMasterLLM._get_decrypted_key", lambda self, provider: "sk-or-v1-test")
    router = GameMasterLLM(user, provider="openrouter")

    calls = []

    class _Msg:
        content = "ok"

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

        @staticmethod
        def model_dump():
            return {}

    def fake_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise Exception(
                "Error code: 404 - {'error': {'message': 'No allowed providers are available for the selected model.', "
                "'metadata': {'available_providers': ['xai'], 'requested_providers': ['openai']}}}"
            )
        return _Resp()

    monkeypatch.setattr("backend.core.llm_router.litellm.completion", fake_completion)

    out = router.execute_simple_task(
        system_prompt="sys",
        user_prompt="hello",
        model="openai/gpt-5-mini",
    )

    assert out == "ok"
    assert len(calls) == 2
    assert "extra_body" not in calls[0]
    assert calls[1]["extra_body"]["provider"]["order"] == ["xai"]
    assert calls[1]["extra_body"]["provider"]["allow_fallbacks"] is True


@pytest.mark.asyncio
async def test_openrouter_async_retries_with_available_providers_on_provider_mismatch(monkeypatch):
    user = _make_user(
        llm_settings={},
        encrypted_api_keys={"openrouter": "encrypted-placeholder"},
    )
    monkeypatch.setattr("backend.core.llm_router.GameMasterLLM._get_decrypted_key", lambda self, provider: "sk-or-v1-test")
    router = GameMasterLLM(user, provider="openrouter")

    calls = []

    class _Msg:
        content = "ok"

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

        @staticmethod
        def model_dump():
            return {}

    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise Exception(
                "Error code: 404 - {'error': {'message': 'No allowed providers are available for the selected model.', "
                "'metadata': {'available_providers': ['xai'], 'requested_providers': ['openai']}}}"
            )
        return _Resp()

    monkeypatch.setattr("backend.core.llm_router.litellm.acompletion", fake_acompletion)

    out = await router.stream_simple_task(
        system_prompt="sys",
        user_prompt="hello",
        model="openai/gpt-5-mini",
    )

    assert out is not None
    assert len(calls) == 2
    assert "extra_body" not in calls[0]
    assert calls[1]["extra_body"]["provider"]["order"] == ["xai"]
    assert calls[1]["extra_body"]["provider"]["allow_fallbacks"] is True


def test_thinking_defaults_to_disabled_when_not_configured(monkeypatch):
    monkeypatch.setattr("backend.core.llm_router.GameMasterLLM._get_decrypted_key", lambda self, provider: "test-key")
    user = _make_user(llm_settings={"small_model": "gpt-4o-mini"})
    router = GameMasterLLM(user, provider="openai", model_category="small")
    assert router.enable_thinking is False


def test_thinking_string_false_is_treated_as_disabled(monkeypatch):
    monkeypatch.setattr("backend.core.llm_router.GameMasterLLM._get_decrypted_key", lambda self, provider: "test-key")
    user = _make_user(llm_settings={"small_enable_thinking": "false"})
    router = GameMasterLLM(user, provider="openai", model_category="small")
    assert router.enable_thinking is False


def test_thinking_string_true_is_treated_as_enabled(monkeypatch):
    monkeypatch.setattr("backend.core.llm_router.GameMasterLLM._get_decrypted_key", lambda self, provider: "test-key")
    user = _make_user(llm_settings={"small_enable_thinking": "true"})
    router = GameMasterLLM(user, provider="openai", model_category="small")
    assert router.enable_thinking is True


def test_invalid_thinking_value_logs_warning_and_falls_back_to_false(monkeypatch, caplog):
    monkeypatch.setattr("backend.core.llm_router.GameMasterLLM._get_decrypted_key", lambda self, provider: "test-key")
    user = _make_user(llm_settings={"small_enable_thinking": "definitely"})

    caplog.set_level("WARNING")
    router = GameMasterLLM(user, provider="openai", model_category="small")

    assert router.enable_thinking is False
    assert "Invalid thinking setting" in caplog.text


@pytest.mark.asyncio
async def test_aexecute_simple_task(monkeypatch):
    user = _make_user(
        encrypted_api_keys={"openai": "encrypted-placeholder"},
    )
    monkeypatch.setattr("backend.core.llm_router.GameMasterLLM._get_decrypted_key", lambda self, provider: "sk-test")
    router = GameMasterLLM(user, provider="openai")

    captured = {}

    class _Msg:
        content = "hello world"

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

        @staticmethod
        def model_dump():
            return {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        return _Resp()

    monkeypatch.setattr("backend.core.llm_router.litellm.acompletion", fake_acompletion)

    out = await router.aexecute_simple_task(
        system_prompt="sys",
        user_prompt="prompt",
        model="gpt-4o",
    )

    assert out == "hello world"
    assert captured["model"] == "gpt-4o"
    assert captured["custom_llm_provider"] == "openai"
    assert "stream" not in captured or captured["stream"] is False


@pytest.mark.asyncio
async def test_stream_simple_task_openai_non_prefixed_model_sets_provider(monkeypatch):
    user = _make_user(
        encrypted_api_keys={"openai": "encrypted-placeholder"},
    )
    monkeypatch.setattr("backend.core.llm_router.GameMasterLLM._get_decrypted_key", lambda self, provider: "sk-test")
    router = GameMasterLLM(user, provider="openai")

    captured = {}

    class _Msg:
        content = "hello stream"

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

        @staticmethod
        def model_dump():
            return {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        return _Resp()

    monkeypatch.setattr("backend.core.llm_router.litellm.acompletion", fake_acompletion)

    out = await router.stream_simple_task(
        system_prompt="sys",
        user_prompt="prompt",
        model="gpt-5.3",
    )

    assert out is not None
    assert captured["model"] == "gpt-5.3"
    assert captured["custom_llm_provider"] == "openai"
    assert captured["stream"] is True


@pytest.mark.asyncio
async def test_aexecute_complex_task_fallback_injects_schema_into_sent_system_prompt(monkeypatch):
    class _MiniSchema(BaseModel):
        required: str

    user = _make_user(encrypted_api_keys={"openai": "encrypted-placeholder"})
    monkeypatch.setattr("backend.core.llm_router.GameMasterLLM._get_decrypted_key", lambda self, provider: "sk-test")
    router = GameMasterLLM(user, provider="openai")

    captured = {}

    class _Msg:
        content = '{"required":"ok"}'

    class _Choice:
        message = _Msg()
        finish_reason = "stop"

    class _Resp:
        choices = [_Choice()]

        @staticmethod
        def model_dump():
            return {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        return _Resp()

    monkeypatch.setattr("backend.core.llm_router.litellm.acompletion", fake_acompletion)

    out = await router.aexecute_complex_task(
        system_prompt="sys",
        user_prompt="prompt",
        response_model=_MiniSchema,
        model="claude-3-5-sonnet",
    )

    assert out.required == "ok"
    assert "SCHEMA:" in captured["messages"][0]["content"]


@pytest.mark.asyncio
async def test_aexecute_complex_task_gemini_direct_uses_structured_outputs(monkeypatch):
    class _MiniSchema(BaseModel):
        required: str

    user = _make_user(encrypted_api_keys={"google": "encrypted-placeholder"})
    monkeypatch.setattr("backend.core.llm_router.GameMasterLLM._get_decrypted_key", lambda self, provider: "sk-test")
    router = GameMasterLLM(user, provider="google")

    captured = {}

    class _Msg:
        content = '{"required":"ok"}'

    class _Choice:
        message = _Msg()
        finish_reason = "stop"

    class _Resp:
        choices = [_Choice()]

        @staticmethod
        def model_dump():
            return {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        return _Resp()

    monkeypatch.setattr("backend.core.llm_router.litellm.acompletion", fake_acompletion)

    out = await router.aexecute_complex_task(
        system_prompt="sys",
        user_prompt="prompt",
        response_model=_MiniSchema,
        model="gemini-3.1-pro-preview",
    )

    assert out.required == "ok"
    # Direct Gemini should pass response_model directly as response_format
    assert captured["response_format"] == _MiniSchema


@pytest.mark.asyncio
async def test_aexecute_complex_task_kimi_uses_json_mode_fallback(monkeypatch):
    class _MiniSchema(BaseModel):
        title: str

    user = _make_user(
        encrypted_api_keys={"kimi": "encrypted-placeholder"},
    )
    monkeypatch.setattr("backend.core.llm_router.GameMasterLLM._get_decrypted_key", lambda self, provider: "sk-kimi-test")
    router = GameMasterLLM(user, provider="kimi")

    captured = {}

    class _Msg:
        content = '{"title":"ok"}'

    class _Choice:
        message = _Msg()
        finish_reason = "stop"

    class _Resp:
        choices = [_Choice()]

        @staticmethod
        def model_dump():
            return {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        return _Resp()

    monkeypatch.setattr("backend.core.llm_router.litellm.acompletion", fake_acompletion)

    out = await router.aexecute_complex_task(
        system_prompt="sys",
        user_prompt="prompt",
        response_model=_MiniSchema,
        model="kimi-k2.6",
    )

    assert out.title == "ok"
    assert captured["response_format"] == {"type": "json_object"}
    assert "SCHEMA:" in captured["messages"][0]["content"]
    assert captured["api_base"] == "https://api.moonshot.ai/v1"


@pytest.mark.asyncio
async def test_aexecute_complex_task_surfaces_schema_validation_failure(monkeypatch):
    class _MiniSchema(BaseModel):
        required: str

    user = _make_user(encrypted_api_keys={"openai": "encrypted-placeholder"})
    monkeypatch.setattr("backend.core.llm_router.GameMasterLLM._get_decrypted_key", lambda self, provider: "sk-test")
    router = GameMasterLLM(user, provider="openai")

    class _Msg:
        content = "{}"

    class _Choice:
        message = _Msg()
        finish_reason = "stop"

    class _Resp:
        choices = [_Choice()]

        @staticmethod
        def model_dump():
            return {}

    async def fake_acompletion(**kwargs):
        return _Resp()

    monkeypatch.setattr("backend.core.llm_router.litellm.acompletion", fake_acompletion)

    with pytest.raises(ValueError, match="does not match expected schema"):
        await router.aexecute_complex_task(
            system_prompt="sys",
            user_prompt="prompt",
            response_model=_MiniSchema,
            model="claude-3-5-sonnet",
        )


@pytest.mark.asyncio
async def test_aexecute_complex_task_treats_empty_cleaned_content_as_no_content(monkeypatch):
    class _MiniSchema(BaseModel):
        required: str

    user = _make_user(encrypted_api_keys={"openai": "encrypted-placeholder"})
    monkeypatch.setattr("backend.core.llm_router.GameMasterLLM._get_decrypted_key", lambda self, provider: "sk-test")
    router = GameMasterLLM(user, provider="openai")

    class _Msg:
        content = "```json\n```"

    class _Choice:
        message = _Msg()
        finish_reason = "stop"

    class _Resp:
        choices = [_Choice()]

        @staticmethod
        def model_dump():
            return {}

    async def fake_acompletion(**kwargs):
        return _Resp()

    monkeypatch.setattr("backend.core.llm_router.litellm.acompletion", fake_acompletion)

    with pytest.raises(ValueError, match="No content returned from LLM for complex task"):
        await router.aexecute_complex_task(
            system_prompt="sys",
            user_prompt="prompt",
            response_model=_MiniSchema,
            model="claude-3-5-sonnet",
        )
