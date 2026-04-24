import asyncio
from sqlalchemy import select
from backend.core.database import AsyncSessionLocal
from backend.models.user import User
from backend.core.auth import verify_password

async def check_admin_password(password):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).filter(User.username == "admin"))
        user = result.scalars().first()
        if not user:
            print("User 'admin' not found.")
            return
        
        print(f"User: {user.username}")
        print(f"Stored Hash: {user.hashed_password}")
        
        is_correct = verify_password(password, user.hashed_password)
        print(f"Password '{password}' is correct: {is_correct}")

if __name__ == "__main__":
    import sys
    pw = sys.argv[1] if len(sys.argv) > 1 else "anno1503"
    asyncio.run(check_admin_password(pw))
