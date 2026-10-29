"""Tests for the ``/roll [sides]`` player command."""

import json
import re

import pytest

from backend.engine.rules import dice_command
from backend.engine.rules.dice_command import (
    DEFAULT_SIDES,
    RollCommandError,
    format_roll_message,
    handle_roll_command,
    is_roll_command,
    parse_roll_sides,
)


class _FakeDb:
    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1


class _FakeManager:
    def __init__(self):
        self.db = _FakeDb()
        self.saved: list[tuple[str, str]] = []

    async def _save_chat_message(self, role: str, content: str):
        self.saved.append((role, content))


async def _collect(manager, message):
    return [chunk async for chunk in handle_roll_command(manager, message)]


def _payload(chunk: str) -> dict:
    return json.loads(chunk.split("data: ", 1)[1])


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("/roll", True),
        ("/ROLL 20", True),
        ("/roll d12", True),
        ("/rolling", False),
        ("roll 6", False),
    ],
)
def test_is_roll_command(message, expected):
    # Arrange / Act / Assert
    assert is_roll_command(message) is expected


@pytest.mark.parametrize(
    ("message", "sides"),
    [
        ("/roll", DEFAULT_SIDES),
        ("/roll 20", 20),
        ("/roll d12", 12),
        ("/roll 2", 2),
        ("/roll 30", 30),
    ],
)
def test_parse_roll_sides_accepts_valid_ranges(message, sides):
    # Arrange / Act
    result = parse_roll_sides(message)

    # Assert
    assert result == sides


@pytest.mark.parametrize("message", ["/roll 1", "/roll 31", "/roll abc", "/roll -5", "/roll 2.5"])
def test_parse_roll_sides_rejects_invalid_input(message):
    # Arrange / Act / Assert
    with pytest.raises(RollCommandError):
        parse_roll_sides(message)


def test_format_roll_message_matches_frontend_pattern():
    # Arrange
    pattern = re.compile(r"ROLL d(\d+)\*\*:\s*\*\*(\d+)\*\*")

    # Act
    match = pattern.search(format_roll_message(20, 17))

    # Assert
    assert match is not None
    assert match.groups() == ("20", "17")


async def test_handle_roll_command_saves_and_streams_result(monkeypatch):
    # Arrange
    monkeypatch.setattr(dice_command, "roll_die", lambda sides: 4)
    manager = _FakeManager()

    # Act
    chunks = await _collect(manager, "/roll 6")

    # Assert
    assert len(chunks) == 1
    assert chunks[0].startswith("event: system")
    assert _payload(chunks[0])["content"] == format_roll_message(6, 4)
    assert manager.saved == [("system", format_roll_message(6, 4))]
    assert manager.db.commits == 1


async def test_handle_roll_command_reports_invalid_range_without_saving():
    # Arrange
    manager = _FakeManager()

    # Act
    chunks = await _collect(manager, "/roll 99")

    # Assert
    assert "between 2 and 30" in _payload(chunks[0])["content"]
    assert manager.saved == []
    assert manager.db.commits == 0


def test_roll_die_stays_within_bounds():
    # Arrange / Act
    results = {dice_command.roll_die(6) for _ in range(500)}

    # Assert
    assert results <= set(range(1, 7))
    assert min(results) == 1
    assert max(results) == 6


async def test_roll_endpoint_returns_and_stores_result_instantly(auth_client, monkeypatch):
    # Arrange
    from sqlalchemy import select

    from backend.models.chat import ChatMessage
    from tests.conftest import TestSessionLocal
    from tests.test_adventures_api import _create_adventure

    monkeypatch.setattr(dice_command, "roll_die", lambda sides: sides)
    ids = await _create_adventure(auth_client, "Dice Endpoint Quest")

    # Act
    resp = await auth_client.post(f"/api/adventures/{ids['game_id']}/roll", json={"args": "d20"})

    # Assert
    assert resp.status_code == 200, resp.text
    assert resp.json()["content"] == format_roll_message(20, 20)
    async with TestSessionLocal() as db:
        stored = (
            (await db.execute(select(ChatMessage).where(ChatMessage.session_id == ids["game_id"])))
            .scalars()
            .all()
        )
    assert [m.content for m in stored if m.role == "system"][-1] == format_roll_message(20, 20)


async def test_roll_endpoint_rejects_invalid_sides(auth_client):
    # Arrange
    from tests.test_adventures_api import _create_adventure

    ids = await _create_adventure(auth_client, "Dice Error Quest")

    # Act
    resp = await auth_client.post(f"/api/adventures/{ids['game_id']}/roll", json={"args": "99"})

    # Assert
    assert resp.status_code == 422
    assert "between 2 and 30" in resp.json()["detail"]
