import asyncio
import os
import sys

# Add the project root to sys.path so we can import backend modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.core.config import settings
from backend.engine.media_engine import MediaEngine

async def run_migration():
    print("--- TaleWeaver Thumbnail Migration ---")
    library_dir = os.path.join(settings.DATA_DIR, "adventures", "library")
    
    if not os.path.exists(library_dir):
        print(f"Library directory not found: {library_dir}")
        return

    adventures = [d for d in os.listdir(library_dir) if os.path.isdir(os.path.join(library_dir, d))]
    print(f"Found {len(adventures)} adventures in library.")

    for adventure_id in adventures:
        print(f"Processing adventure: {adventure_id}...")
        await MediaEngine.ensure_thumbnails(adventure_id)

    print("\nMigration complete! All missing thumbnails have been generated.")

if __name__ == "__main__":
    asyncio.run(run_migration())
