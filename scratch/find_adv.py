
import asyncio
import sys
import os

# Add the current directory to sys.path to find 'backend'
sys.path.append(os.getcwd())

from backend.core.database import AsyncSessionLocal
from backend.models.adventure_template import AdventureTemplate
from sqlalchemy import select

async def check_adv():
    adv_id = "69529b8d-2989-4952-a457-ab4f141f3a2b"
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(AdventureTemplate).where(AdventureTemplate.id == adv_id))
        adv = result.scalars().first()
        if adv:
            print(f"Adventure found: {adv.title}")
            print(f"Owner ID: {adv.owner_id}")
        else:
            print("Adventure NOT found")

if __name__ == "__main__":
    asyncio.run(check_adv())
