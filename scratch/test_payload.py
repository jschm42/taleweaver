from backend.api.routes.adventures.schemas import CreateAdventureTemplatePayload
import json

payload_data = {
    "title": "Test Adventure",
    "storyIdea": "A test idea",
    "generate_npc_images": True,
    "generate_item_images": True,
    "generate_scene_images": True,
    "automatic_cover_generation": True,
    "clock_enabled": True,
    "pacing_minutes": 5,
    "rule_enforcement_mode": "story",
    "selected_style_id": "clinical",
    "selected_tone_id": "clinical",
    "min_scenes": 3,
    "max_scenes": 6,
    "award_generation_enabled": True,
    "min_awards": 3,
    "max_awards": 8,
    "language": "",
    "id": "1234-5678",
    "original_prompt": "A test idea",
    "time_per_turn": 5,
    "selected_image_styles": [{"id": "clinical", "name": "Clinical"}],
    "selected_tone": {"id": "clinical", "name": "Clinical"}
}

try:
    payload = CreateAdventureTemplatePayload.model_validate(payload_data)
    print("Validation successful!")
except Exception as e:
    print(f"Validation failed: {e}")
