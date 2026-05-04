import requests

url = "http://localhost:8000/api/adventures/the-rpg-testing-grounds-8nl305xe"
# Use a mock token to bypass auth or see if auth fails
headers = {"Authorization": "Bearer TEST_TOKEN"}

# payload that AdventureEditorView.vue sends
payload = {
  "title": 'The RPG Testing Grounds',
  "teaser": '...',
  "original_prompt": '',
  "strict_rules": True,
  "rule_enforcement_mode": 'rpg',
  "time_per_turn": 5,
  "pacing_minutes": 5,
  "clock_enabled": False,
  "time_system": 'calendar',
  "selected_style_id": 'dark-fantasy',
  "selected_tone_id": 'serious',
  "game_over_rules": {},
  "min_scenes": 1,
  "max_scenes": 5,
  "plot": '',
  "rules": '',
  "walkthrough": '',
  "completed_condition": '',
  "gameover_condition": '',
  "selected_image_styles": [{"id": "dark-fantasy", "name": "dark-fantasy"}],
  "selected_tone": {"id": "serious", "name": "serious"}
}

try:
    resp = requests.patch(url, json=payload, headers=headers)
    print(resp.status_code)
    print(resp.text)
except Exception as e:
    print(e)
