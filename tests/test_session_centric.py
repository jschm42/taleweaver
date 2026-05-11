
import pytest
from sqlalchemy import select

from backend.api.routes.adventures.sessions import start_session_for_template
from backend.models.adventure_template import AdventureTemplate
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldScene

pytestmark = pytest.mark.asyncio

async def test_session_isolation_from_template(auth_client, setup_test_db):
    """Verifies that a session is a full snapshot and remains playable if the template is modified/deleted."""
    from tests.conftest import TestSessionLocal
    
    async with TestSessionLocal() as db:
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()
        
        # 1. Create a Template
        adv = AdventureTemplate(
            id="template-1",
            owner_id=user.id,
            title="Snapshot Test",
            plot="Original Plot",
            rules="Original Rules",
            is_ready=True
        )
        db.add(adv)
        
        scene = WorldScene(id="SCENE_A", template_id="template-1", label="Original Scene", description="Original Desc")
        db.add(scene)
        
        npc = WorldEntity(id="NPC_A", template_id="template-1", entity_type="NPC", name="Original NPC", description="Original Desc", current_scene_id="SCENE_A")
        db.add(npc)
        
        await db.commit()
        
        # 2. Start Session
        result = await start_session_for_template("template-1", db, user)
        session_id = result["game_id"]
        
        # 3. Modify Template
        adv.plot = "CHANGED PLOT"
        scene.label = "CHANGED SCENE"
        npc.name = "CHANGED NPC"
        await db.commit()
        
        # 4. Verify Session still has original data
        state_res = await db.execute(select(SessionState).where(SessionState.session_id == session_id))
        state = state_res.scalars().first()
        assert state.plot == "Original Plot"
        
        scene_res = await db.execute(select(WorldScene).where(WorldScene.session_id == session_id, WorldScene.id == "SCENE_A"))
        sess_scene = scene_res.scalars().first()
        assert sess_scene.label == "Original Scene"
        
        npc_res = await db.execute(select(WorldEntity).where(WorldEntity.session_id == session_id, WorldEntity.id == "NPC_A"))
        sess_npc = npc_res.scalars().first()
        assert sess_npc.name == "Original NPC"
        
        # 5. Delete Template and check session integrity
        await db.delete(adv)
        await db.commit()
        
        # SessionState should still exist (it has template_id but it's just a ref, the data is in state)
        # Note: If there's a FK constraint it might fail, but let's see. 
        # In our models, template_id is often just a string.
        
        db.expire_all()
        state_res = await db.execute(select(SessionState).where(SessionState.session_id == session_id))
        state = state_res.scalars().first()
        assert state is not None
        assert state.plot == "Original Plot"

async def test_session_stat_cloning(auth_client, setup_test_db):
    """Verifies that NPC stats (HP, Mana, Stamina) are correctly cloned into the session."""
    from tests.conftest import TestSessionLocal
    
    async with TestSessionLocal() as db:
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()
        
        adv = AdventureTemplate(id="temp-stat", owner_id=user.id, title="Stat Test", is_ready=True)
        db.add(adv)
        
        npc = WorldEntity(
            id="NPC_STAT", template_id="temp-stat", entity_type="NPC", name="Beefy NPC",
            description="Beefy NPC", current_scene_id="START",
            hp=500, max_hp=500, stamina=300, max_stamina=300, mana=100, max_mana=100
        )
        db.add(npc)
        await db.commit()
        
        result = await start_session_for_template("temp-stat", db, user)
        session_id = result["game_id"]
        
        npc_res = await db.execute(select(WorldEntity).where(WorldEntity.session_id == session_id, WorldEntity.id == "NPC_STAT"))
        sess_npc = npc_res.scalars().first()
        
        assert sess_npc.hp == 500
        assert sess_npc.stamina == 300
        assert sess_npc.mana == 100
