"""
Tests for the Adventures REST API (Package 4).

Covers: create, list, get, update, delete, pause/resume, and game-state
sub-routes. All tests follow the Arrange-Act-Assert pattern.
"""
import pytest
import pytest_asyncio
import json
from httpx import AsyncClient
from io import BytesIO
import os
from sqlalchemy import delete, select

from PIL import Image
from backend.models.adventure import Adventure
from backend.models.avatar import Avatar
from backend.models.game_state import GameState
from backend.models.world_entity import WorldEntity
from backend.models.world_entity import WorldScene
from backend.models.user import User
from backend.engine.debug_engine import DebugEngine
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def client(auth_client: AsyncClient) -> AsyncClient:
    """Adventures endpoints require authentication."""
    return auth_client


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _create_adventure(client: AsyncClient, title: str = "Test Quest") -> dict:
    """Creates a minimal adventure and returns the response JSON."""
    resp = await client.post(
        "/api/adventures",
        json={"title": title, "avatar_name": "Hero"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# POST /api/adventures
# ---------------------------------------------------------------------------

async def test_create_adventure_returns_ids(client: AsyncClient):
    """Creating an adventure returns game_id, adventure_id, and avatar_id."""
    # Arrange & Act
    data = await _create_adventure(client)

    # Assert
    assert "game_id" in data
    assert "adventure_id" in data
    assert "avatar_id" in data


async def test_create_adventure_creates_one_visible_session(client: AsyncClient):
    """A single create call should result in exactly one visible session row."""
    # Arrange & Act
    ids = await _create_adventure(client)

    # Assert
    resp = await client.get("/api/adventures")
    assert resp.status_code == 200
    sessions = resp.json()
    assert len(sessions) == 1
    assert sessions[0]["adventure_id"] == ids["adventure_id"]
    assert sessions[0]["game_id"] == ids["adventure_id"]


async def test_create_adventure_with_heartbeat(client: AsyncClient):
    """Heartbeat settings are persisted when creating an adventure."""
    # Arrange
    payload = {
        "title": "Timed Quest",
        "avatar_name": "Ranger",
        "heartbeat_enabled": True,
        "heartbeat_interval": 30,
    }

    # Act
    resp = await client.post("/api/adventures", json=payload)
    data = resp.json()

    # Assert
    assert resp.status_code == 201
    adv_resp = await client.get(f"/api/adventures/{data['adventure_id']}")
    adv = adv_resp.json()
    assert adv["heartbeat_enabled"] is True
    assert adv["heartbeat_interval"] == 30


async def test_create_adventure_with_rule_mode_and_style_tone(client: AsyncClient):
    """New generation controls should be persisted on adventure creation."""
    payload = {
        "title": "Curated Quest",
        "avatar_name": "Guide",
        "rule_enforcement_mode": "story",
        "clock_enabled": True,
        "time_per_turn": 12,
        "pacing_minutes": 12,
        "selected_image_styles": ["dark-fantasy-painting", "cinematic-realism"],
        "selected_tone": "horror",
    }

    resp = await client.post("/api/adventures", json=payload)
    assert resp.status_code == 201
    ids = resp.json()

    adv_resp = await client.get(f"/api/adventures/{ids['adventure_id']}")
    assert adv_resp.status_code == 200
    adv = adv_resp.json()
    assert adv["rule_enforcement_mode"] == "story"
    assert adv["strict_rules"] is True
    assert adv["clock_enabled"] is True
    assert adv["pacing_minutes"] == 12
    assert adv["selected_tone"] == "horror"
    assert "dark-fantasy-painting" in adv["selected_image_styles"]


async def test_create_adventure_preserves_advanced_manifest_fields(client: AsyncClient):
    """Advanced create payloads preserve time pacing and start datetime metadata."""
    payload = {
        "title": "Chronicle of Dawn",
        "avatar_name": "Chronicle Keeper",
        "time_per_turn": 12,
        "original_manifest": {
            "version": "1.0",
            "title": "Chronicle of Dawn",
            "time_per_turn": 12,
            "start_date": "2026-04-14",
            "start_time": "08:30",
            "start_datetime": "2026-04-14T08:30:00.000Z",
            "protagonist": {
                "name": "Nora",
                "role": "Archivist",
                "description": "A careful keeper of the first dawn records.",
            },
        },
    }

    resp = await client.post("/api/adventures", json=payload)
    assert resp.status_code == 201, resp.text
    ids = resp.json()

    adv_resp = await client.get(f"/api/adventures/{ids['adventure_id']}")
    assert adv_resp.status_code == 200
    adv = adv_resp.json()
    assert adv["time_per_turn"] == 12

    debug_resp = await client.get(f"/api/adventures/{ids['adventure_id']}/debug")
    assert debug_resp.status_code == 200
    debug_data = debug_resp.json()
    original_manifest = debug_data["adventure"]["original_manifest"]
    assert original_manifest["time_per_turn"] == 12
    assert original_manifest["start_date"] == "2026-04-14"
    assert original_manifest["start_time"] == "08:30"
    assert original_manifest["start_datetime"] == "2026-04-14T08:30:00.000Z"


async def test_create_adventure_persists_generation_status_before_world_gen(client: AsyncClient, monkeypatch):
    """The background job writes an intermediate status before the world generator starts."""
    captured: dict[str, str] = {}

    llm_config_resp = await client.post(
        "/api/settings/llm",
        json={
            "small_model": "llama3.2",
            "small_model_provider": "ollama",
            "complex_model": "qwen2.5",
            "complex_model_provider": "ollama",
            "preferred_provider": "ollama",
            "ollama_url": "http://localhost:11434",
        },
    )
    assert llm_config_resp.status_code == 200, llm_config_resp.text

    async def fake_generate_world(
        db,
        _user,
        adventure_id,
        *_args,
        **_kwargs,
    ):
        _ = (_args, _kwargs)
        adventure = await db.get(Adventure, adventure_id)
        assert adventure is not None
        captured["status"] = adventure.creation_status or ""

        db.add(
            WorldScene(
                id="START",
                adventure_id=adventure_id,
                label="Starting Room",
                description="A minimal scene created by the test double.",
                image_url=None,
            )
        )
        await db.commit()

    monkeypatch.setattr("backend.api.routes.adventures.WorldGenerator.generate_world", fake_generate_world)

    resp = await client.post(
        "/api/adventures",
        json={"title": "Status Quest", "avatar_name": "Hero"},
    )
    assert resp.status_code == 201, resp.text
    adventure_id = resp.json()["adventure_id"]

    assert captured["status"] == "Generating world structure"

    status_resp = await client.get(f"/api/adventures/{adventure_id}/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert "is_ready" in status_data
    assert "status" in status_data


async def test_debug_includes_protagonist_profile_image(client: AsyncClient):
    """The adventure debug payload exposes the protagonist portrait for the Visuals panel."""
    ids = await _create_adventure(client, "Portrait Quest")

    async with TestSessionLocal() as session:
        avatar = await session.get(Avatar, ids["avatar_id"])
        assert avatar is not None
        avatar.profile_image = "/data/adventures/example/protagonist.png"
        await session.commit()

    debug_resp = await client.get(f"/api/adventures/{ids['adventure_id']}/debug")
    assert debug_resp.status_code == 200
    debug_data = debug_resp.json()
    assert debug_data["protagonist"]["id"] == ids["avatar_id"]
    assert debug_data["protagonist"]["profile_image"] == "/data/adventures/example/protagonist.png"


async def test_debug_award_grants_all_adventure_awards():
    """The /debug award command should mark every adventure award as earned."""
    async with TestSessionLocal() as session:
        user = User(username="award_debugger", hashed_password="hash", role="user")
        adventure = Adventure(title="Award Debug Quest")
        session.add_all([user, adventure])
        await session.flush()

        # Existing award from another adventure with identical key must not block this one.
        user.earned_awards = [
            {
                "key": "award-1",
                "title": "Plumber of the Hour",
                "description": "From another adventure",
                "tier": "gold",
                "adventure_id": "other-adventure",
                "adventure_title": "Old Quest",
                "session_id": "old-session",
                "earned_at": "2026-01-01T00:00:00",
            }
        ]

        adventure.owner_id = user.id
        avatar = Avatar(user_id=user.id, adventure_id=adventure.id, name="Hero")
        session.add(avatar)
        await session.flush()

        adventure.awards = [
            {
                "key": "award-1",
                "title": "Plumber of the Hour",
                "description": "A debug-only award.",
                "tier": "gold",
                "requirement": "Test command",
                "is_earned": False,
            },
            {
                "key": "award-2",
                "title": "Pipe Whisperer",
                "description": "A second debug-only award.",
                "tier": "silver",
                "requirement": "Test command",
                "is_earned": False,
            },
        ]

        state = GameState(
            user_id=user.id,
            avatar_id=avatar.id,
            adventure_id=adventure.id,
            scene_id="SCENE-1",
        )

        session.add(state)
        await session.commit()

        message = await DebugEngine.handle_debug_command(
            session,
            state,
            "award",
            user=user,
            adventure=adventure,
        )
        await session.commit()
        await session.refresh(adventure)
        await session.refresh(user)

    assert "All adventure awards granted" in message
    assert all(award["is_earned"] is True for award in adventure.awards)
    assert len(user.earned_awards or []) == 3
    this_adv_awards = [a for a in (user.earned_awards or []) if a.get("adventure_id") == adventure.id]
    assert {entry["key"] for entry in this_adv_awards} == {"award-1", "award-2"}


async def test_get_chat_history_includes_awards(client: AsyncClient):
    """Session snapshot must include the full award list for Quest Log rendering."""
    ids = await _create_adventure(client, "Awards Snapshot Quest")

    async with TestSessionLocal() as session:
        adventure = await session.get(Adventure, ids["adventure_id"])
        assert adventure is not None
        adventure.awards = [
            {
                "key": "a-snapshot",
                "title": "Visible in Log",
                "description": "Should be present in GET /chat response",
                "tier": "bronze",
                "requirement": "Any",
                "is_earned": False,
            }
        ]
        await session.commit()

    chat_resp = await client.get(f"/api/adventures/{ids['game_id']}/chat")
    assert chat_resp.status_code == 200
    data = chat_resp.json()
    assert "awards" in data
    assert len(data["awards"]) == 1
    assert data["awards"][0]["key"] == "a-snapshot"


async def test_regenerate_visual_updates_protagonist_image(client: AsyncClient, monkeypatch):
    """Regenerating the protagonist uses the default prompt when none is provided."""
    ids = await _create_adventure(client, "Regenerate Quest")

    async with TestSessionLocal() as session:
        avatar = await session.get(Avatar, ids["avatar_id"])
        assert avatar is not None
        avatar.profile_image = None
        await session.commit()

    captured: dict[str, str] = {}

    async def fake_generate_entity_image(prompt, _adventure_id, entity_id, entity_type, _user_config, _api_keys):
        captured["prompt"] = prompt
        captured["entity_id"] = entity_id
        captured["entity_type"] = entity_type
        return "/data/adventures/generated/protagonist.png"

    monkeypatch.setattr("backend.api.routes.adventures.MediaEngine.generate_entity_image", fake_generate_entity_image)

    resp = await client.post(
        f"/api/adventures/{ids['adventure_id']}/visuals/regenerate",
        json={"target_type": "protagonist", "target_id": ids["avatar_id"]},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["image_url"] == "/data/adventures/generated/protagonist.png"
    assert captured["entity_id"] == ids["avatar_id"]
    assert captured["entity_type"] == "PROTAGONIST"
    assert "Portrait of character" in captured["prompt"]

    async with TestSessionLocal() as session:
        avatar = await session.get(Avatar, ids["avatar_id"])
        assert avatar is not None
        assert avatar.profile_image == "/data/adventures/generated/protagonist.png"


async def test_regenerate_visual_injects_style_and_tone(client: AsyncClient, monkeypatch):
    """Visual prompt generation should include selected style and tone instructions."""
    ids = await _create_adventure(client, "Styled Prompt Quest")

    async with TestSessionLocal() as session:
        adventure = await session.get(Adventure, ids["adventure_id"])
        assert adventure is not None
        adventure.selected_image_styles = ["chalk-noir"]
        adventure.selected_tone = "horror"
        await session.commit()

    captured: dict[str, str] = {}

    async def fake_generate_entity_image(prompt, _adventure_id, entity_id, entity_type, _user_config, _api_keys):
        captured["prompt"] = prompt
        captured["entity_id"] = entity_id
        captured["entity_type"] = entity_type
        return "/data/adventures/generated/protagonist-tone-style.png"

    monkeypatch.setattr("backend.api.routes.adventures.MediaEngine.generate_entity_image", fake_generate_entity_image)

    resp = await client.post(
        f"/api/adventures/{ids['adventure_id']}/visuals/regenerate",
        json={"target_type": "protagonist", "target_id": ids["avatar_id"]},
    )
    assert resp.status_code == 200, resp.text
    assert "Style constraints" in captured["prompt"]
    assert "Narrative tone reference" in captured["prompt"]


async def test_regenerate_visual_uses_custom_prompt_for_scene(client: AsyncClient, monkeypatch):
    """A custom prompt overrides the default prompt when regenerating a scene image."""
    ids = await _create_adventure(client, "Scene Prompt Quest")

    async with TestSessionLocal() as session:
        avatar = await session.get(Avatar, ids["avatar_id"])
        assert avatar is not None
        avatar.profile_image = None
        session.add(
            WorldScene(
                id="HALL",
                adventure_id=ids["adventure_id"],
                label="Great Hall",
                description="A vast room of cold marble and chandeliers.",
                image_url=None,
            )
        )
        await session.commit()

    captured: dict[str, str] = {}

    async def fake_generate_scene_image(prompt, _adventure_id, _user_config, _api_keys):
        captured["prompt"] = prompt
        return "/data/adventures/generated/scene.png"

    monkeypatch.setattr("backend.api.routes.adventures.MediaEngine.generate_scene_image", fake_generate_scene_image)

    resp = await client.post(
        f"/api/adventures/{ids['adventure_id']}/visuals/regenerate",
        json={
            "target_type": "scene",
            "target_id": "HALL",
            "prompt": "A foggy hall lit by green lanterns, cinematic wide shot.",
        },
    )
    assert resp.status_code == 200, resp.text
    assert captured["prompt"] == "A foggy hall lit by green lanterns, cinematic wide shot."

    debug_resp = await client.get(f"/api/adventures/{ids['adventure_id']}/debug")
    assert debug_resp.status_code == 200
    debug_data = debug_resp.json()
    scene = next(scene for scene in debug_data["scenes"] if scene["id"] == "HALL")
    assert scene["image_url"] == "/data/adventures/generated/scene.png"


async def test_regenerate_visual_updates_cover_image(client: AsyncClient, monkeypatch):
    """Regenerating the cover should persist the generated adventure cover URL."""
    ids = await _create_adventure(client, "Cover Regenerate Quest")

    captured: dict[str, str] = {}

    async def fake_generate_adventure_cover(title, context, adventure_id, **_kwargs):
        captured["title"] = title
        captured["context"] = context
        captured["adventure_id"] = adventure_id
        return "/data/adventures/generated/cover.png"

    monkeypatch.setattr("backend.api.routes.adventures.MediaEngine.generate_adventure_cover", fake_generate_adventure_cover)

    resp = await client.post(
        f"/api/adventures/{ids['adventure_id']}/visuals/regenerate",
        json={"target_type": "cover", "target_id": ids["adventure_id"], "prompt": "Stormbound citadel on a fractured moon."},
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["image_url"] == "/data/adventures/generated/cover.png"
    assert captured["title"] == "Cover Regenerate Quest"
    assert captured["context"] == "Stormbound citadel on a fractured moon."
    assert captured["adventure_id"] == ids["adventure_id"]

    async with TestSessionLocal() as session:
        adventure = await session.get(Adventure, ids["adventure_id"])
        assert adventure is not None
        assert adventure.image_url == "/data/adventures/generated/cover.png"


def _make_png_bytes(width: int, height: int) -> bytes:
    buffer = BytesIO()
    image = Image.new("RGB", (width, height), color=(123, 45, 67))
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _make_noisy_png_bytes(width: int, height: int) -> bytes:
    """Creates a PNG that is likely large in byte-size due to low compressibility."""
    buffer = BytesIO()
    pixels = os.urandom(width * height * 3)
    image = Image.frombytes("RGB", (width, height), pixels)
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def test_upload_visual_updates_protagonist_image(client: AsyncClient):
    """Uploading a valid visual should persist the new protagonist image URL."""
    ids = await _create_adventure(client, "Upload Quest")
    image_bytes = _make_png_bytes(800, 1000)

    resp = await client.post(
        f"/api/adventures/{ids['adventure_id']}/visuals/upload",
        data={"target_type": "protagonist", "target_id": ids["avatar_id"]},
        files={"file": ("portrait.png", image_bytes, "image/png")},
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "uploaded"
    assert data["target_type"] == "protagonist"
    assert data["image_url"].endswith(f"/protagonist/{ids['avatar_id']}.png")

    debug_resp = await client.get(f"/api/adventures/{ids['adventure_id']}/debug")
    assert debug_resp.status_code == 200
    debug_data = debug_resp.json()
    assert debug_data["protagonist"]["profile_image"] == data["image_url"]


async def test_upload_visual_rejects_oversized_image(client: AsyncClient):
    """Oversized uploads should fail validation before persisting anything."""
    ids = await _create_adventure(client, "Upload Validation Quest")
    image_bytes = _make_png_bytes(1600, 1600)

    resp = await client.post(
        f"/api/adventures/{ids['adventure_id']}/visuals/upload",
        data={"target_type": "protagonist", "target_id": ids["avatar_id"]},
        files={"file": ("too-large.png", image_bytes, "image/png")},
    )

    assert resp.status_code == 400
    assert "Max size for this asset" in resp.text


async def test_upload_visual_rejects_oversized_file_bytes(client: AsyncClient):
    """Uploads that exceed file byte limits should fail before persisting anything."""
    ids = await _create_adventure(client, "Upload File Size Validation Quest")
    image_bytes = _make_noisy_png_bytes(1024, 1280)
    assert len(image_bytes) > 2 * 1024 * 1024

    resp = await client.post(
        f"/api/adventures/{ids['adventure_id']}/visuals/upload",
        data={"target_type": "protagonist", "target_id": ids["avatar_id"]},
        files={"file": ("too-heavy.png", image_bytes, "image/png")},
    )

    assert resp.status_code == 400
    assert "Max file size for this asset" in resp.text


async def test_upload_visual_updates_cover_image(client: AsyncClient):
    """Uploading a valid cover image should persist the adventure image URL."""
    ids = await _create_adventure(client, "Cover Upload Quest")
    image_bytes = _make_png_bytes(1600, 800)

    resp = await client.post(
        f"/api/adventures/{ids['adventure_id']}/visuals/upload",
        data={"target_type": "cover", "target_id": ids["adventure_id"]},
        files={"file": ("cover.png", image_bytes, "image/png")},
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "uploaded"
    assert data["target_type"] == "cover"
    assert "/cover_" in data["image_url"]
    assert data["image_url"].endswith(".png")

    debug_resp = await client.get(f"/api/adventures/{ids['adventure_id']}/debug")
    assert debug_resp.status_code == 200
    debug_data = debug_resp.json()
    assert debug_data["adventure"]["image_url"] == data["image_url"]


async def test_reset_adventure_preserves_existing_image_assets(client: AsyncClient):
    """Reset should keep already generated protagonist/scene/entity image URLs."""
    ids = await _create_adventure(client, "Reset Asset Quest")

    protagonist_img = "/data/adventures/reset-asset/protagonist.png"
    scene_img = "/data/adventures/reset-asset/scenes/hall.png"
    npc_img = "/data/adventures/reset-asset/npcs/guide.png"

    async with TestSessionLocal() as session:
        adventure = await session.get(Adventure, ids["adventure_id"])
        assert adventure is not None
        adventure.original_manifest = {
            "title": "Reset Asset Quest",
            "protagonist": {
                "name": "Hero",
                "role": "Plumber",
                "description": "Keeps pipes alive",
            },
            "scenes": [
                {
                    "id": "HALL",
                    "name": "Hall",
                    "description": "A simple corridor",
                }
            ],
            "exits": [],
            "npcs": [
                {
                    "id": "GUIDE",
                    "name": "Guide",
                    "description": "Shows the way",
                    "start_scene_id": "HALL",
                }
            ],
            "objects": [],
        }

        state_res = await session.execute(select(GameState).where(GameState.adventure_id == ids["adventure_id"]))
        state = state_res.scalars().first()
        assert state is not None
        state.scene_id = "HALL"

        avatar = await session.get(Avatar, ids["avatar_id"])
        assert avatar is not None
        avatar.profile_image = protagonist_img

        await session.execute(delete(WorldScene).where(WorldScene.adventure_id == ids["adventure_id"]))
        await session.execute(delete(WorldEntity).where(WorldEntity.adventure_id == ids["adventure_id"]))

        session.add(
            WorldScene(
                id="HALL",
                adventure_id=ids["adventure_id"],
                label="Hall",
                description="A simple corridor",
                image_url=scene_img,
            )
        )
        session.add(
            WorldEntity(
                id="GUIDE",
                adventure_id=ids["adventure_id"],
                entity_type="NPC",
                name="Guide",
                description="Shows the way",
                current_scene_id="HALL",
                image_url=npc_img,
            )
        )
        await session.commit()

    reset_resp = await client.post(f"/api/adventures/{ids['adventure_id']}/reset")
    assert reset_resp.status_code == 200, reset_resp.text

    async with TestSessionLocal() as session:
        avatar = await session.get(Avatar, ids["avatar_id"])
        assert avatar is not None
        assert avatar.profile_image == protagonist_img

        hall_scene_res = await session.execute(
            select(WorldScene).where(
                WorldScene.adventure_id == ids["adventure_id"],
                WorldScene.id == "HALL",
            )
        )
        hall_scene = hall_scene_res.scalars().first()
        assert hall_scene is not None
        assert hall_scene.image_url == scene_img

        guide_res = await session.execute(
            select(WorldEntity).where(
                WorldEntity.adventure_id == ids["adventure_id"],
                WorldEntity.id == "GUIDE",
            )
        )
        guide = guide_res.scalars().first()
        assert guide is not None
        assert guide.image_url == npc_img


async def test_export_manifest_returns_original_manifest_only(client: AsyncClient):
    """Exported .adv manifest should be the original blueprint without runtime/session enrichment."""
    payload = {
        "title": "Export Quest",
        "avatar_name": "Archivist",
        "original_manifest": {
            "version": "1.0",
            "title": "Export Quest",
            "scenes": [
                {
                    "id": "LIBRARY",
                    "title": "The Library",
                    "description": "A quiet room of dusty shelves.",
                    "is_hidden": False,
                }
            ],
            "characters": [
                {
                    "id": "LIBRARIAN",
                    "name": "Old Librarian",
                    "role": "NPC",
                    "description": "A stern keeper of secrets.",
                    "is_npc": True,
                }
            ],
            "items": [
                {
                    "id": "ANCIENT_KEY",
                    "name": "Ancient Key",
                    "type": "KEY",
                    "description": "A key from another age.",
                }
            ],
        },
    }

    resp = await client.post("/api/adventures", json=payload)
    assert resp.status_code == 201, resp.text
    adventure_id = resp.json()["adventure_id"]

    # Add runtime state that must NOT bleed into exported manifest.
    async with TestSessionLocal() as session:
        session.add(
            WorldEntity(
                id="ANCIENT_KEY",
                adventure_id=adventure_id,
                entity_type="OBJECT",
                name="Ancient Key",
                description="A key from another age.",
                current_scene_id="HIDDEN_VAULT",
                spatial_position="inside a brass lockbox",
                item_type="KEY",
                wearable_slots=None,
                is_in_inventory=False,
                is_hidden=False,
                inventory=[],
                metadata_json={"durability": 42},
            )
        )
        await session.commit()

    export_resp = await client.get(f"/api/adventures/{adventure_id}/export/manifest")
    assert export_resp.status_code == 200, export_resp.text
    export_data = export_resp.json()
    assert export_data["title"] == "Export Quest"
    assert "npcs" not in export_data
    assert "objects" not in export_data
    assert export_data["items"][0].get("start_scene_id") is None


async def test_export_manifest_backfills_core_metadata_without_runtime_state(client: AsyncClient):
    """Export should include core .adv metadata even if original manifest is sparse."""
    payload = {
        "title": "Sparse Quest",
        "avatar_name": "Archivist",
        "context": "A lightweight context.",
        "time_per_turn": 7,
        "original_manifest": {
            "title": "Sparse Quest",
            "items": [{"id": "SPARE_KEY", "name": "Spare Key", "type": "KEY"}],
        },
    }

    resp = await client.post("/api/adventures", json=payload)
    assert resp.status_code == 201, resp.text
    adventure_id = resp.json()["adventure_id"]

    async with TestSessionLocal() as session:
        session.add(
            WorldEntity(
                id="SPARE_KEY",
                adventure_id=adventure_id,
                entity_type="OBJECT",
                name="Spare Key",
                description="A tiny brass key.",
                current_scene_id="SECRET_ROOM",
                spatial_position="inside a hidden drawer",
                item_type="KEY",
                wearable_slots=None,
                is_in_inventory=False,
                is_hidden=False,
                inventory=[],
                metadata_json={"uses": 1},
            )
        )
        await session.commit()

    export_resp = await client.get(f"/api/adventures/{adventure_id}/export/manifest")
    assert export_resp.status_code == 200, export_resp.text
    export_data = export_resp.json()

    assert export_data["version"] == "1.0"
    assert export_data["id"] == adventure_id
    assert export_data["title"] == "Sparse Quest"
    assert export_data["time_per_turn"] == 7
    assert export_data["generate_npc_images"] is False
    assert export_data["generate_item_images"] is False
    assert export_data["automatic_cover_generation"] is False

    # Runtime world details must not leak into export.
    assert "npcs" not in export_data
    assert "objects" not in export_data
    assert export_data["items"][0].get("start_scene_id") is None


# ---------------------------------------------------------------------------
# GET /api/adventures
# ---------------------------------------------------------------------------

async def test_list_adventures_empty(client: AsyncClient):
    """Listing adventures on a fresh DB returns an empty list."""
    resp = await client.get("/api/adventures")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_adventures_returns_created(client: AsyncClient):
    """After creating two adventures, both appear in the list."""
    await _create_adventure(client, "Quest A")
    await _create_adventure(client, "Quest B")

    resp = await client.get("/api/adventures")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# ---------------------------------------------------------------------------
# GET /api/adventures/{adventure_id}
# ---------------------------------------------------------------------------

async def test_get_adventure_success(client: AsyncClient):
    """Fetching an existing adventure returns its details."""
    ids = await _create_adventure(client, "Dragon's Lair")

    resp = await client.get(f"/api/adventures/{ids['adventure_id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Dragon's Lair"
    assert "strict_rules" in data


async def test_get_adventure_not_found(client: AsyncClient):
    """Fetching a non-existent adventure returns 404."""
    resp = await client.get("/api/adventures/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/adventures/{adventure_id}
# ---------------------------------------------------------------------------

async def test_update_adventure_title(client: AsyncClient):
    """Patching the title of an adventure updates only that field."""
    ids = await _create_adventure(client, "Old Title")

    resp = await client.patch(
        f"/api/adventures/{ids['adventure_id']}",
        json={"title": "New Title"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "New Title"


async def test_update_adventure_strict_rules(client: AsyncClient):
    """Patching strict_rules toggles the flag correctly."""
    ids = await _create_adventure(client)

    resp = await client.patch(
        f"/api/adventures/{ids['adventure_id']}",
        json={"strict_rules": False},
    )
    assert resp.status_code == 200
    assert resp.json()["strict_rules"] is False


async def test_update_adventure_not_found(client: AsyncClient):
    """Patching a non-existent adventure returns 404."""
    resp = await client.patch(
        "/api/adventures/00000000-0000-0000-0000-000000000000",
        json={"title": "Ghost"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/adventures/{adventure_id}
# ---------------------------------------------------------------------------

async def test_delete_adventure(client: AsyncClient):
    """Deleting an adventure removes it; subsequent GET returns 404."""
    ids = await _create_adventure(client)
    adv_id = ids["adventure_id"]

    del_resp = await client.delete(f"/api/adventures/{adv_id}")
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/api/adventures/{adv_id}")
    assert get_resp.status_code == 404


async def test_delete_adventure_not_found(client: AsyncClient):
    """Deleting a non-existent adventure returns 404."""
    resp = await client.delete("/api/adventures/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/adventures/{adventure_id}/state
# ---------------------------------------------------------------------------

async def test_get_game_state(client: AsyncClient):
    """The initial game state has scene_id='START' and in_game_time=0."""
    ids = await _create_adventure(client)

    resp = await client.get(f"/api/adventures/{ids['adventure_id']}/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scene_id"] == "START"
    assert data["in_game_time"] == 0
    assert data["is_paused"] is False


# ---------------------------------------------------------------------------
# PATCH /api/adventures/{adventure_id}/state
# ---------------------------------------------------------------------------

async def test_update_game_state_scene(client: AsyncClient):
    """Patching the game state updates scene_id."""
    ids = await _create_adventure(client)

    resp = await client.patch(
        f"/api/adventures/{ids['adventure_id']}/state",
        json={"scene_id": "DUNGEON_ENTRANCE"},
    )
    assert resp.status_code == 200

    state_resp = await client.get(f"/api/adventures/{ids['adventure_id']}/state")
    assert state_resp.json()["scene_id"] == "DUNGEON_ENTRANCE"


# ---------------------------------------------------------------------------
# POST /api/adventures/{adventure_id}/pause & /resume
# ---------------------------------------------------------------------------

async def test_pause_and_resume_game(client: AsyncClient):
    """Pausing sets is_paused=True; resuming sets it back to False."""
    ids = await _create_adventure(client)
    adv_id = ids["adventure_id"]

    # Pause
    pause_resp = await client.post(f"/api/adventures/{adv_id}/pause")
    assert pause_resp.status_code == 200

    state = (await client.get(f"/api/adventures/{adv_id}/state")).json()
    assert state["is_paused"] is True

    # Resume
    resume_resp = await client.post(f"/api/adventures/{adv_id}/resume")
    assert resume_resp.status_code == 200

    state = (await client.get(f"/api/adventures/{adv_id}/state")).json()
    assert state["is_paused"] is False


# ---------------------------------------------------------------------------
# POST /api/adventures/import
# ---------------------------------------------------------------------------

async def test_import_adv_payload_maps_protagonist_and_manifest(client: AsyncClient):
    """Importing an ADV payload maps protagonist fields and persists original_manifest."""
    payload = {
        "version": "1.0",
        "title": "Imported Quest",
        "story_idea": "A direct import test.",
        "protagonist": {
            "name": "Aria",
            "role": "Scout",
            "description": "A keen-eyed trailblazer.",
        },
        "pacing": {
            "scene_length": "short",
            "event_frequency": "high",
            "notes": "Fast pace",
        },
        "generate_npc_images": True,
        "generate_item_images": True,
        "automatic_cover_generation": True,
    }

    import_resp = await client.post("/api/adventures/import", json=payload)
    assert import_resp.status_code == 201, import_resp.text
    ids = import_resp.json()

    debug_resp = await client.get(f"/api/adventures/{ids['adventure_id']}/debug")
    assert debug_resp.status_code == 200
    debug_data = debug_resp.json()

    original_manifest = debug_data["adventure"]["original_manifest"]
    assert original_manifest["title"] == "Imported Quest"
    assert original_manifest["pacing"]["scene_length"] == "short"
    assert original_manifest["generate_npc_images"] is True
    assert original_manifest["generate_item_images"] is True
    assert original_manifest["automatic_cover_generation"] is True

    session_resp = await client.get(f"/api/adventures/{ids['adventure_id']}/export/session")
    assert session_resp.status_code == 200
    session_data = session_resp.json()
    assert session_data["avatar"]["name"] == "Aria"
    assert session_data["avatar"]["role"] == "Scout"
    assert session_data["avatar"]["description"] == "A keen-eyed trailblazer."


# ---------------------------------------------------------------------------
# POST /api/adventures/import/session-bundle
# ---------------------------------------------------------------------------

async def test_import_session_bundle_uses_split_route(client: AsyncClient):
    """Session bundle imports use the dedicated split route and return SESSION type."""
    payload = {
        "version": "1.0",
        "type": "SESSION_BUNDLE",
        "adventure": {
            "title": "Bundle Quest",
            "context": "Restored context",
            "image_url": None,
            "strict_rules": True,
            "time_per_turn": 5,
            "game_over_rules": None,
            "original_manifest": {"version": "1.0", "title": "Bundle Quest"},
        },
        "scenes": [],
        "exits": [],
        "entities": [],
        "game_state": None,
        "avatar": None,
        "chat_history": [],
    }

    resp = await client.post("/api/adventures/import/session-bundle", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "imported"
    assert data["type"] == "SESSION"
    assert data["adventure_id"]


async def test_import_adv_file_keeps_quests_npcs_and_initial_scene(client: AsyncClient):
    """ADV file import should keep world data and set the first scene as active."""
    adv_payload = {
        "format": "taleweaver.adz",
        "version": "1.0",
        "type": "ADVENTURE_BLUEPRINT",
        "adventure": {
            "title": "ADV File Import Quest",
            "context": "Imported from file",
            "strict_rules": True,
            "rule_enforcement_mode": "story",
            "time_per_turn": 5,
            "pacing_minutes": 5,
            "clock_enabled": False,
            "heartbeat_enabled": False,
            "generate_scene_images": False,
            "generate_npc_images": False,
            "generate_item_images": False,
            "quests": [
                {
                    "id": "Q_MAIN",
                    "title": "Imported Main Quest",
                    "description": "Should survive ADV import",
                    "goal": "Do the thing",
                    "impact": "World changes",
                    "exp_reward": 100,
                    "is_main": True,
                    "status": "open",
                }
            ],
            "awards": [
                {
                    "key": "IMP_AWARD",
                    "title": "Imported Award",
                    "description": "Should survive ADV import",
                    "tier": "bronze",
                    "requirement": "Finish Q_MAIN",
                    "is_earned": False,
                }
            ],
        },
        "protagonist": {
            "name": "Import Hero",
            "role": "Tester",
            "description": "Checks import",
            "inventory": [],
            "equipment": {},
            "stats": {},
        },
        "scenes": [
            {"id": "ROOM_A", "name": "Room A", "description": "First room"},
            {"id": "ROOM_B", "name": "Room B", "description": "Second room"},
        ],
        "exits": [
            {
                "from_scene_id": "ROOM_A",
                "to_scene_id": "ROOM_B",
                "label": "door",
                "is_locked": False,
                "lock_description": None,
            }
        ],
        "npcs": [
            {
                "id": "NPC_A",
                "name": "Import NPC",
                "description": "Should exist after import",
                "start_scene_id": "ROOM_A",
                "spatial_position": "near the door",
                "is_hidden": False,
            }
        ],
        "objects": [
            {
                "id": "OBJ_A",
                "name": "Import Object",
                "description": "Should exist after import",
                "start_scene_id": "ROOM_A",
                "spatial_position": "on the floor",
                "item_type": "PICKABLE",
                "is_hidden": False,
            }
        ],
    }

    file_bytes = json.dumps(adv_payload).encode("utf-8")
    resp = await client.post(
        "/api/adventures/import/adv",
        files={"file": ("import_test.adv", file_bytes, "application/json")},
    )
    assert resp.status_code == 201, resp.text
    adventure_id = resp.json()["adventure_id"]

    debug_resp = await client.get(f"/api/adventures/{adventure_id}/debug")
    assert debug_resp.status_code == 200, debug_resp.text
    debug_data = debug_resp.json()

    assert len(debug_data.get("scenes", [])) == 2
    assert any(npc.get("id") == "NPC_A" for npc in debug_data.get("npcs", []))
    assert any(obj.get("id") == "OBJ_A" for obj in debug_data.get("objects", []))
    assert any(q.get("id") == "Q_MAIN" for q in (debug_data.get("adventure", {}).get("quests", []) or []))
    assert any(a.get("key") == "IMP_AWARD" for a in (debug_data.get("adventure", {}).get("awards", []) or []))

    state_resp = await client.get(f"/api/adventures/{adventure_id}/state")
    assert state_resp.status_code == 200, state_resp.text
    state_data = state_resp.json()
    assert (state_data.get("scene_id") or state_data.get("current_scene_id")) == "ROOM_A"
