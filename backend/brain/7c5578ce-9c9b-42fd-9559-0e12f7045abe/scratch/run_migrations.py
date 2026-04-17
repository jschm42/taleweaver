import asyncio
from backend.core.database import apply_sqlite_compat_migrations

async def run_migrations():
    print("Applying migrations...")
    await apply_sqlite_compat_migrations()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(run_migrations())
