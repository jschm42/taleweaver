import os
import sys
import asyncio
from sqlalchemy import select

# Add the project root to sys.path so we can import 'backend'
sys.path.append(os.getcwd())

from backend.core.database import AsyncSessionLocal
from backend.models.user import User

async def check_tts_settings():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()
        for user in users:
            print(f"User: {user.username}")
            print(f"TTS Settings: {user.tts_settings}")
            print("-" * 20)

if __name__ == "__main__":
    asyncio.run(check_tts_settings())
