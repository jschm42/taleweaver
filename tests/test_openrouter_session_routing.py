"""Session cache routing: calls of one game session carry a stable cache-routing key.

OpenRouter gets `session_id` (sticky provider routing), OpenAI gets `prompt_cache_key`.
"""

import contextvars

from backend.core.llm_request_tuning import (
    apply_session_cache_routing,
    bind_llm_session,
    session_cache_key,
)
from backend.core.llm_router import GameMasterLLM


def _router(
    provider: str = "openrouter", category: str = "small", order: str = ""
) -> GameMasterLLM:
    router = GameMasterLLM.__new__(GameMasterLLM)
    router.provider = provider
    router.api_key = "sk-or-v1-test" if provider == "openrouter" else "sk-test"
    router.openrouter_provider = order
    router.model_category = category
    return router


def _routed_kwargs(router: GameMasterLLM, session_id: str | None = "game-abc") -> dict:
    def run() -> dict:
        bind_llm_session(session_id)
        kwargs: dict = {"extra_body": {"foo": 1}}
        router._apply_request_routing(kwargs)
        return kwargs

    return contextvars.copy_context().run(run)


def test_session_key_is_stable_opaque_and_per_category() -> None:
    def run() -> tuple[str | None, str | None, str | None]:
        bind_llm_session("game-123")
        return session_cache_key("small"), session_cache_key("small"), session_cache_key("complex")

    # Act
    first, second, complex_key = contextvars.copy_context().run(run)

    # Assert
    assert first == second
    assert first != complex_key
    assert first is not None and "game-123" not in first
    assert len(first) <= 64


def test_no_session_bound_adds_nothing() -> None:
    # Arrange
    kwargs: dict = {"model": "gpt-4o-mini"}

    # Act
    contextvars.copy_context().run(
        apply_session_cache_routing, kwargs, "openai", "small", via_openrouter=False
    )

    # Assert
    assert kwargs == {"model": "gpt-4o-mini"}


def test_openrouter_request_carries_session_id_next_to_provider_order() -> None:
    # Act
    kwargs = _routed_kwargs(_router(order="google-vertex"))

    # Assert
    body = kwargs["extra_body"]
    assert body["foo"] == 1
    assert body["session_id"].startswith("tw-") and body["session_id"].endswith("-small")
    assert body["provider"]["order"] == ["google-vertex"]
    assert "prompt_cache_key" not in kwargs


def test_openai_request_carries_prompt_cache_key() -> None:
    # Act
    kwargs = _routed_kwargs(_router(provider="openai", category="complex"))

    # Assert
    assert kwargs["prompt_cache_key"].endswith("-complex")
    assert kwargs["extra_body"] == {"foo": 1}


def test_other_providers_get_no_routing_key() -> None:
    # Act
    kwargs = _routed_kwargs(_router(provider="gemini"))

    # Assert
    assert kwargs == {"extra_body": {"foo": 1}}
