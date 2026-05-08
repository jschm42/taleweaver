import asyncio
import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from sqlalchemy import select
from backend.core.database import AsyncSessionLocal
from backend.models.world_entity import WorldEntity

async def check_db():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(WorldEntity).where(WorldEntity.name.ilike("%Rusty Dagger%")))
        entities = res.scalars().all()
        if not entities:
            print("No entities found matching 'Rusty Dagger'")
            # Try just 'Rusty'
            res = await db.execute(select(WorldEntity).where(WorldEntity.name.ilike("%Rusty%")))
            entities = res.scalars().all()
            
        for e in entities:
            print(f"Entity: {e.name} (ID: {e.id})")
            print(f"  Template ID: {e.template_id}")
            print(f"  Image URL: {e.image_url}")
            print(f"  Current Scene: {e.current_scene_id}")
            print(f"  Is in inventory: {e.is_in_inventory}")

if __name__ == "__main__":
    asyncio.run(check_db())
