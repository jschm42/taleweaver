import asyncio
from sqlalchemy import select
from backend.core.database import AsyncSessionLocal
from backend.models.avatar import Avatar

async def check_stats():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Avatar))
        avatars = res.scalars().all()
        for av in avatars:
            print(f"Avatar: {av.name}")
            print(f"  strength: {av.strength} (type: {type(av.strength)})")
            print(f"  stats: {av.stats}")

if __name__ == "__main__":
    asyncio.run(check_stats())
