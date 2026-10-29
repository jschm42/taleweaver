"""on_interact targets: GM-reported entities plus reachable entities named in the message."""

import pytest

from backend.engine.interaction.interaction_targets import (
    interacted_entity_ids,
    mentioned_entity_ids,
)
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal
from tests.test_game_loop import _seed_game_context

CANDIDATES = [("TICKING_BOMB", "Ticking Bomb"), ("WIRE_CUTTERS", "Wire Cutters"), ("OX", "Ox")]


def test_context_menu_command_matches_entity_name():
    # Act
    ids = mentioned_entity_ids("Inspect Ticking Bomb", CANDIDATES)

    # Assert
    assert ids == ["TICKING_BOMB"]


def test_entity_id_and_spaced_id_match():
    # Act
    by_id = mentioned_entity_ids("use WIRE_CUTTERS", CANDIDATES)
    by_spaced_id = mentioned_entity_ids("Push wire cutters", CANDIDATES)

    # Assert
    assert by_id == ["WIRE_CUTTERS"]
    assert by_spaced_id == ["WIRE_CUTTERS"]


def test_partial_words_and_short_names_do_not_match():
    # Act
    ids = mentioned_entity_ids("I look at the bombastic oxygen tank", CANDIDATES)

    # Assert
    assert ids == []


@pytest.mark.asyncio
async def test_resolver_merges_reported_ids_and_skips_unreachable_entities():
    async with TestSessionLocal() as db:
        # Arrange
        _user, _adv, _avatar, state = await _seed_game_context(db)
        db.add_all([
            WorldEntity(id="TICKING_BOMB", session_id=state.session_id, entity_type="OBJECT",
                        name="Ticking Bomb", description="A bomb.", current_scene_id="START"),
            WorldEntity(id="HIDDEN_SAFE", session_id=state.session_id, entity_type="OBJECT",
                        name="Hidden Safe", description="A safe.", current_scene_id="START",
                        is_hidden=True),
            WorldEntity(id="FAR_LEVER", session_id=state.session_id, entity_type="OBJECT",
                        name="Far Lever", description="A lever.", current_scene_id="ELSEWHERE"),
        ])  # fmt: skip
        await db.commit()

        # Act
        ids = await interacted_entity_ids(
            db,
            state,
            "Inspect Ticking Bomb, the Hidden Safe and the Far Lever",
            ["ticking_bomb", "DOOR_1"],
        )

        # Assert
        assert ids == ["TICKING_BOMB", "DOOR_1"]
