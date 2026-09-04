import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import litellm

from backend.core.llm_router import GameMasterLLM
from backend.models.user import User

pytestmark = pytest.mark.asyncio


def _mock_user():
    return User(
        id="test-user-retry",
        username="retryplayer",
        hashed_password="pw",
        role="user",
        llm_settings={"openai_api_key": "dummy-key"}
    )


def _create_test_router(user):
    with patch.object(GameMasterLLM, "_get_decrypted_key", return_value="fake-api-key"):
        return GameMasterLLM(user=user, provider="openai", model_category="small")


async def test_llm_router_transient_retry_success():
    """Verifies that transient timeout errors are retried up to 3 times and succeed if an attempt passes."""
    user = _mock_user()
    router = _create_test_router(user)

    call_count = 0

    async def _mock_acompletion(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            # Simulate transient timeout on attempts 1 and 2
            raise litellm.Timeout(
                "Timeout Error: DeepseekException - litellm.Timeout: Connection timed out. Timeout passed=60.0, time taken=0.005 seconds",
                model="deepseek-v4-flash",
                llm_provider="deepseek",
            )
        # Succeeded on attempt 3 (retry 2)
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content="Success narrative"))]
        return mock_resp

    with patch.object(router, "_get_litellm") as mock_litellm, patch("asyncio.sleep", new_callable=AsyncMock):
        mock_litellm.return_value.acompletion = AsyncMock(side_effect=_mock_acompletion)
        kwargs = {"model": "deepseek-v4-flash", "messages": [{"role": "user", "content": "Hello"}]}
        result = await router._acompletion_with_openrouter_fallback(kwargs)
        assert call_count == 3
        assert result.choices[0].message.content == "Success narrative"


async def test_llm_router_transient_retry_exhausted_raises():
    """Verifies that after 3 retries (4 attempts total), the exception is raised."""
    user = _mock_user()
    router = _create_test_router(user)

    call_count = 0

    async def _mock_acompletion(**kwargs):
        nonlocal call_count
        call_count += 1
        raise litellm.Timeout(
            "Timeout Error: DeepseekException - litellm.Timeout: Connection timed out. Timeout passed=60.0, time taken=0.005 seconds",
            model="deepseek-v4-flash",
            llm_provider="deepseek",
        )

    with patch.object(router, "_get_litellm") as mock_litellm, patch("asyncio.sleep", new_callable=AsyncMock):
        mock_litellm.return_value.acompletion = AsyncMock(side_effect=_mock_acompletion)
        kwargs = {"model": "deepseek-v4-flash", "messages": [{"role": "user", "content": "Hello"}]}
        with pytest.raises(litellm.Timeout):
            await router._acompletion_with_openrouter_fallback(kwargs)
        # Should have executed attempt 1 + 3 retries = 4 attempts total
        assert call_count == 4


async def test_llm_router_non_transient_error_no_retry():
    """Verifies that non-transient errors (e.g. auth/value errors) are not retried."""
    user = _mock_user()
    router = _create_test_router(user)

    call_count = 0

    async def _mock_acompletion(**kwargs):
        nonlocal call_count
        call_count += 1
        raise ValueError("Non-transient error")

    with patch.object(router, "_get_litellm") as mock_litellm, patch("asyncio.sleep", new_callable=AsyncMock):
        mock_litellm.return_value.acompletion = AsyncMock(side_effect=_mock_acompletion)
        kwargs = {"model": "deepseek-v4-flash", "messages": [{"role": "user", "content": "Hello"}]}
        with pytest.raises(ValueError):
            await router._acompletion_with_openrouter_fallback(kwargs)
        assert call_count == 1
