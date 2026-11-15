"""Quest items stay with the protagonist: no handover to NPCs or companions, no GM removal."""

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.npc_give import give_items_to_npc
from backend.engine.adventures.adventure_exporter import _normalize_exported_object_metadata
from backend.engine.blueprint import analyze_blueprint
from backend.engine.manifest_apply.objects import item_numbers, object_metadata
from backend.engine.rules.rule_engine import GameEvent
from backend.engine.world.world_object_schema import WorldObjectSchema
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal
from tests.test_npc_give import _seed_world


async def _mark_quest_item(db, item_id: str) -> None:
    res = await db.execute(select(WorldEntity).where(WorldEntity.id == item_id))
    row = res.scalars().first()
    row.metadata_json = {**(row.metadata_json or {}), "quest_item": True}
    await db.commit()


def test_blueprint_quest_key_sets_quest_item():
    # Arrange
    text = "[Scene: HARBOR] Harbor\nA pier.\n[Item: LETTER] Sealed letter\nin: HARBOR\nquest: yes\n"

    # Act
    blueprint, _issues = analyze_blueprint(text)

    # Assert
    item = next(block for block in blueprint.blocks if block.kind == "item")
    assert item.fields["quest_item"].value is True


def test_generated_quest_item_survives_applier_and_export():
    # Arrange
    generated = WorldObjectSchema.model_json_schema()["properties"]
    obj = {"id": "LETTER", "name": "Sealed letter", "item_type": "DEFAULT", "quest_item": True}

    # Act
    metadata = object_metadata(obj, item_numbers(obj, {}))
    exported = {"item_type": "DEFAULT", "metadata_json": dict(metadata)}
    _normalize_exported_object_metadata(exported)
    reimported = object_metadata(exported, item_numbers(exported, {}))

    # Assert
    assert "quest_item" in generated
    assert metadata["quest_item"] is True
    assert exported["quest_item"] is True
    assert reimported["quest_item"] is True


def test_false_quest_item_is_not_stored():
    # Arrange
    obj = {"id": "ROCK", "name": "Rock", "item_type": "DEFAULT", "quest_item": False}

    # Act
    metadata = object_metadata(obj, item_numbers(obj, {}))

    # Assert
    assert "quest_item" not in metadata


@pytest.mark.asyncio
async def test_npc_refuses_quest_item_but_takes_the_rest():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)
        await _mark_quest_item(db, "IRON_KEY")

        # Act
        outcome = await give_items_to_npc(manager, "Bram Ironhand | Sword, Iron Key")

        # Assert
        texts = [text for _role, text in outcome.events]
        assert texts[0] == "You give Sword to Bram Ironhand."
        assert texts[1] == "Iron Key is too important for your quest to give away."
        assert [item["id"] for item in manager.avatar.inventory] == ["IRON_KEY"]


@pytest.mark.asyncio
async def test_only_quest_items_means_no_handover_and_no_reaction():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)
        await _mark_quest_item(db, "IRON_KEY")

        # Act
        outcome = await give_items_to_npc(manager, "Bram Ironhand | Iron Key")

        # Assert
        assert [text for _role, text in outcome.events] == [
            "Iron Key is too important for your quest to give away."
        ]
        assert outcome.reaction_prompt is None
        assert {item["id"] for item in manager.avatar.inventory} == {"SWORD", "IRON_KEY"}


@pytest.mark.asyncio
async def test_gm_cannot_remove_a_quest_item():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)
        await _mark_quest_item(db, "IRON_KEY")
        event = GameEvent(removed_inventory_item_ids=["IRON_KEY", "SWORD"])

        # Act
        violations = await manager.guardrails._enforce_inventory_removals(
            event, "I hand the iron key and the sword to the smith"
        )

        # Assert
        assert event.removed_inventory_item_ids == ["SWORD"]
        assert len(violations) == 1
        assert "Iron Key is a quest item" in violations[0]
