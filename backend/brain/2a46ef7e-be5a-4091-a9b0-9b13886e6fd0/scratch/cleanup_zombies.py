import asyncio
from sqlalchemy import select, delete
from backend.core.database import AsyncSessionLocal
from backend.models.game_session import GameSession
from backend.models.adventure_template import AdventureTemplate

async def cleanup_zombies():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(GameSession))
        sessions = res.scalars().all()
        to_delete = []
        
        for s in sessions:
            if s.template_id:
                template = await db.get(AdventureTemplate, s.template_id)
                if not template:
                    print(f"Session {s.id} is a zombie (Template {s.template_id} missing). Deleting...")
                    to_delete.append(s.id)
            else:
                print(f"Session {s.id} has no template_id. Deleting...")
                to_delete.append(s.id)
        
        if to_delete:
            for sid in to_delete:
                await db.execute(delete(GameSession).where(GameSession.id == sid))
            await db.commit()
            print(f"Successfully deleted {len(to_delete)} zombie sessions.")
        else:
            print("No zombie sessions found.")

if __name__ == "__main__":
    asyncio.run(cleanup_zombies())
