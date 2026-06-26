import asyncio
import os
import sys

# Add root to path so we can import backend
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backend.core.database import AsyncSessionLocal
from backend.engine.adventure_importer import AdventureTemplateImporter
from backend.models.user import User
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        # Find the first admin user to assign ownership to
        result = await db.execute(select(User).where(User.role == "admin").limit(1))
        admin = result.scalars().first()
        owner_id = admin.id if admin else None
        
        file_path = os.path.join("adventures", "default", "combat_test_adventure.adv")
        print(f"Importing {file_path} for owner_id: {owner_id}...")
        
        success = await AdventureTemplateImporter.import_file(
            db,
            file_path,
            owner_id=owner_id,
            overwrite=True
        )
        if success:
            print("Successfully imported Kampfsystem Testarena!")
        else:
            print("Failed to import.")

if __name__ == "__main__":
    asyncio.run(main())
