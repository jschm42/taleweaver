import pytest
from httpx import AsyncClient
from sqlalchemy import select
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.adventure_template import AdventureTemplate
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio

async def test_session_remains_after_adventure_deletion(auth_client: AsyncClient):
    """
    Verifies that deleting an adventure template does NOT delete its associated game sessions.
    Also verifies that the sessions are correctly detached (template_id set to None).
    """
    # 1. Create an adventure template
    # We'll create it directly in the DB for speed, or via API if we want full E2E
    async with TestSessionLocal() as db:
        from backend.models.user import User
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()
        
        template = AdventureTemplate(
            id="test-template",
            owner_id=user.id,
            title="Test Adventure",
            is_ready=True
        )
        db.add(template)
        await db.commit()

    # 2. Start a session for this template via API
    start_resp = await auth_client.post("/api/adventures/test-template/sessions/start")
    assert start_resp.status_code == 201
    game_id = start_resp.json()["game_id"]

    # 3. Verify session exists in API list
    list_resp = await auth_client.get("/api/adventures/sessions")
    assert list_resp.status_code == 200
    sessions = list_resp.json()
    assert any(s["game_id"] == game_id for s in sessions)
    
    session_data = next(s for s in sessions if s["game_id"] == game_id)
    assert session_data["template_id"] == "test-template"

    # 4. Delete the adventure template via API
    del_resp = await auth_client.delete("/api/adventures/test-template")
    assert del_resp.status_code == 200

    # 5. Verify the template is gone but the session survives in the DB
    async with TestSessionLocal() as db:
        template_in_db = await db.get(AdventureTemplate, "test-template")
        assert template_in_db is None
        
        session_in_db = await db.get(GameSession, game_id)
        assert session_in_db is not None
        assert session_in_db.template_id is None # Explicitly detached
        
        state_in_db = await db.execute(select(SessionState).where(SessionState.session_id == game_id))
        state = state_res = state_in_db.scalars().first()
        assert state is not None
        assert state.template_id is None # Explicitly detached

    # 6. Verify the session still appears in the API list and has NULL template_id
    list_resp_after = await auth_client.get("/api/adventures/sessions")
    assert list_resp_after.status_code == 200
    sessions_after = list_resp_after.json()
    assert any(s["game_id"] == game_id for s in sessions_after)
    
    session_after = next(s for s in sessions_after if s["game_id"] == game_id)
    assert session_after["template_id"] is None
    assert session_after["adventure_id"] is None
    assert session_after["adventure_title"] == "Test Adventure" # Preserved from GameSession record
