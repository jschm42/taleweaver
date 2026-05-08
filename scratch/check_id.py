
import asyncio
import os
import sys
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

# Add the current directory to sys.path to find 'backend'
sys.path.append(os.getcwd())

from backend.models.adventure_template import AdventureTemplate
from backend.core.config import settings

async def check_id():
    engine = create_async_engine(settings.DATABASE_URL)
    target_id = "69529b8d-2989-4952-a457-ab4f141f3a2b"
    async with AsyncSession(engine) as session:
        result = await session.execute(select(AdventureTemplate).where(AdventureTemplate.id == target_id))
        adv = result.scalars().first()
        if adv:
            print(f"FOUND adventure: {adv.title} (ID: {adv.id}, Owner: {adv.owner_id})")
        else:
            print(f"Adventure {target_id} NOT FOUND in database.")

if __name__ == "__main__":
    asyncio.run(check_id())
