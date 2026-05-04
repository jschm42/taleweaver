import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# POST /api/adventures/
# ---------------------------------------------------------------------------

async def test_update_adventure_frontend_payload(client: AsyncClient):
    """Patching with frontend payload should not give 422."""
    # 1. create an adventure
    resp = await client.post(
        "/api/adventures/",
        json={"title": "Test Quest", "avatar_name": "Hero"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    adv_id = data["adventure_id"]

    # 2. send frontend payload
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
    
    resp2 = await client.patch(
        f"/api/adventures/{adv_id}",
        json=payload,
    )
    assert resp2.status_code == 200, resp2.text
