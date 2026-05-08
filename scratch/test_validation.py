import asyncio
import os
import sys
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

sys.path.append(os.getcwd())

from backend.models.adventure_template import AdventureTemplate
from backend.api.routes.adventures.schemas import AdventureTemplateResponse
from backend.core.config import settings

async def test_validation():
    engine = create_async_engine(settings.DATABASE_URL)
    async with AsyncSession(engine) as session:
        result = await session.execute(select(AdventureTemplate).limit(5))
        adventures = result.scalars().all()
        for adv in adventures:
            try:
                print(f"Validating adventure {adv.id} ({adv.title})...")
                # Simulate what FastAPI does
                AdventureTemplateResponse.model_validate(adv)
                print("Success!")
            except Exception as e:
                print(f"VALIDATION FAILED for {adv.id}:")
                print(e)

if __name__ == "__main__":
    asyncio.run(test_validation())
