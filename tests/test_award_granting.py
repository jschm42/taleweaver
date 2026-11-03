"""Granting awards from the GM and from scripts (tw.awards.grant)."""

from types import SimpleNamespace

import pytest

from backend.api.routes.adventures.award_granting import (
    AWARD_MESSAGE_PREFIX,
    CHECKPOINT_REASON_AWARD_GRANTED,
    grant_awards,
    record_earned_awards,
)
from backend.engine.scripting.context import GameContext


class _FakeManager:
    def __init__(self, awards: list[dict], earned: list[dict] | None = None):
        self.user = SimpleNamespace(earned_awards=list(earned or []))
        self.adventure = SimpleNamespace(id="adv-1", title="Test-Lab", awards=awards)
        self.state = SimpleNamespace(session_id="sess-1")
        self.chat: list[tuple[str, str]] = []
        self.checkpoints: list[str] = []

    async def _save_chat_message(self, role: str, content: str) -> None:
        self.chat.append((role, content))

    def _queue_checkpoint(self, reason: str) -> None:
        self.checkpoints.append(reason)


_AWARDS = [{"key": "AWARD_BRASS_LEVER", "title": "Brass Lever Whisperer", "tier": "gold"}]


@pytest.fixture(autouse=True)
def _plain_user(monkeypatch):
    # flag_modified needs a mapped object; the fake user is a plain namespace.
    monkeypatch.setattr(
        "backend.api.routes.adventures.award_granting.flag_modified", lambda *_: None
    )


def _record(manager: _FakeManager, keys: list[str]) -> list[dict]:
    return record_earned_awards(manager.user, manager.adventure, "sess-1", keys)


def test_record_matches_case_insensitively_and_only_once():
    # Arrange
    manager = _FakeManager(_AWARDS)

    # Act
    first = _record(manager, ["award_brass_lever"])
    second = _record(manager, ["AWARD_BRASS_LEVER"])

    # Assert
    assert [a["key"] for a in first] == ["AWARD_BRASS_LEVER"]
    assert second == []
    assert len(manager.user.earned_awards) == 1
    earned = manager.user.earned_awards[0]
    assert (earned["key"], earned["template_id"], earned["tier"]) == (
        "AWARD_BRASS_LEVER",
        "adv-1",
        "gold",
    )


def test_record_ignores_unknown_keys():
    # Arrange
    manager = _FakeManager(_AWARDS)

    # Act
    granted = _record(manager, ["NO_SUCH_AWARD"])

    # Assert
    assert granted == []
    assert manager.user.earned_awards == []


@pytest.mark.asyncio
async def test_script_grant_reaches_the_player():
    # Arrange: what tw.awards.grant(...) leaves in the script changeset
    manager = _FakeManager(_AWARDS)
    ctx = GameContext()
    ctx.awards.grant("award_brass_lever")

    # Act
    messages = await grant_awards(manager, ctx.changeset.granted_award_keys)

    # Assert
    expected = f"{AWARD_MESSAGE_PREFIX}Brass Lever Whisperer"
    assert messages == [expected]
    assert manager.chat == [("system", expected)]
    assert manager.checkpoints == [CHECKPOINT_REASON_AWARD_GRANTED]
    assert manager.user.earned_awards[0]["key"] == "AWARD_BRASS_LEVER"


@pytest.mark.asyncio
async def test_unknown_script_award_is_reported_in_the_chat():
    # Arrange
    manager = _FakeManager(_AWARDS)

    # Act
    messages = await grant_awards(manager, ["AWARD_TYPO"], from_script=True)

    # Assert
    assert len(messages) == 1
    assert messages[0].startswith("Script error in 'tw.awards.grant'")
    assert "'AWARD_TYPO' does not exist" in messages[0]
    assert manager.chat == [("system", messages[0])]
    assert manager.user.earned_awards == []
    assert manager.checkpoints == []


@pytest.mark.asyncio
async def test_unknown_gm_award_is_only_logged():
    # Arrange
    manager = _FakeManager(_AWARDS)

    # Act
    messages = await grant_awards(manager, ["AWARD_TYPO"])

    # Assert
    assert messages == []
    assert manager.chat == []
