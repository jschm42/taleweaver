"""Scripts damage, heal and defeat NPCs (tw.npcs.get(ID).damage / heal / kill)."""

import pytest
from sqlalchemy import select

from backend.engine.scripting.runner import ScriptRunner
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal
from tests.test_script_turn_integration import _build_test_turn_manager


async def _goblin_manager(db, session_id: str):
    manager = await _build_test_turn_manager(db, [], session_id=session_id)
    db.add(
        WorldEntity(
            id="GOBLIN",
            session_id=session_id,
            entity_type="NPC",
            name="Goblin",
            description="A small goblin.",
            current_scene_id="SCENE_START",
            hp=30,
            max_hp=30,
        )
    )
    await db.commit()
    return manager


async def _run_and_apply(manager, code: str) -> list:
    ctx = await manager._build_script_context()
    ScriptRunner([]).execute_code(code, {"tw": ctx}, script_id="test")
    return await manager._apply_script_changeset(ctx.changeset)


async def _goblin(db) -> WorldEntity:
    return (await db.execute(select(WorldEntity).where(WorldEntity.id == "GOBLIN"))).scalar_one()


@pytest.mark.asyncio
async def test_script_damage_lowers_npc_hp(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _goblin_manager(db, "sess_npc_dmg")

        # Act
        await _run_and_apply(manager, "tw.npcs.get('GOBLIN').damage(12)")
        await db.commit()

        # Assert
        assert (await _goblin(db)).hp == 18


@pytest.mark.asyncio
async def test_script_heal_stops_at_max_hp(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _goblin_manager(db, "sess_npc_heal")
        await _run_and_apply(manager, "tw.npcs.get('GOBLIN').damage(10)")
        await db.commit()

        # Act
        await _run_and_apply(manager, "tw.npcs.get('GOBLIN').heal(50)")
        await db.commit()

        # Assert
        assert (await _goblin(db)).hp == 30


@pytest.mark.asyncio
async def test_lethal_script_damage_defeats_the_npc(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _goblin_manager(db, "sess_npc_kill")

        # Act
        await _run_and_apply(manager, "tw.npcs.get('GOBLIN').damage(99)")
        await db.commit()

        # Assert
        goblin = await _goblin(db)
        assert goblin.hp == 0
