"""Tests for NPC battle banter at the end of every few combat rounds."""

import pytest

from backend.api.routes.adventures.combat.banter import (
    FALLBACK_LINES,
    MAX_BANTER_CHARS,
    CombatBanterMixin,
    battle_mood,
    clean_banter_line,
)
from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from tests.test_combat_encounters import SESSION_ID, _patch_dice, _play, _seed


def test_battle_mood_compares_hp_ratios():
    # Arrange
    healthy = {"hp": 90, "max_hp": 100}
    wounded = {"hp": 20, "max_hp": 100}

    # Act / Assert
    assert battle_mood(healthy, wounded) == "winning"
    assert battle_mood(wounded, healthy) == "losing"
    assert battle_mood(healthy, healthy) == "even"


def test_clean_banter_line_strips_quotes_and_caps_length():
    # Arrange
    quoted = '  "You call that a swing?"  '
    long_line = "word " * 80

    # Act
    cleaned = clean_banter_line(quoted)
    capped = clean_banter_line(long_line)

    # Assert
    assert cleaned == "You call that a swing?"
    assert len(capped) == MAX_BANTER_CHARS
    assert capped.endswith("…")


def test_banter_is_scheduled_every_three_to_four_rounds(monkeypatch):
    # Arrange
    monkeypatch.setattr(
        "backend.api.routes.adventures.gameplay_logic.random.randint", lambda *_a: 3
    )
    mixin = CombatBanterMixin()
    combat = {"round": 2}

    # Act
    due_round_two = mixin._banter_due(combat)
    combat["round"] = 3
    due_round_three = mixin._banter_due(combat)
    CombatBanterMixin._schedule_next_banter(combat, 3)

    # Assert
    assert due_round_two is False
    assert due_round_three is True
    assert combat["next_banter_round"] == 6


@pytest.mark.asyncio
async def test_round_end_adds_llm_banter_for_engaged_enemy(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        user, _avatar, _state = await _seed(db)
        _patch_dice(monkeypatch)
        monkeypatch.setattr(CombatBanterMixin, "_banter_due", lambda _self, _combat: True)

        async def fake_line(_self, _combat, _speaker, _mood):
            return "You fight like a startled chicken."

        monkeypatch.setattr(CombatBanterMixin, "_llm_banter_line", fake_line)
        manager = GameTurnManager(db, SESSION_ID, user)
        await _play(manager, "/fight GOBLIN")

        # Act
        await _play(manager, "/attack GOBLIN")

        # Assert
        combat = manager._read_combat_state()
        banter = [e for e in combat["log"] if e["type"] == "banter"]
        assert len(banter) == 1
        assert banter[0]["data"] == {
            "kind": "banter",
            "actor": "GOBLIN",
            "line": "You fight like a startled chicken.",
        }
        assert banter[0]["text"] == 'Goblin: "You fight like a startled chicken."'


@pytest.mark.asyncio
async def test_banter_falls_back_to_canned_line_without_llm(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        user, _avatar, _state = await _seed(db)
        _patch_dice(monkeypatch)
        monkeypatch.setattr(CombatBanterMixin, "_banter_due", lambda _self, _combat: True)
        monkeypatch.setattr(CombatBanterMixin, "_small_llm", lambda _self: None)
        manager = GameTurnManager(db, SESSION_ID, user)
        await _play(manager, "/fight GOBLIN")

        # Act
        await _play(manager, "/attack GOBLIN")

        # Assert
        combat = manager._read_combat_state()
        banter = next(e for e in combat["log"] if e["type"] == "banter")
        all_fallbacks = {line for lines in FALLBACK_LINES.values() for line in lines}
        assert banter["data"]["line"] in all_fallbacks
