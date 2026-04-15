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
