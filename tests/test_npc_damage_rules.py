"""The "NPC can be damaged" switch (is_killable): HP losses are blocked when it is off."""

from types import SimpleNamespace

from backend.engine.rules.npc_damage import blocks_hp_loss, can_be_damaged


def test_npc_is_damageable_unless_the_switch_is_off():
    # Act / Assert
    assert can_be_damaged(None, SimpleNamespace(is_killable=True)) is True
    assert can_be_damaged(None, SimpleNamespace(is_killable=None)) is True
    assert can_be_damaged(None, SimpleNamespace(is_killable=False)) is False


def test_session_override_wins_over_the_template_value():
    # Arrange
    row = SimpleNamespace(is_killable=True, hp=30)

    # Act / Assert
    assert can_be_damaged({"is_killable": False}, row) is False
    assert can_be_damaged({"is_killable": True}, SimpleNamespace(is_killable=False)) is True


def test_only_hp_losses_are_blocked():
    # Arrange
    immune = SimpleNamespace(is_killable=False, hp=30)
    mortal = SimpleNamespace(is_killable=True, hp=30)

    # Act / Assert
    assert blocks_hp_loss(None, immune, 10) is True
    assert blocks_hp_loss({"hp": 20}, immune, 25) is False  # healing from the current 20 HP
    assert blocks_hp_loss(None, immune, 30) is False
    assert blocks_hp_loss(None, mortal, 0) is False
