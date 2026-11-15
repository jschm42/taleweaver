"""Recruiting companions with the Recruit action: instant, with a wanted item, or script-only."""

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.companion_recruit import recruit_companion_command
from backend.engine.blueprint import analyze_blueprint
from backend.engine.interaction.command_parser import CommandParser
from backend.engine.party.companion_config import normalize_companion
from backend.engine.party.party_state import read_party
from backend.engine.party.party_view import mark_recruitable_npcs
from backend.engine.scripting.item_transfer import ref_id
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal
from tests.test_npc_give import _seed_world


async def _make_companion(db, recruit: dict, **hooks: str) -> None:
    res = await db.execute(select(WorldEntity).where(WorldEntity.id == "BRAM"))
    bram = res.scalars().first()
    bram.metadata_json = {
        "companion": normalize_companion({"recruitable": True, **recruit}),
        **hooks,
    }
    await db.commit()


def _member(manager) -> bool:
    return read_party(manager.state.entity_states).is_member("BRAM")


def test_recruit_command_maps_to_trigger_tag():
    # Act
    response = CommandParser.parse_command(None, "/recruit BRAM | IRON_KEY")

    # Assert
    assert response == "[TRIGGER_COMPANION_RECRUIT] BRAM | IRON_KEY"


def test_item_mode_without_item_falls_back_to_instant():
    # Act
    config = normalize_companion({"recruit_mode": "item", "recruit_item_id": ""})

    # Assert
    assert config["recruit_mode"] == "INSTANT"
    assert config["recruit_item_id"] == ""


def test_blueprint_recruit_keys_fill_the_companion_block():
    # Arrange
    text = (
        "[Scene: TAVERN] Tavern\nSmoky.\n[Item: RUM] Bottle of rum\nin: TAVERN\n"
        "[NPC: GRULL] Grull\nin: TAVERN\ncompanion: yes\nrecruit: item\nrecruit_item: RUM\n"
        "recruit_hint: Bring me something to drink.\non_recruit_fail_text: Grull shakes his head.\n"
    )

    # Act
    blueprint, issues = analyze_blueprint(text)

    # Assert
    npc = next(block for block in blueprint.blocks if block.kind == "npc")
    assert npc.fields["companion.recruit_mode"].value == "ITEM"
    assert npc.fields["companion.recruit_item_id"].value == "RUM"
    assert npc.fields["companion.recruit_hint"].value == "Bring me something to drink."
    assert npc.fields["on_recruit_failure_text"].value == "Grull shakes his head."
    assert issues == []


def test_recruitable_npcs_are_flagged_without_the_wanted_item():
    # Arrange
    entities = [
        {
            "id": "GRULL",
            "metadata_json": {"companion": {"recruit_mode": "ITEM", "recruit_item_id": "RUM"}},
        },
        {"id": "SAGE", "metadata_json": {"companion": {"recruitable": True}}},
        {"id": "MATE", "metadata_json": {"companion": {"recruit_mode": "INSTANT"}}},
    ]
    states = {"__party__": {"active_id": "MATE", "recruited": ["MATE"]}}

    # Act
    mark_recruitable_npcs(entities, states)

    # Assert
    grull, sage, mate = entities
    assert grull["is_recruitable"] is True
    assert grull["recruit_mode"] == "ITEM"
    assert "recruit_item_id" not in grull
    assert "is_recruitable" not in sage
    assert "is_recruitable" not in mate


@pytest.mark.asyncio
async def test_wrong_item_fails_and_keeps_the_item():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)
        await _make_companion(
            db,
            {"recruit_mode": "ITEM", "recruit_item_id": "IRON_KEY"},
            on_recruit_failure_text="Bram snorts. 'A sword? I have plenty.'",
        )

        # Act
        outcome = await recruit_companion_command(manager, "Bram Ironhand | Sword")

        # Assert
        assert [text for _role, text in outcome.events] == [
            "Bram snorts. 'A sword? I have plenty.'"
        ]
        assert outcome.reaction_prompt is None
        assert not _member(manager)
        assert {ref_id(item) for item in manager.avatar.inventory} == {"SWORD", "IRON_KEY"}


