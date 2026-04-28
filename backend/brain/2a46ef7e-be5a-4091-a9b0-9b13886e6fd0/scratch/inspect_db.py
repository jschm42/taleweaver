import asyncio
from sqlalchemy import select
from backend.core.database import engine, AsyncSessionLocal
from backend.models.game_session import GameSession
from backend.models.adventure_template import AdventureTemplate
from backend.models.session_state import SessionState

async def inspect_db():
    async with AsyncSessionLocal() as db:
        sessions_res = await db.execute(select(GameSession))
        sessions = sessions_res.scalars().all()
        print(f"Total sessions: {len(sessions)}")
        for s in sessions:
            state_res = await db.execute(select(SessionState).where(SessionState.session_id == s.id))
            state = state_res.scalars().first()
            state_info = f"State exists (Scene: {state.current_scene_id})" if state else "NO STATE FOUND"
            print(f"Session ID: {s.id}, User: {s.user_id}, Template ID: {s.template_id}")
            print(f"  Title: {s.adventure_title}, Image: {s.adventure_image_url}, {state_info}")
            
        templates_res = await db.execute(select(AdventureTemplate))
        templates = templates_res.scalars().all()
        print(f"\nTotal templates: {len(templates)}")
        for t in templates:
            print(f"Template ID: {t.id}, Title: {t.title}, Owner: {t.owner_id}, Image: {t.image_url}")

        from backend.models.user import User
        users_res = await db.execute(select(User))
        users = users_res.scalars().all()
        print(f"\nTotal users: {len(users)}")
        for u in users:
            print(f"User ID: {u.id}, Username: {u.username}")

if __name__ == "__main__":
    asyncio.run(inspect_db())
