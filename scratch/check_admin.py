import asyncio
from backend.core.database import AsyncSessionLocal
from backend.models.user import User
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).where(User.username == 'admin'))
        u = res.scalars().first()
        if u:
            print(f"User: {u.username}")
            print(f"Log: {u.game_log}")
        else:
            print("Admin user not found")

if __name__ == "__main__":
    asyncio.run(check())
