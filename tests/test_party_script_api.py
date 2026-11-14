"""``tw.party``: recruiting, dismissing and steering companions from scripts."""

import pytest

from backend.engine.interaction.trigger_service import TriggerService
from backend.engine.party.party_ops import apply_party_ops
from backend.engine.party.party_state import PARTY_KEY, read_party
from backend.engine.scripting.context import GameContext
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity, WorldScene
from tests.conftest import TestSessionLocal


def _npc(name: str, companion=None) -> dict:
    return {"name": name, "entity_type": "NPC", "metadata_json": {"companion": companion}}


def _context(party: dict | None = None) -> GameContext:
    return GameContext(
        current_scene_id="HALL",
        entities={
            "NPC_LARA": _npc("Lara", {"recruitable": True, "tactics": "SUPPORT"}),
            "NPC_BORIS": _npc("Boris"),
            "NPC_STATUE": _npc("Statue", {"recruitable": False}),
        },
        party=party,
    )


def test_recruit_by_name_records_an_op_and_reads_back():
    # Arrange
    tw = _context()

    # Act
    recruited = tw.party.recruit("lara")

    # Assert
    assert recruited is True
    assert tw.party.active == "NPC_LARA"
    assert tw.party.members == ["NPC_LARA"]
    assert tw.party.following is True
    assert tw.party.tactics_of() == "SUPPORT"  # from the NPC's companion settings
    assert tw.party.companion.name == "Lara"
    assert tw.changeset.party_ops == [{"op": "recruit", "npc_id": "NPC_LARA", "tactics": None}]
    assert tw.changeset.has_changes


def test_recruit_refuses_unknown_unrecruitable_and_bad_tactics():
    # Arrange
    tw = _context()

    # Act
    unknown = tw.party.recruit("NOBODY")
    statue = tw.party.recruit("NPC_STATUE")
    bad_tactics = tw.party.recruit("NPC_BORIS", tactics="berserk")

    # Assert
    assert (unknown, statue, bad_tactics) == (False, False, False)
    assert tw.changeset.party_ops == []
    errors = list(tw.changeset.system_messages)
    assert any("tw.party.recruit" in e and "NOBODY" in e for e in errors)
    assert any("berserk" in e for e in errors)


def test_wait_follow_switch_tactics_and_dismiss():
    # Arrange: Lara and Boris recruited, Boris active
    party = {"active_id": "NPC_BORIS", "recruited": ["NPC_LARA", "NPC_BORIS"], "following": True}
    tw = _context(party)

    # Act
    tw.party.wait()
    waiting = tw.party.following
    tw.party.follow()
    switched = tw.party.set_active(tw.npcs.get("NPC_LARA"))
    tactics_set = tw.party.set_tactics("defensive")
    dismissed = tw.party.dismiss("Boris")

    # Assert
    assert waiting is False
    assert tw.party.following is True
    assert switched and tactics_set and dismissed
    assert tw.party.active == "NPC_LARA"
    assert tw.party.tactics_of("NPC_LARA") == "DEFENSIVE"
    assert tw.party.is_member("NPC_BORIS") is False
    assert tw.party.tactics_of("NPC_BORIS") is None


def test_party_ops_replay_onto_entity_states():
    # Arrange
    tw = _context()
    tw.party.recruit("NPC_LARA")
    tw.party.recruit("NPC_BORIS", tactics="offensive")
    tw.party.wait()
    states: dict = {}

    # Act
    apply_party_ops(states, tw.changeset.party_ops)

    # Assert
    party = read_party(states)
    assert party.active_id == "NPC_BORIS"
    assert party.recruited == ["NPC_LARA", "NPC_BORIS"]
    assert party.following is False
    assert party.tactics == {"NPC_BORIS": "OFFENSIVE"}


def test_dismissing_the_last_member_removes_the_party_key():
    # Arrange
    states = {PARTY_KEY: {"active_id": "NPC_LARA", "recruited": ["NPC_LARA"]}}
    tw = _context(states[PARTY_KEY])

    # Act
    tw.party.dismiss()
    apply_party_ops(states, tw.changeset.party_ops)

    # Assert
    assert tw.party.is_empty
    assert PARTY_KEY not in states


@pytest.mark.asyncio
async def test_script_recruits_and_teleports_with_the_new_companion(setup_test_db):
    # Arrange: no party yet; Lara stands next to the player
    session_id = "sess_party_script"
    async with TestSessionLocal() as db:
        db.add_all(
            [
                WorldScene(id="HALL", session_id=session_id, label="Hall", description=""),
                WorldScene(id="CELLAR", session_id=session_id, label="Cellar", description=""),
                WorldEntity(
                    id="NPC_LARA",
                    session_id=session_id,
                    entity_type="NPC",
                    name="Lara",
                    description="A rogue.",
                    current_scene_id="HALL",
                ),
            ]
        )
        await db.commit()
        state = SessionState(session_id=session_id, current_scene_id="HALL", entity_states={})

        # Act
        await TriggerService.execute_trigger(
            db,
            state,
            "on_interact",
            "LEVER",
            script_code="tw.party.recruit('NPC_LARA')\ntw.scene.teleport('CELLAR')",
        )

        # Assert: the party is stored and the fresh recruit came along
        assert read_party(state.entity_states).active_id == "NPC_LARA"
        assert state.current_scene_id == "CELLAR"
        assert state.entity_states["NPC_LARA"]["current_scene_id"] == "CELLAR"
