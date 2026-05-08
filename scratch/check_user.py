
import asyncio
import os
import sys
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

# Add the current directory to sys.path to find 'backend'
sys.path.append(os.getcwd())

from backend.models.user import User
from backend.core.config import settings

async def check_user():
    engine = create_async_engine(settings.DATABASE_URL)
    owner_id = "4dea50b5-c3d1-4701-8870-d7bad53cafca"
    async with AsyncSession(engine) as session:
        result = await session.execute(select(User).where(User.id == owner_id))
        user = result.scalars().first()
        if user:
            print(f"FOUND user: {user.username} (ID: {user.id})")
        else:
            print(f"User {owner_id} NOT FOUND in database.")

if __name__ == "__main__":
    asyncio.run(check_user())
