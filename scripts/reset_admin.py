import asyncio
import os
import sys
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

# Add root to path so we can import backend
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backend.core.auth import get_password_hash, validate_password_strength
from backend.core.config import settings
from backend.core.database import AsyncSessionLocal
from backend.models.user import User

DEFAULT_ADMIN_USERNAME = "admin"


async def reset_admin(username: str = DEFAULT_ADMIN_USERNAME, password: Optional[str] = None):
    if not password:
        print(
            "ERROR: Refusing to reset the admin password without an explicit value. "
            "Pass the new password as the second argument: "
            "`python scripts/reset_admin.py admin 'Your-Strong-Pa55!word'`.\n"
            "For local dev with simple passwords, you can add `--no-strict`: "
            "`python scripts/reset_admin.py admin admin123 --no-strict`.",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        validate_password_strength(password)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        if getattr(settings, "STRICT_PASSWORD_POLICY", True):
            print(
                "HINT: For local development, pass `--no-strict` or set `STRICT_PASSWORD_POLICY=False` in `.env`.",
                file=sys.stderr,
            )
        sys.exit(2)

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
            print(f"Successfully set '{username}' with role 'admin'.")
            print("Please log in immediately and change the password via the user profile.")
        except SQLAlchemyError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            await db.rollback()
            sys.exit(1)


if __name__ == "__main__":
    flags = {arg.lower() for arg in sys.argv[1:] if arg.startswith("--")}
    positional = [arg for arg in sys.argv[1:] if not arg.startswith("--")]

    if "--no-strict" in flags or "--insecure" in flags:
        settings.STRICT_PASSWORD_POLICY = False

    if len(positional) > 1:
        asyncio.run(reset_admin(positional[0], positional[1]))
    elif len(positional) == 1:
        asyncio.run(reset_admin(positional[0]))
    else:
        asyncio.run(reset_admin())
