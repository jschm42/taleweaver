import asyncio
from sqlalchemy import select
from backend.core.database import AsyncSessionLocal
from backend.models.user import User

async def dump_users():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()
        for user in users:
            print(f"ID: {user.id}, Username: {user.username}, Role: {user.role}, Hash: {user.hashed_password}")

if __name__ == "__main__":
    asyncio.run(dump_users())
