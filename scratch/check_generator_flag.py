import asyncio
import sys
import os

sys.path.append(os.getcwd())

from backend.core.database import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(text("SELECT id, title, strict_rules, rule_enforcement_mode, is_adventure_generator FROM adventure_templates WHERE origin_id = 'THE_ARCHITECT'"))
        print(res.all())

if __name__ == "__main__":
    asyncio.run(check())
