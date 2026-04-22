import os
import sys
import asyncio
from passlib.context import CryptContext
from sqlalchemy import select

# Add root to path so we can import backend
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backend.core.database import AsyncSessionLocal
from backend.core.auth import get_password_hash
from backend.models.user import User

async def reset_admin(username="admin", password="password"):
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(User).filter(User.username == username))
            user = result.scalars().first()
            hashed_password = get_password_hash(password)
            
            if user:
                print(f"Resetting password for existing user '{username}'...")
                user.hashed_password = hashed_password
                user.role = "admin"
            else:
                print(f"Creating new root admin user '{username}'...")
                user = User(
                    username=username,
                    hashed_password=hashed_password,
                    role="admin",
                    bio="The root weaver of this realm."
                )
                db.add(user)
            
            await db.commit()
            print(f"Successfully set '{username}' with role 'admin' and password '{password}'.")
        except Exception as e:
            print(f"Error: {e}")
            await db.rollback()

if __name__ == "__main__":
    if len(sys.argv) > 2:
        asyncio.run(reset_admin(sys.argv[1], sys.argv[2]))
    else:
        asyncio.run(reset_admin())
