"""Tests for the per-session narration style (how much the narrator writes per turn)."""

import pytest
from sqlalchemy import select

from backend.core import prompts
from backend.core.narration_styles import (
    DEFAULT_NARRATION_STYLE,
    is_narration_style,
    narration_max_tokens,
    narration_style_reminder,
    narration_style_rules,
)
from backend.models.session_state import SessionState
from tests.conftest import TestSessionLocal
from tests.test_adventures_api import _create_adventure


@pytest.mark.parametrize(
    ("style", "marker"),
    [
        ("terse", "TERSE"),
        ("dialogue", "DIALOGUE-FIRST SCRIPT"),
        ("balanced", "BALANCED"),
        ("rich", "RICH"),
        ("epic", "EPIC"),
    ],
)
def test_each_style_has_its_own_length_rules(style, marker):
    # Arrange / Act
    rules = narration_style_rules(style)

    # Assert
    assert f"NARRATION STYLE — {marker}" in rules


@pytest.mark.parametrize("value", [None, "", "verbose", 3])
def test_unknown_style_falls_back_to_default(value):
    # Arrange / Act
    rules = narration_style_rules(value)

    # Assert
    assert not is_narration_style(value)
    assert rules == narration_style_rules(DEFAULT_NARRATION_STYLE)


def test_shared_formatting_no_longer_hardcodes_length():
    # Arrange
    formatting = prompts.GM_NARRATION_MANDATORY_FORMATTING

    # Act / Assert
    assert "1-2 short paragraphs max" not in formatting
    assert "NARRATION STYLE" in formatting


async def test_session_update_stores_narration_style(auth_client):
    # Arrange
    ids = await _create_adventure(auth_client, "Narration Style Quest")

    # Act
    resp = await auth_client.patch(
        f"/api/adventures/sessions/{ids['game_id']}", json={"narration_style": "epic"}
    )

    # Assert
    assert resp.status_code == 200, resp.text
    async with TestSessionLocal() as db:
        state = (
            (
                await db.execute(
                    select(SessionState).where(SessionState.session_id == ids["game_id"])
                )
            )
            .scalars()
            .first()
        )
    assert state.narration_style == "epic"


async def test_session_update_rejects_unknown_narration_style(auth_client):
    # Arrange
    ids = await _create_adventure(auth_client, "Narration Style Error Quest")

    # Act
    resp = await auth_client.patch(
        f"/api/adventures/sessions/{ids['game_id']}", json={"narration_style": "verbose"}
    )

    # Assert
    assert resp.status_code == 422


async def test_new_sessions_default_to_balanced(auth_client):
    # Arrange / Act
    ids = await _create_adventure(auth_client, "Default Style Quest")

    # Assert
    async with TestSessionLocal() as db:
        state = (
            (
                await db.execute(
                    select(SessionState).where(SessionState.session_id == ids["game_id"])
                )
            )
            .scalars()
            .first()
        )
    assert state.narration_style == DEFAULT_NARRATION_STYLE


def test_default_style_is_balanced():
    # Arrange / Act / Assert
    assert DEFAULT_NARRATION_STYLE == "balanced"


@pytest.mark.parametrize("style", ["terse", "dialogue", "balanced", "rich", "epic", None])
def test_every_style_has_a_turn_length_reminder(style):
    # Arrange / Act
    reminder = narration_style_reminder(style)

    # Assert
    assert reminder.startswith("LENGTH:")


@pytest.mark.parametrize("style", ["terse", "dialogue", "balanced", "rich", "epic", None])
def test_every_style_caps_narration_tokens(style):
    # Arrange / Act
    cap = narration_max_tokens(style)

    # Assert
    assert 200 <= cap <= 2000


def test_longer_styles_get_more_room():
    # Arrange / Act / Assert
    assert (
        narration_max_tokens("terse")
        < narration_max_tokens("dialogue")
        < narration_max_tokens("epic")
    )
