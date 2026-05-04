import sys
from backend.schemas.adventure import AdventureTemplateUpdate
from pydantic import ValidationError

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

try:
    obj = AdventureTemplateUpdate(**payload)
    print("OK")
except ValidationError as e:
    print("ERROR:")
    print(e.json())
