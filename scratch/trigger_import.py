import asyncio
import sys
import os

# Add current directory to path so we can import backend
sys.path.append(os.getcwd())

from backend.core.database import AsyncSessionLocal
from backend.engine.adventure_importer import AdventureTemplateImporter

async def run_import():
    async with AsyncSessionLocal() as db:
        print("Starting import from data/imports/adventures...")
        # Use the admin user as owner for convenience drops
        owner_id = "4dea50b5-c3d1-4701-8870-d7bad53cafca"
        await AdventureTemplateImporter.import_from_directory(db, "adventures/default", owner_id=owner_id, delete_after=False)
        print("Import completed.")

if __name__ == "__main__":
    asyncio.run(run_import())
