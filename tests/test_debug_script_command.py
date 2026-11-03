"""/script <code>: runs script statements in debug mode and answers with a debug message."""

import json

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.debug_script_command import debug_report
from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.core.config import settings
from backend.models.chat import ChatMessage
from tests.test_game_loop import _seed_game_context


def _system_payloads(chunks: list[str]) -> list[dict]:
    payloads = []
    for chunk in chunks:
        if not chunk.startswith("event: system"):
            continue
        data_line = next(line for line in chunk.split("\n") if line.startswith("data:"))
        payloads.append(json.loads(data_line[5:]))
    return payloads


async def _run(db, user, message: str) -> list[dict]:
    manager = GameTurnManager(db, "session-1", user)
    return _system_payloads([chunk async for chunk in manager.process_turn(message)])


@pytest.mark.asyncio
async def test_script_runs_statements_and_returns_expression_value(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    # Arrange
    monkeypatch.setattr(settings, "TALEWEAVER_DEBUG_ENABLED", False)
    async with TestSessionLocal() as db:
        user, _adv, _avatar, state = await _seed_game_context(db)
        state.is_debug_enabled = True
        await db.commit()

        # Act
        await _run(db, user, "/script tw.vars.set('Door', 'OPEN'); tw.vars.set('count', 2)")
        payloads = await _run(db, user, "/script tw.vars.get('Door') + str(tw.vars.get('count'))")

        # Assert
        report = payloads[-1]
        assert report["is_debug"] is True
        assert report["content"] == (
            "[DEBUG SCRIPT] OK\n>>> tw.vars.get('Door') + str(tw.vars.get('count'))\n= 'OPEN2'"
        )
        saved = (await db.execute(select(ChatMessage.content))).scalars().all()
        assert report["content"] in saved


@pytest.mark.asyncio
async def test_script_reports_syntax_errors_without_running(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    # Arrange
    monkeypatch.setattr(settings, "TALEWEAVER_DEBUG_ENABLED", False)
    async with TestSessionLocal() as db:
        user, _adv, _avatar, state = await _seed_game_context(db)
        state.is_debug_enabled = True
        await db.commit()

        # Act
        payloads = await _run(db, user, "/script tw.vars.set('x', ")

        # Assert
        assert payloads[-1]["content"].startswith("[DEBUG SCRIPT] FAILED\n>>> tw.vars.set('x',\n")
        assert "Syntax error" in payloads[-1]["content"]


@pytest.mark.asyncio
async def test_script_is_unknown_without_debug_mode(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    # Arrange
    monkeypatch.setattr(settings, "TALEWEAVER_DEBUG_ENABLED", False)
    async with TestSessionLocal() as db:
        user, _adv, _avatar, state = await _seed_game_context(db)
        state.is_debug_enabled = False
        await db.commit()

        # Act
        payloads = await _run(db, user, "/script tw.vars.set('x', 1)")
        await db.refresh(state)

        # Assert
        assert payloads[0]["content"].startswith("Unknown command: /script")
        assert "x" not in (state.entity_states or {}).get("__script_vars__", {})


def test_report_lists_runtime_errors_instead_of_a_value():
    # Act
    report = debug_report(
        "tw.npcs.get('X').boom()", "None", ["Script error in 'debug_script': boom"]
    )

    # Assert
    assert report == (
        "[DEBUG SCRIPT] FAILED\n>>> tw.npcs.get('X').boom()\nScript error in 'debug_script': boom"
    )
