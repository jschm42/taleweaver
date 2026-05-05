import asyncio
import sys
import os
import json

sys.path.append(os.getcwd())

from backend.core.database import AsyncSessionLocal
from backend.engine.adventure_exporter import AdventureExporter

async def check_export():
    async with AsyncSessionLocal() as db:
        template_id = 'the-architect-fgztycua'
        manifest = await AdventureExporter.build_full_manifest(db, template_id)
        print(json.dumps(manifest["adventure"], indent=2))

if __name__ == "__main__":
    asyncio.run(check_export())
