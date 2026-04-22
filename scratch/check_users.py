import asyncio
import os
import sys
from sqlalchemy import select

# Add root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backend.core.database import AsyncSessionLocal
from backend.models.user import User

async def list_users():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()
        if not users:
            print("No users found in database.")
        for u in users:
            print(f"ID: {u.id} | Username: {u.username} | Role: {u.role}")

if __name__ == "__main__":
    asyncio.run(list_users())
