import os
import sys
import asyncio
from sqlalchemy import select

# Add the project root to sys.path so we can import 'backend'
sys.path.append(os.getcwd())

from backend.core.database import AsyncSessionLocal
from backend.models.user import User

async def test_update_settings():
    async with AsyncSessionLocal() as db:
        # Find the admin user
        result = await db.execute(select(User).where(User.username == "admin"))
        user = result.scalars().first()
        if not user:
            print("Admin user not found")
            return

        print(f"Original settings: {user.tts_settings}")
        
        # Simulate update
        new_settings = dict(user.tts_settings or {})
        new_settings["use_text_chunking"] = False
        user.tts_settings = new_settings
        
        await db.commit()
        await db.refresh(user)
        
        print(f"Updated settings: {user.tts_settings}")

if __name__ == "__main__":
    asyncio.run(test_update_settings())
