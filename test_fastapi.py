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
  "teaser": '',
  "original_prompt": '',
  "strict_rules": True,
  "rule_enforcement_mode": 'rpg',
  "time_per_turn": 5,
  "pacing_minutes": 5,
  "clock_enabled": False,
  "time_system": 'calendar',
  "selected_style_id": '',
  "selected_tone_id": '',
  "game_over_rules": {},
  "min_scenes": 1,
  "max_scenes": 5,
  "plot": '',
  "rules": '',
  "walkthrough": '',
  "completed_condition": '',
  "gameover_condition": '',
  "selected_image_styles": [],
  "selected_tone": None
}

resp = client.patch("/test", json=payload)
print(resp.status_code)
print(resp.json())
