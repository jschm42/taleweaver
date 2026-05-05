import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://localhost:8000/api"
TOKEN = "YOUR_TOKEN_HERE" # Need to get a real token for manual testing if needed

async def test_debug_commands():
    # This is a placeholder for manual verification steps
    print("Verification steps:")
    print("1. Start the server with TALEWEAVER_DEBUG_ENABLED=True")
    print("2. Open the game and type /debug engine")
    print("3. Verify the output contains version and session info")
    print("4. Type /debug scenes, /debug npcs, /debug items, /debug exits")
    print("5. Verify IDs are shown")
    print("6. Type /debug walkthrough")
    print("7. Verify it unlocks the walkthrough modal")

if __name__ == "__main__":
    asyncio.run(test_debug_commands())
