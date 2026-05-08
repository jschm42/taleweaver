
import asyncio
import sys
import os

# Add the current directory to sys.path to find 'backend'
sys.path.append(os.getcwd())

from backend.core.database import AsyncSessionLocal
from backend.models.user import User
from sqlalchemy import select

async def check_users():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()
        for user in users:
            print(f"User: {user.username} (ID: {user.id})")

if __name__ == "__main__":
    asyncio.run(check_users())
