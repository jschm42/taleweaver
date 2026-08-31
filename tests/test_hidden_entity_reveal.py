import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from backend.models.world_entity import WorldEntity
from backend.models.adventure import Adventure
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.avatar import Avatar
from backend.engine.rule_engine import GameEvent, WorldEntityUpdate
from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from tests.conftest import TestSessionLocal


@pytest.mark.asyncio
async def test_hidden_entity_revealed_on_location_search():
    async with TestSessionLocal() as db:
        user = User(id="test-u1", username="testuser", hashed_password="mockhash")
        db.add(user)
        await db.flush()

        adv = Adventure(
            id="test-adv-reveal",
            title="Kitchen Crisis",
            owner_id=user.id,
            origin_id="LIVING_ROOM"
        )
        db.add(adv)
        await db.flush()

        state = SessionState(
            session_id="test-session-reveal",
            adventure_id=adv.id,
            user_id=user.id,
            current_scene_id="LIVING_ROOM",
            entity_states={}
        )
        db.add(state)

        avatar = Avatar(
            id="test-av-reveal",
            user_id=user.id,
            template_id=adv.id,
            name="Jamie Miller",
            inventory=[]
        )
        db.add(avatar)

        couch = WorldEntity(
            id="COUCH",
            session_id=state.session_id,
            template_id=adv.id,
            name="Couch",
            description="A soft couch with cushions.",
            entity_type="OBJECT",
            item_type="STATIC",
            current_scene_id="LIVING_ROOM",
            is_hidden=False
        )
        batteries = WorldEntity(
            id="LOOSE_BATTERIES",
            session_id=state.session_id,
            template_id=adv.id,
            name="Loose Batteries",
            description="Two AA batteries.",
            entity_type="OBJECT",
            item_type="PICKABLE",
            current_scene_id="LIVING_ROOM",
            spatial_position="buried deep between the ##COUCH cushions",
            reveal_rule="If the protagonist searches the ##COUCH cushions",
            is_hidden=True
        )
        db.add_all([couch, batteries])
        await db.commit()

        logic = GameTurnManager(
            db=db,
            game_id=state.session_id,
            user=user
        )
        logic.state = state
        logic.adventure = adv
        logic.avatar = avatar

        event = GameEvent(discovered_entity_ids=["LOOSE_BATTERIES"])
        # Test: Player searches sofa in German, LLM generates discovered_entity_ids
        await logic._enforce_hidden_entity_reveal(event, "durchsuche sofa")

        assert event.updated_entities is not None
        assert len(event.updated_entities) == 1
        assert event.updated_entities[0].entity_id == "LOOSE_BATTERIES"
        assert event.updated_entities[0].is_hidden is False


@pytest.mark.asyncio
async def test_hidden_entity_revealed_via_discovered_entity_ids():
    async with TestSessionLocal() as db:
        user = User(id="test-u2", username="testuser2", hashed_password="mockhash")
        db.add(user)
        await db.flush()

        adv = Adventure(
            id="test-adv-reveal-2",
            title="Kitchen Crisis",
            owner_id=user.id,
            origin_id="LIVING_ROOM"
        )
        db.add(adv)
        await db.flush()

        state = SessionState(
            session_id="test-session-reveal-2",
            adventure_id=adv.id,
            user_id=user.id,
            current_scene_id="LIVING_ROOM",
            entity_states={}
        )
        db.add(state)

        avatar = Avatar(
            id="test-av-reveal-2",
            user_id=user.id,
            template_id=adv.id,
            name="Jamie Miller",
            inventory=[]
        )
        db.add(avatar)

        batteries = WorldEntity(
            id="LOOSE_BATTERIES",
            session_id=state.session_id,
            template_id=adv.id,
            name="Loose Batteries",
            description="Two AA batteries.",
            entity_type="OBJECT",
            item_type="PICKABLE",
            current_scene_id="LIVING_ROOM",
            is_hidden=True
        )
        db.add(batteries)
        await db.commit()

        logic = GameTurnManager(
            db=db,
            game_id=state.session_id,
            user=user
        )
        logic.state = state
        logic.adventure = adv
        logic.avatar = avatar

        event = GameEvent(narrative_description="You find a pair of Loose Batteries behind the drawer.", discovered_entity_ids=["LOOSE_BATTERIES"])
        await logic._enforce_hidden_entity_reveal(event, "i look around")

        assert event.updated_entities is not None
        assert any(up.entity_id == "LOOSE_BATTERIES" and up.is_hidden is False for up in event.updated_entities)

@pytest.mark.asyncio
async def test_hidden_entity_revealed_via_llm_fallback():
    async with TestSessionLocal() as db:
        user = User(id="test-u3", username="testuser3", hashed_password="mockhash")
        db.add(user)
        await db.flush()

        adv = Adventure(
            id="test-adv-reveal-3",
            title="Kitchen Crisis",
            owner_id=user.id,
            origin_id="LIVING_ROOM"
        )
        db.add(adv)
        await db.flush()

        state = SessionState(
            session_id="test-session-reveal-3",
            adventure_id=adv.id,
            user_id=user.id,
            current_scene_id="LIVING_ROOM",
            entity_states={}
        )
        db.add(state)

        avatar = Avatar(
            id="test-av-reveal-3",
            user_id=user.id,
            template_id=adv.id,
            name="Jamie Miller",
            inventory=[]
        )
        db.add(avatar)

        batteries = WorldEntity(
            id="LOOSE_BATTERIES",
            session_id=state.session_id,
            template_id=adv.id,
            name="Loose Batteries",
            description="Two AA batteries.",
            entity_type="OBJECT",
            item_type="PICKABLE",
            current_scene_id="LIVING_ROOM",
            is_hidden=True
        )
        db.add(batteries)
        await db.commit()

        logic = GameTurnManager(
            db=db,
            game_id=state.session_id,
            user=user
        )
        logic.state = state
        logic.adventure = adv
        logic.avatar = avatar

        # Event does NOT have discovered_entity_ids populated
        event = GameEvent(narrative_description="Du findest Batterien.")

        with patch("backend.core.llm_router.GameMasterLLM.__init__", return_value=None), \
             patch("backend.core.llm_router.GameMasterLLM.aexecute_complex_task") as mock_aexecute:
            mock_aexecute.return_value = {"discovered": True}
            await logic._enforce_hidden_entity_reveal(event, "suche batterien")

        assert event.updated_entities is not None
        assert any(up.entity_id == "LOOSE_BATTERIES" and up.is_hidden is False for up in event.updated_entities)
