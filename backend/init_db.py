import asyncio

from backend.core.database import engine

# Make sure all models are imported so Base metadata is updated
from backend.models import *
from backend.models.base import Base


async def init_db():
    print("Initializing database...")
    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    print("Database initialization successful!")

if __name__ == "__main__":
    asyncio.run(init_db())
