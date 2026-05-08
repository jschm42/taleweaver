import asyncio
import os
import sys
from sqlalchemy import select, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

# Add the parent directory to sys.path to import backend
sys.path.append(os.getcwd())

from backend.models.world_entity import WorldEntity
from backend.core.config import settings

async def debug_db():
    print(f"Database URL: {settings.DATABASE_URL}")
    engine = create_async_engine(settings.DATABASE_URL)
    async with AsyncSession(engine) as session:
        try:
            print("Attempting to select WorldEntity...")
            stmt = select(WorldEntity).limit(1)
            result = await session.execute(stmt)
            entity = result.scalars().first()
            print(f"Success! Found entity: {entity.id if entity else 'None'}")
        except Exception as e:
            print(f"\nERROR caught during execution:\n{e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_db())
