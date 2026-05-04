import asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.schemas.adventure import AdventureTemplateUpdate

app = FastAPI()

@app.patch("/test")
async def test_patch(payload: AdventureTemplateUpdate):
    return "OK"

client = TestClient(app)

payload = {
  "title": '',
  "original_prompt": '',
  "strict_rules": True,
  "time_per_turn": 5,
  "min_scenes": 1,
  "max_scenes": 5,
  "time_system": 'calendar',
  "time_config": {
    "day_label": 'Day',
    "start_year_override": None,
    "start_time": '08:00'
  }
}

resp = client.patch("/test", json=payload)
print(resp.status_code)
print(resp.json())
