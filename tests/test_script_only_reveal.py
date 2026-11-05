"""Hidden entities with the reveal rule ``script`` are revealed only by scripts."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.engine.interaction.location_context import build_hidden_entities_context
from backend.engine.rules.crafting_recipes import craft_only_result_ids
from backend.engine.rules.reveal_policy import (
    has_discoverable_reveal_rule,
    is_script_only_reveal,
)
from backend.engine.rules.rule_engine import GameEvent, WorldEntityUpdate
from backend.models.adventure import Adventure
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal

SCENE = "PAD_ROOM"


def _npc(entity_id: str, session_id: str, adv_id: str, reveal_rule: str | None) -> WorldEntity:
    return WorldEntity(
        id=entity_id,
        session_id=session_id,
        template_id=adv_id,
        name=entity_id.title(),
        description="Stands on the raised metal platform.",
        entity_type="NPC",
        current_scene_id=SCENE,
        spatial_position="standing on the raised metal platform",
        reveal_rule=reveal_rule,
        is_hidden=True,
    )


async def _manager(db, suffix: str) -> GameTurnManager:
    user = User(id=f"u-sor-{suffix}", username=f"sor{suffix}", hashed_password="x")
    db.add(user)
    await db.flush()
    adv = Adventure(id=f"adv-sor-{suffix}", title="Pad", owner_id=user.id, origin_id=SCENE)
    db.add(adv)
    await db.flush()
    state = SessionState(
        session_id=f"s-sor-{suffix}",
        adventure_id=adv.id,
        user_id=user.id,
        current_scene_id=SCENE,
        entity_states={},
    )
    avatar = Avatar(id=f"av-sor-{suffix}", user_id=user.id, template_id=adv.id, name="Alex")
    db.add_all(
        [
            state,
            avatar,
            _npc("STOWAWAY", state.session_id, adv.id, "Script"),
            _npc("LURKER", state.session_id, adv.id, None),
        ]
    )
    await db.commit()
    logic = GameTurnManager(db=db, game_id=state.session_id, user=user)
    logic.state = state
    logic.adventure = adv
    logic.avatar = avatar
    return logic


def test_policy_recognizes_reserved_value():
    # Arrange
    values = ["script", " SCRIPT ", "Script"]

    # Act / Assert
    assert all(is_script_only_reveal(v) for v in values)
    assert not is_script_only_reveal("If the player uses the script terminal")
    assert not is_script_only_reveal(None)
    assert has_discoverable_reveal_rule("If the player searches the desk")
    assert not has_discoverable_reveal_rule("script")
    assert not has_discoverable_reveal_rule("")


def test_gm_hidden_context_omits_script_only_entities():
    # Arrange
    hidden = [
        SimpleNamespace(
            id="STOWAWAY",
            name="Stowaway",
            spatial_position="",
            reveal_rule="script",
            entity_type="NPC",
        ),
        SimpleNamespace(
            id="LURKER", name="Lurker", spatial_position="", reveal_rule="", entity_type="NPC"
        ),
    ]

    # Act
    block = build_hidden_entities_context(hidden)
    only_script = build_hidden_entities_context(hidden[:1])

    # Assert
    assert "LURKER" in block
    assert "STOWAWAY" not in block
    assert only_script == ""


def test_script_only_craft_result_stays_craft_only():
    # Arrange
    recipe = SimpleNamespace(
        id="RECIPE",
        item_type="CONSTRUCTABLE",
        reveals_item_id=None,
        reveal_rule=None,
        metadata_json={"result_item_ids": ["GADGET"]},
    )
    gadget = SimpleNamespace(
        id="GADGET",
        item_type="PICKABLE",
        reveals_item_id=None,
        reveal_rule="script",
        metadata_json={},
    )

    # Act
    result = craft_only_result_ids([recipe, gadget])

    # Assert
    assert result == {"GADGET"}


@pytest.mark.asyncio
async def test_discovery_never_reveals_script_only_entity():
    async with TestSessionLocal() as db:
        # Arrange
        logic = await _manager(db, "1")
        event = GameEvent(discovered_entity_ids=["STOWAWAY"])

        # Act
        with (
            patch("backend.core.llm_router.GameMasterLLM.__init__", return_value=None),
            patch("backend.core.llm_router.GameMasterLLM.aexecute_complex_task") as mock_llm,
        ):
            # The model even names the script-only entity: it is no candidate, so it stays hidden.
            mock_llm.return_value = {"discovered_ids": ["LURKER", "STOWAWAY"]}
            messages = await logic._enforce_hidden_entity_reveal(
                event, "I inspect the raised metal platform"
            )

        # Assert
        revealed = {up.entity_id for up in event.updated_entities or [] if up.is_hidden is False}
        assert "STOWAWAY" not in revealed
        assert "LURKER" in revealed
        assert messages == ["Revealed Lurker"]


@pytest.mark.asyncio
async def test_gm_reveal_of_script_only_entity_is_blocked():
    async with TestSessionLocal() as db:
        # Arrange
        logic = await _manager(db, "2")
        event = GameEvent(
            discovered_entity_ids=["STOWAWAY", "LURKER"],
            updated_entities=[
                WorldEntityUpdate(entity_id="STOWAWAY", is_hidden=False, notes="appears"),
                WorldEntityUpdate(entity_id="LURKER", is_hidden=False),
            ],
        )

        # Act
        await logic.guardrails._block_script_only_reveals(event)

        # Assert
        by_id = {up.entity_id: up for up in event.updated_entities}
        assert by_id["STOWAWAY"].is_hidden is None
        assert by_id["STOWAWAY"].notes == "appears"
        assert by_id["LURKER"].is_hidden is False
        assert event.discovered_entity_ids == ["LURKER"]
