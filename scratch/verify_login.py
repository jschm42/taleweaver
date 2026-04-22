import asyncio
import os
import sys
from sqlalchemy import select

# Add root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backend.core.database import AsyncSessionLocal
from backend.models.user import User
from backend.core.auth import verify_password

async def check_admin_login(username, password):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).filter(User.username == username))
        user = result.scalars().first()
        if not user:
            print(f"User '{username}' not found.")
            return
        
        is_correct = verify_password(password, user.hashed_password)
        print(f"User: {username}")
        print(f"Hashed Password: {user.hashed_password}")
        print(f"Login valid: {is_correct}")

if __name__ == "__main__":
    import sys
    username = sys.argv[1] if len(sys.argv) > 1 else "admin"
    password = sys.argv[2] if len(sys.argv) > 2 else "password"
    asyncio.run(check_admin_login(username, password))
