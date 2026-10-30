"""Script editor AI assistant: optimize / generate endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from tests.test_ai_fix_endpoint import _auth_headers
from tests.test_world_builder_instruct import _seed_user_with_adventure


@pytest.fixture
async def client():
    app.dependency_overrides.clear()
    from backend.core.database import get_db
    from tests.conftest import override_get_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def _patch_llm(monkeypatch, answers: list, captured: list) -> None:
    """Fake provider answering with ``answers`` in order (an Exception is raised instead)."""
    queue = list(answers)

    class _FakeLLM:
        def __init__(self, *args, **kwargs):
            pass

        async def aexecute_complex_task(self, *, system_prompt, user_prompt, response_model, **_):
            captured.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
            answer = queue.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return response_model.model_validate(answer)

    from backend.api.routes.adventures.editing import ai_fix_llm

    monkeypatch.setattr(ai_fix_llm, "GameMasterLLM", _FakeLLM)


async def _assist(client, username: str, **body) -> dict:
    tpl_id = await _seed_user_with_adventure(username)
    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/scripts/assist",
        headers=_auth_headers(username),
        json=body,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_optimize_returns_the_proposal_and_sends_the_field_context(
    client, setup_test_db, monkeypatch
):
    # Arrange
    captured: list = []
    answer = {"code": "tw.player.give_item('SAFE_01')", "summary": "Replaced the TODO."}
    _patch_llm(monkeypatch, [answer], captured)

    # Act
    payload = await _assist(
        client,
        "sa_user_1",
        mode="optimize",
        code="# TODO: give the player the safe",
        context="on_pickup",
        label="On Pickup Script",
    )

    # Assert
    assert payload == {
        "code": "tw.player.give_item('SAFE_01')",
        "summary": "Replaced the TODO.",
        "syntax_errors": [],
        "error": None,
    }
    prompt = captured[0]["user_prompt"]
    assert "On Pickup Script: runs when the item is taken into the inventory" in prompt
    assert "# TODO: give the player the safe" in prompt
    assert "OLD_LIBRARIAN" in prompt


async def test_invalid_proposal_gets_one_repair_round(client, setup_test_db, monkeypatch):
    # Arrange
    captured: list = []
    broken = {"code": "while True:\n    pass", "summary": "Loops."}
    fixed = {"code": "for i in range(3):\n    pass", "summary": "Bounded loop."}
    _patch_llm(monkeypatch, [broken, fixed], captured)

    # Act
    payload = await _assist(
        client, "sa_user_2", mode="generate", instruction="Loop three times", context="on_drop"
    )

    # Assert
    assert payload["code"] == "for i in range(3):\n    pass"
    assert payload["syntax_errors"] == []
    assert "FAILED THE SANDBOX CHECK" in captured[1]["user_prompt"]
    assert "While" in captured[1]["user_prompt"]


async def test_still_invalid_proposal_reports_its_errors(client, setup_test_db, monkeypatch):
    # Arrange
    broken = {"code": "import os", "summary": "Imports os."}
    _patch_llm(monkeypatch, [broken, broken], [])

    # Act
    payload = await _assist(client, "sa_user_3", mode="optimize", code="x = 1")

    # Assert
    assert payload["code"] == "import os"
    assert payload["syntax_errors"]


async def test_guard_expression_is_checked_as_an_expression(client, setup_test_db, monkeypatch):
    # Arrange
    answer = {"code": "tw.vars.get('lever_pulled', False)", "summary": "Guard."}
    _patch_llm(monkeypatch, [answer], [])

    # Act
    payload = await _assist(
        client,
        "sa_user_4",
        mode="generate",
        instruction="Only after the lever was pulled",
        context="guard_expression",
    )

    # Assert
    assert payload["syntax_errors"] == []


async def test_markdown_fence_is_removed(client, setup_test_db, monkeypatch):
    # Arrange
    answer = {"code": "```python\ntw.story.narrate('Hi')\n```", "summary": "Fenced."}
    _patch_llm(monkeypatch, [answer], [])

    # Act
    payload = await _assist(client, "sa_user_5", mode="optimize", code="x = 1")

    # Assert
    assert payload["code"] == "tw.story.narrate('Hi')"


async def test_generate_without_instruction_is_rejected(client, setup_test_db):
    # Act
    payload = await _assist(client, "sa_user_6", mode="generate", instruction="  ")

    # Assert
    assert payload["code"] is None
    assert payload["error"] == "Describe what the code should do."


async def test_llm_failure_returns_an_error(client, setup_test_db, monkeypatch):
    # Arrange
    _patch_llm(monkeypatch, [RuntimeError("boom")], [])

    # Act
    payload = await _assist(client, "sa_user_7", mode="optimize", code="x = 1")

    # Assert
    assert payload["code"] is None
    assert payload["error"]