@pytest.mark.asyncio
async def test_wanted_item_recruits_and_the_npc_keeps_it():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)
        await _make_companion(
            db,
            {"recruit_mode": "ITEM", "recruit_item_id": "IRON_KEY"},
            on_recruit_success_text="Bram pockets the key and grabs his hammer.",
        )

        # Act
        outcome = await recruit_companion_command(manager, "BRAM | iron key")
        await db.commit()

        # Assert
        texts = [text for _role, text in outcome.events]
        assert "Bram Ironhand joins your party." in texts
        assert texts[-1] == "Bram pockets the key and grabs his hammer."
        assert outcome.reaction_prompt is None
        assert _member(manager)
        assert [ref_id(item) for item in manager.avatar.inventory] == ["SWORD"]
        assert "IRON_KEY" in {
            ref_id(item) for item in manager.state.entity_states["BRAM"]["inventory"]
        }


@pytest.mark.asyncio
async def test_instant_recruit_without_hooks_chains_a_gm_reaction():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)
        await _make_companion(db, {"recruit_mode": "INSTANT"})

        # Act
        outcome = await recruit_companion_command(manager, "BRAM")

        # Assert
        assert _member(manager)
        assert outcome.reaction_prompt.startswith("[COMPANION_RECRUITED]")


@pytest.mark.asyncio
async def test_script_only_companion_refuses_the_recruit_action():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)
        await _make_companion(db, {})

        # Act
        outcome = await recruit_companion_command(manager, "BRAM")

        # Assert
        assert [text for _role, text in outcome.events] == [
            "Bram Ironhand does not want to join you."
        ]
        assert not _member(manager)


def test_replaced_companion_is_offered_again_without_its_price():
    # Arrange
    wanted = {
        "companion": {"recruit_mode": "ITEM", "recruit_item_id": "RUM", "recruit_hint": "Rum!"}
    }
    entities = [
        {"id": "GRULL", "metadata_json": wanted},
        {"id": "MATE", "metadata_json": {"companion": {"recruitable": True}}},
    ]
    states = {"__party__": {"active_id": "NEW_ONE", "recruited": ["GRULL", "MATE", "NEW_ONE"]}}

    # Act
    mark_recruitable_npcs(entities, states)

    # Assert
    grull, mate = entities
    assert (grull["is_recruitable"], grull["recruit_mode"], grull["recruit_hint"]) == (
        True,
        "INSTANT",
        "",
    )
    assert mate["is_recruitable"] is True  # script-recruited the first time, back for free


@pytest.mark.asyncio
async def test_replaced_companion_rejoins_without_an_item():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)
        await _make_companion(
            db,
            {"recruit_mode": "ITEM", "recruit_item_id": "IRON_KEY"},
            on_recruit_success_text="Bram pockets the key.",
        )
        manager.state.entity_states = {
            **(manager.state.entity_states or {}),
            "__party__": {"active_id": "OTHER", "recruited": ["BRAM", "OTHER"]},
        }

        # Act
        outcome = await recruit_companion_command(manager, "BRAM")

        # Assert
        assert [text for _role, text in outcome.events][-1] == "Bram Ironhand rejoins your party."
        assert read_party(manager.state.entity_states).active_id == "BRAM"
        assert outcome.reaction_prompt.startswith("[COMPANION_RECRUITED]")
        assert {ref_id(item) for item in manager.avatar.inventory} == {"SWORD", "IRON_KEY"}


@pytest.mark.asyncio
async def test_paid_companion_rejoins_for_free_after_being_dismissed():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)
        await _make_companion(db, {"recruit_mode": "ITEM", "recruit_item_id": "IRON_KEY"})
        await recruit_companion_command(manager, "BRAM | Iron Key")
        party = dict(manager.state.entity_states["__party__"])
        manager.state.entity_states = {
            **manager.state.entity_states,
            "__party__": {**party, "active_id": None, "recruited": []},
        }

        # Act
        outcome = await recruit_companion_command(manager, "BRAM")

        # Assert
        assert [text for _role, text in outcome.events][-1] == "Bram Ironhand rejoins your party."
        assert _member(manager)
        assert manager.state.entity_states["BRAM"]["recruit_paid"] is True
