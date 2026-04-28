import asyncio
from sqlalchemy import select
from backend.core.database import engine, AsyncSessionLocal
from backend.models.game_session import GameSession
from backend.models.adventure_template import AdventureTemplate

async def heal_sessions():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(GameSession))
        sessions = res.scalars().all()
        healed_count = 0
        
        for s in sessions:
            if not s.adventure_title or not s.adventure_image_url:
                print(f"Healing session {s.id}...")
                template = await db.get(AdventureTemplate, s.template_id)
                if template:
                    if not s.adventure_title:
                        s.adventure_title = template.title
                    if not s.adventure_image_url:
                        s.adventure_image_url = template.image_url
                    healed_count += 1
                else:
                    print(f"  Warning: Template {s.template_id} not found for session {s.id}")
        
        if healed_count > 0:
            await db.commit()
            print(f"Successfully healed {healed_count} sessions.")
        else:
            print("No sessions needed healing.")

if __name__ == "__main__":
    asyncio.run(heal_sessions())
