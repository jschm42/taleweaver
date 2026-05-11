"""
Unit tests for the HeartbeatManager and status-effect tick logic.

LLM calls are not involved here; we test the pure game-logic functions
in isolation using simple Avatar stubs.
"""
from unittest.mock import MagicMock

from backend.engine.rule_engine import RESOURCE_CAP, RuleEngine


def _apply_status_effect_ticks(avatar):
    return RuleEngine.apply_ticks(avatar)


def _make_avatar(hp: int = 200, stamina: int = 200, mana: int = 200, effects=None):
    """Creates a minimal Avatar-like mock for unit testing."""
    avatar = MagicMock()
    avatar.hp = hp
    avatar.stamina = stamina
    avatar.mana = mana
    avatar.status_effects = effects or []
    return avatar


# ---------------------------------------------------------------------------
# _apply_status_effect_ticks
# ---------------------------------------------------------------------------

def test_poison_drains_hp():
    """Poisoned status reduces HP by 5 per tick."""
    # Arrange
    avatar = _make_avatar(hp=100, effects=["Poisoned"])

    # Act
    messages = _apply_status_effect_ticks(avatar)

    # Assert
    assert avatar.hp == 95
    assert any("Poisoned" in m for m in messages)


def test_burning_drains_hp():
    """Burning status reduces HP by 10 per tick."""
    avatar = _make_avatar(hp=50, effects=["Burning"])
    _apply_status_effect_ticks(avatar)
    assert avatar.hp == 40


def test_bleeding_drains_hp_and_stamina():
    """Bleeding reduces HP by 3 and Stamina by 2 per tick."""
    avatar = _make_avatar(hp=100, stamina=100, effects=["Bleeding"])
    _apply_status_effect_ticks(avatar)
    assert avatar.hp == 97
    assert avatar.stamina == 98


def test_regenerating_restores_hp():
    """Regenerating status restores 5 HP per tick."""
    avatar = _make_avatar(hp=50, effects=["Regenerating"])
    _apply_status_effect_ticks(avatar)
    assert avatar.hp == 55


def test_resting_restores_stamina_and_mana():
    """Resting status restores 3 Stamina and 3 Mana per tick."""
    avatar = _make_avatar(stamina=100, mana=100, effects=["Resting"])
    _apply_status_effect_ticks(avatar)
    assert avatar.stamina == 103
    assert avatar.mana == 103


def test_hp_clamped_at_zero():
    """HP cannot drop below 0 even with heavy damage effects."""
    avatar = _make_avatar(hp=3, effects=["Burning"])  # -10 HP
    _apply_status_effect_ticks(avatar)
    assert avatar.hp == 0


def test_hp_clamped_at_resource_cap():
    """HP cannot exceed RESOURCE_CAP even with healing effects."""
    avatar = _make_avatar(hp=RESOURCE_CAP, effects=["Regenerating"])
    _apply_status_effect_ticks(avatar)
    assert avatar.hp == RESOURCE_CAP


def test_stamina_clamped_at_resource_cap():
    """Stamina cannot exceed RESOURCE_CAP."""
    avatar = _make_avatar(stamina=RESOURCE_CAP, effects=["Resting"])
    _apply_status_effect_ticks(avatar)
    assert avatar.stamina == RESOURCE_CAP


def test_unknown_effect_is_ignored():
    """An unrecognised status effect produces no changes and no errors."""
    avatar = _make_avatar(hp=100, effects=["Invisible"])
    messages = _apply_status_effect_ticks(avatar)
    assert avatar.hp == 100
    assert messages == []


def test_multiple_effects_stack():
    """Multiple active effects are all applied in the same tick."""
    avatar = _make_avatar(hp=100, stamina=100, effects=["Poisoned", "Regenerating"])
    _apply_status_effect_ticks(avatar)
    # Poisoned: -5 HP, Regenerating: +5 HP → net 0
    assert avatar.hp == 100


def test_no_effects_returns_empty_messages():
    """An avatar with no status effects produces no tick messages."""
    avatar = _make_avatar(effects=[])
    messages = _apply_status_effect_ticks(avatar)
    assert messages == []
