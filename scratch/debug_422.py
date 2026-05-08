import asyncio
import os
import sys
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

sys.path.append(os.getcwd())

from backend.models.adventure_template import AdventureTemplate
from backend.api.routes.adventures.schemas import AdventureTemplateResponse
from backend.schemas.adventure import AdventureTemplateUpdate
from backend.core.config import settings

async def debug_422():
    engine = create_async_engine(settings.DATABASE_URL)
    async with AsyncSession(engine) as session:
        target_id = "5e687f41-3ae5-403a-81d5-745e778f11fe"
        adv = await session.get(AdventureTemplate, target_id)
        if not adv:
            print("Adv not found")
            return
            
        print(f"Adventure: {adv.title}")
        print(f"Prompt length: {len(adv.original_prompt) if adv.original_prompt else 0}")
        
        try:
            print("Validating against AdventureTemplateResponse...")
            AdventureTemplateResponse.model_validate(adv)
            print("Response Validation Success!")
        except Exception as e:
            print("Response Validation FAILED:")
            print(e)
            
        try:
            print("\nValidating against AdventureTemplateUpdate (simulating patch payload)...")
            # Convert model to dict to simulate payload
            data = {c.name: getattr(adv, c.name) for c in adv.__table__.columns if getattr(adv, c.name) is not None}
            AdventureTemplateUpdate(**data)
            print("Update Validation Success!")
        except Exception as e:
            print("Update Validation FAILED:")
            print(e)

if __name__ == "__main__":
    asyncio.run(debug_422())
