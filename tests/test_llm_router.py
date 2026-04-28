"""Tests for strict provider routing behavior in GameMasterLLM."""
import pytest

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
