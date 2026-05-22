"""
Tests for the Adventures REST API (Package 4).

Covers: create, list, get, update, delete, pause/resume, and game-state
sub-routes. All tests follow the Arrange-Act-Assert pattern.
"""
import json
import os
import zipfile
from io import BytesIO

import pytest
import pytest_asyncio
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import delete, func, select

from backend.core.config import settings
from backend.engine.debug_engine import DebugEngine
from backend.api.routes.adventures.schemas import StoryIdeaSuggestionResponse
from backend.models.adventure_template import AdventureTemplate as Adventure
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState as GameState
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldScene
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
        "/api/adventures/",
        json={"title": title, "avatar_name": "Hero"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# POST /api/adventures/
# ---------------------------------------------------------------------------

async def test_create_adventure_returns_ids(client: AsyncClient):
    """Creating an adventure returns game_id, adventure_id, and avatar_id."""
    # Arrange & Act
    data = await _create_adventure(client)

    # Assert
    assert "game_id" in data
    assert "adventure_id" in data
    assert "avatar_id" in data


async def test_suggest_story_idea_generates_title_and_story_when_empty(client: AsyncClient, monkeypatch):
    """Story idea endpoint generates both title and story for empty input and clamps title length."""

    async def fake_story_suggest(self, system_prompt, user_prompt, response_model, model, **kwargs):
        assert "Narrative Tone: Horror" in user_prompt
        assert "Rule Mode: STORY" in user_prompt
        assert "User Provided Content: no" in user_prompt
        return StoryIdeaSuggestionResponse(
            title="This generated title is intentionally far too long to exceed fifty characters",
            story_idea="A cursed observatory reopens at midnight, and every wish granted by its telescope demands a memory in return.",
        )

    monkeypatch.setattr(
        "backend.api.routes.adventures.templates.GameMasterLLM.aexecute_complex_task",
        fake_story_suggest,
    )

    resp = await client.post(
        "/api/adventures/story-idea/suggest",
        json={
            "title": "",
            "story_idea": "",
            "selected_tone": {"id": "horror", "name": "Horror"},
            "rule_enforcement_mode": "story",
            "language": "German",
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["title"]) <= 50
    assert data["story_idea"]


async def test_suggest_story_idea_keeps_existing_title_on_optimization(client: AsyncClient, monkeypatch):
    """When input exists and title is present, endpoint keeps the existing title but updates story text."""

    async def fake_story_suggest(self, system_prompt, user_prompt, response_model, model, **kwargs):
        assert "User Provided Content: yes" in user_prompt
        assert "Rule Mode: RPG" in user_prompt
        return StoryIdeaSuggestionResponse(
            title="Different Returned Title",
            story_idea="Optimized premise: your artifact hunt becomes a survival race through collapsing ruins.",
        )

    monkeypatch.setattr(
        "backend.api.routes.adventures.templates.GameMasterLLM.aexecute_complex_task",
        fake_story_suggest,
    )

    resp = await client.post(
        "/api/adventures/story-idea/suggest",
        json={
            "title": "Ancient Ruins",
            "story_idea": "Find the artifact.",
            "selected_tone": {"id": "adventure", "name": "Adventure"},
            "rule_enforcement_mode": "rpg",
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["title"] == "Ancient Ruins"
    assert "Optimized premise" in data["story_idea"]


async def test_start_session_emits_intro_text_once(client: AsyncClient):
    """A new session should include adventure intro_text as initial system message when provided."""
    ids = await _create_adventure(client, "Intro Session Quest")
    adv_id = ids["adventure_id"]

    patch_resp = await client.patch(
        f"/api/adventures/{adv_id}",
        json={"intro_text": "Welcome to the Archivum. Read the codex before proceeding."},
    )
    assert patch_resp.status_code == 200, patch_resp.text

    start_resp = await client.post(f"/api/adventures/{adv_id}/sessions/start")
    assert start_resp.status_code == 201, start_resp.text
    game_id = start_resp.json()["game_id"]

    chat_resp = await client.get(f"/api/adventures/{game_id}/chat")
    assert chat_resp.status_code == 200, chat_resp.text
    messages = chat_resp.json().get("messages", [])
    assert any(m.get("role") == "system" and "Welcome to the Archivum" in (m.get("content") or "") for m in messages)


async def test_create_adventure_creates_one_visible_session(client: AsyncClient):
    """A single create call should result in exactly one visible session row."""
    # Arrange & Act
    ids = await _create_adventure(client)

    # Assert
    resp = await client.get("/api/adventures/sessions")
    assert resp.status_code == 200
    sessions = resp.json()
    assert len(sessions) == 1
    assert sessions[0]["adventure_id"] == ids["adventure_id"]
    assert sessions[0]["game_id"] == ids["game_id"]


async def test_create_adventure_materializes_initial_session_as_independent_copy(client: AsyncClient, monkeypatch, tmp_path):
    """After generation, the initial auto-created session should own world rows and copied visuals."""
    data_dir = tmp_path / "data"
    monkeypatch.setattr(settings, "DATA_DIR", str(data_dir))

    async def fake_generate_world(db, user=None, template_id=None, adventure_id=None, *args, **kwargs):
        adv_id = template_id or adventure_id
        assert adv_id

        cover_rel = f"adventures/library/{adv_id}/cover.png"
        hero_rel = f"adventures/library/{adv_id}/hero.png"
        scene_rel = f"adventures/library/{adv_id}/scenes/start.png"
        entity_rel = f"adventures/library/{adv_id}/entities/npc.png"

        os.makedirs(data_dir / "adventures" / "library" / adv_id / "scenes", exist_ok=True)
        os.makedirs(data_dir / "adventures" / "library" / adv_id / "entities", exist_ok=True)
        (data_dir / cover_rel).write_bytes(b"cover")
        (data_dir / hero_rel).write_bytes(b"hero")
        (data_dir / scene_rel).write_bytes(b"scene")
        (data_dir / entity_rel).write_bytes(b"entity")

        adventure = await db.get(Adventure, adv_id)
        assert adventure is not None
        adventure.image_url = f"/data/{cover_rel}"

        avatar_res = await db.execute(select(Avatar).where(Avatar.template_id == adv_id).limit(1))
        avatar = avatar_res.scalars().first()
        assert avatar is not None
        avatar.profile_image = f"/data/{hero_rel}"

        db.add(
            WorldScene(
                id="START",
                template_id=adv_id,
                label="Start",
                description="Generated start scene",
                image_url=f"/data/{scene_rel}",
            )
        )
        db.add(
            WorldEntity(
                id="AUTO_NPC",
                template_id=adv_id,
                session_id=None,
                entity_type="NPC",
                name="Auto NPC",
                description="Generated NPC",
                current_scene_id="START",
                image_url=f"/data/{entity_rel}",
            )
        )
        await db.commit()

    monkeypatch.setattr("backend.api.routes.adventures.templates.WorldGenerator.generate_world", fake_generate_world)

    ids = await _create_adventure(client, "Initial Session Materialization Quest")
    game_id = ids["game_id"]

    def _url_to_file_path(url: str) -> str:
        rel = url.replace("/data/", "", 1).lstrip("/")
        return os.path.join(str(data_dir), rel)

    async with TestSessionLocal() as session:
        game_session = await session.get(GameSession, game_id)
        assert game_session is not None
        assert game_session.adventure_image_url.startswith(f"/data/adventures/sessions/{game_id}/visuals/")
        assert os.path.isfile(_url_to_file_path(game_session.adventure_image_url))

        avatar_res = await session.execute(select(Avatar).where(Avatar.id == game_session.avatar_id))
        avatar = avatar_res.scalars().first()
        assert avatar is not None
        assert avatar.profile_image.startswith(f"/data/adventures/sessions/{game_id}/visuals/")
        assert os.path.isfile(_url_to_file_path(avatar.profile_image))

        state_res = await session.execute(select(SessionState).where(SessionState.session_id == game_id))
        state = state_res.scalars().first()
        assert state is not None
        snapshot = dict((state.entity_states or {}).get("__asset_snapshot__") or {})
        assert snapshot.get("cover", "").startswith(f"/data/adventures/sessions/{game_id}/visuals/")
        assert snapshot.get("protagonist", "").startswith(f"/data/adventures/sessions/{game_id}/visuals/")
        assert snapshot.get("entity_images", {}).get("AUTO_NPC", "").startswith(
            f"/data/adventures/sessions/{game_id}/visuals/"
        )

        scene_res = await session.execute(
            select(WorldScene).where(
                WorldScene.session_id == game_id,
                WorldScene.id == "START",
            )
        )
        cloned_scene = scene_res.scalars().first()
        assert cloned_scene is not None
        assert cloned_scene.image_url.startswith(f"/data/adventures/sessions/{game_id}/visuals/")
        assert os.path.isfile(_url_to_file_path(cloned_scene.image_url))

        entity_res = await session.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == game_id,
                WorldEntity.id == "AUTO_NPC",
            )
        )
        cloned_entity = entity_res.scalars().first()
        assert cloned_entity is not None
        assert cloned_entity.image_url.startswith(f"/data/adventures/sessions/{game_id}/visuals/")
        assert os.path.isfile(_url_to_file_path(cloned_entity.image_url))


async def test_post_chat_stream_includes_turn_correlation_id(client: AsyncClient):
    """Chat stream responses expose a per-turn correlation id in header and SSE fields."""
    ids = await _create_adventure(client, "Turn Correlation Quest")

    resp = await client.post(
        f"/api/adventures/{ids['game_id']}/chat",
        json={"content": "look around"},
    )

    assert resp.status_code == 200, resp.text
    turn_id = resp.headers.get("x-taleweaver-turn-id")
    assert turn_id

    body = resp.text
    assert f"id: {turn_id}" in body
    assert "event:" in body


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

    resp = await client.post("/api/adventures/", json=payload)
    assert resp.status_code == 201
    ids = resp.json()

    adv_resp = await client.get(f"/api/adventures/{ids['adventure_id']}")
    assert adv_resp.status_code == 200
    adv = adv_resp.json()
    assert adv["rule_enforcement_mode"] == "story"
    assert adv["strict_rules"] is True
    assert adv["clock_enabled"] is True
    assert adv["pacing_minutes"] == 12
    assert adv["selected_tone"]["id"] == "horror"
    assert any(style["id"] == "dark-fantasy-painting" for style in adv["selected_image_styles"])


async def test_create_cover_adventure_persists_source_metadata(client: AsyncClient):
    """Cover create payloads persist source adventure linkage and export it in manifest responses."""
    source = await _create_adventure(client, "Source Quest")

    payload = {
        "title": "(Cover) Source Quest",
        "avatar_name": "Cover Hero",
        "cover_source_adventure_id": source["adventure_id"],
        "cover_similarity_percent": 82,
        "allow_reuse_source_assets": False,
    }

    create_resp = await client.post("/api/adventures/", json=payload)
    assert create_resp.status_code == 201, create_resp.text
    cover_id = create_resp.json()["adventure_id"]

    adv_resp = await client.get(f"/api/adventures/{cover_id}")
    assert adv_resp.status_code == 200, adv_resp.text
    adv_data = adv_resp.json()

    assert adv_data["cover_source_adventure_id"] == source["adventure_id"]
    assert adv_data["cover_source_adventure_name"] == "Source Quest"
    assert adv_data["cover_similarity_percent"] == 82
    assert adv_data["allow_reuse_source_assets"] is False

    export_adv_resp = await client.get(f"/api/adventures/{cover_id}/export/adv")
    assert export_adv_resp.status_code == 200, export_adv_resp.text
    export_adv_data = export_adv_resp.json()
    adventure_meta = export_adv_data.get("adventure") or {}
    assert adventure_meta.get("cover_source_adventure_id") == source["adventure_id"]
    assert adventure_meta.get("cover_source_adventure_name") == "Source Quest"
    assert adventure_meta.get("cover_similarity_percent") == 82
    assert adventure_meta.get("allow_reuse_source_assets") is False


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

    resp = await client.post("/api/adventures/", json=payload)
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
        user=None,
        template_id=None,
        adventure_id=None,
        *_args,
        **_kwargs,
    ):
        adv_id = template_id or adventure_id
        print(f"DEBUG: fake_generate_world called with adv_id={adv_id}")
        from sqlalchemy import select
        res = await db.execute(select(Adventure))
        all_advs = res.scalars().all()
        print(f"DEBUG: all adventures in DB: {[a.id for a in all_advs]}")
        adventure = await db.get(Adventure, adv_id)
        assert adventure is not None
        captured["status"] = adventure.creation_status or ""

        db.add(
            WorldScene(
                id="START",
                adventure_id=adv_id,
                label="Starting Room",
                description="A minimal scene created by the test double.",
                image_url=None,
            )
        )
        await db.commit()

    monkeypatch.setattr("backend.api.routes.adventures.templates.WorldGenerator.generate_world", fake_generate_world)

    resp = await client.post(
        "/api/adventures/",
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

        game_session = GameSession(
            user_id=user.id,
            avatar_id=avatar.id,
            template_id=adventure.id,
            status="active",
        )
        session.add(game_session)
        await session.flush()

        state = GameState(
            session_id=game_session.id,
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


async def test_get_chat_history_accepts_adventure_id_alias(client: AsyncClient):
    """GET /chat should resolve adventure/template ids to the latest session for that user."""
    ids = await _create_adventure(client, "Alias Route Quest")

    chat_resp = await client.get(f"/api/adventures/{ids['adventure_id']}/chat")
    assert chat_resp.status_code == 200, chat_resp.text
    payload = chat_resp.json()

    assert "messages" in payload
    assert "sheet" in payload


async def test_terminal_epilogue_completed_updates_chat_flags(client: AsyncClient, monkeypatch):
    """Completed sessions should emit one epilogue and stay unlocked afterwards."""
    ids = await _create_adventure(client, "Completed Epilogue Quest")

    async with TestSessionLocal() as session:
        game_session = await session.get(GameSession, ids["game_id"])
        state_res = await session.execute(select(SessionState).where(SessionState.session_id == ids["game_id"]))
        state = state_res.scalars().first()
        assert game_session is not None
        if state is None:
            state = SessionState(
                session_id=ids["game_id"],
                template_id=ids["adventure_id"],
                avatar_id=ids["avatar_id"],
                user_id=game_session.user_id,
                current_scene_id="START",
            )
            session.add(state)
        game_session.status = "completed"
        game_session.status_note = "All main quests completed."
        state.exit_states = {}
        await session.commit()

    async def fake_epilogue(_self, language=None):
        _ = language
        return "The Game Master congratulates you and reads the final report."

    monkeypatch.setattr(
        "backend.api.routes.adventures.gameplay_logic.GameTurnManager._generate_terminal_epilogue_text",
        fake_epilogue,
    )

    epilogue_resp = await client.post(
        f"/api/adventures/{ids['game_id']}/terminal-epilogue",
        json={},
    )
    assert epilogue_resp.status_code == 200, epilogue_resp.text
    payload = epilogue_resp.json()
    assert payload["content"].startswith("The Game Master congratulates")
    assert payload["game_completed"] is True
    assert payload["pending_terminal_epilogue"] is False
    assert payload["input_locked"] is False

    chat_resp = await client.get(f"/api/adventures/{ids['game_id']}/chat")
    assert chat_resp.status_code == 200, chat_resp.text
    chat_payload = chat_resp.json()
    assert chat_payload["game_completed"] is True
    assert chat_payload["pending_terminal_epilogue"] is False
    assert chat_payload["input_locked"] is False
    assert any(
        msg.get("role") == "assistant" and "final report" in (msg.get("content") or "").lower()
        for msg in chat_payload.get("messages", [])
    )


async def test_terminal_epilogue_game_over_locks_input(client: AsyncClient, monkeypatch):
    """Game-over sessions should lock input after epilogue is generated."""
    ids = await _create_adventure(client, "Game Over Epilogue Quest")

    async with TestSessionLocal() as session:
        game_session = await session.get(GameSession, ids["game_id"])
        state_res = await session.execute(select(SessionState).where(SessionState.session_id == ids["game_id"]))
        state = state_res.scalars().first()
        assert game_session is not None
        if state is None:
            state = SessionState(
                session_id=ids["game_id"],
                template_id=ids["adventure_id"],
                avatar_id=ids["avatar_id"],
                user_id=game_session.user_id,
                current_scene_id="START",
            )
            session.add(state)
        game_session.status = "game_over"
        game_session.status_note = "The hero has fallen."
        state.exit_states = {}
        await session.commit()

    async def fake_epilogue(_self, language=None):
        _ = language
        return "The Game Master shares a compassionate closing report."

    monkeypatch.setattr(
        "backend.api.routes.adventures.gameplay_logic.GameTurnManager._generate_terminal_epilogue_text",
        fake_epilogue,
    )

    epilogue_resp = await client.post(
        f"/api/adventures/{ids['game_id']}/terminal-epilogue",
        json={},
    )
    assert epilogue_resp.status_code == 200, epilogue_resp.text
    payload = epilogue_resp.json()
    assert payload["game_over"] is True
    assert payload["pending_terminal_epilogue"] is False
    assert payload["input_locked"] is True

    chat_resp = await client.get(f"/api/adventures/{ids['game_id']}/chat")
    assert chat_resp.status_code == 200, chat_resp.text
    chat_payload = chat_resp.json()
    assert chat_payload["game_over"] is True
    assert chat_payload["pending_terminal_epilogue"] is False
    assert chat_payload["input_locked"] is True


async def test_regenerate_visual_updates_protagonist_image(client: AsyncClient, monkeypatch):
    """Regenerating the protagonist uses the default prompt when none is provided."""
    async def fake_generate_world(*args, **kwargs):
        pass
    monkeypatch.setattr("backend.api.routes.adventures.templates.WorldGenerator.generate_world", fake_generate_world)

    ids = await _create_adventure(client, "Regenerate Quest")

    async with TestSessionLocal() as session:
        avatar = await session.get(Avatar, ids["avatar_id"])
        assert avatar is not None
        avatar.profile_image = None
        await session.commit()

    captured: dict[str, str] = {}

    async def fake_generate_entity_image(prompt, adventure_id=None, entity_id=None, entity_type=None, user_config=None, api_keys=None, **kwargs):
        captured["prompt"] = prompt
        captured["entity_id"] = entity_id
        captured["entity_type"] = entity_type
        return "/data/adventures/generated/protagonist.png"

    monkeypatch.setattr("backend.api.routes.adventures.assets.MediaEngine.generate_entity_image", fake_generate_entity_image)

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
    async def fake_generate_world(*args, **kwargs):
        pass
    monkeypatch.setattr("backend.api.routes.adventures.templates.WorldGenerator.generate_world", fake_generate_world)

    ids = await _create_adventure(client, "Styled Prompt Quest")

    async with TestSessionLocal() as session:
        adventure = await session.get(Adventure, ids["adventure_id"])
        assert adventure is not None
        adventure.selected_image_styles = ["chalk-noir"]
        adventure.selected_tone = "horror"
        await session.commit()

    captured: dict[str, str] = {}

    async def fake_generate_entity_image(prompt, adventure_id=None, entity_id=None, entity_type=None, user_config=None, api_keys=None, **kwargs):
        captured["prompt"] = prompt
        captured["entity_id"] = entity_id
        captured["entity_type"] = entity_type
        return "/data/adventures/generated/protagonist-tone-style.png"

    monkeypatch.setattr("backend.api.routes.adventures.assets.MediaEngine.generate_entity_image", fake_generate_entity_image)

    resp = await client.post(
        f"/api/adventures/{ids['adventure_id']}/visuals/regenerate",
        json={"target_type": "protagonist", "target_id": ids["avatar_id"]},
    )
    assert resp.status_code == 200, resp.text
    assert "Style constraints" in captured["prompt"]
    assert "Narrative tone reference" in captured["prompt"]


async def test_regenerate_visual_uses_custom_prompt_for_scene(client: AsyncClient, monkeypatch):
    """A custom prompt overrides the default prompt when regenerating a scene image."""
    async def fake_generate_world(*args, **kwargs):
        pass
    monkeypatch.setattr("backend.api.routes.adventures.templates.WorldGenerator.generate_world", fake_generate_world)

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

    async def fake_generate_scene_image(prompt, adventure_id=None, user_config=None, api_keys=None, **kwargs):
        captured["prompt"] = prompt
        return "/data/adventures/generated/scene.png"

    monkeypatch.setattr("backend.api.routes.adventures.assets.MediaEngine.generate_scene_image", fake_generate_scene_image)

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

    async def fake_generate_adventure_cover(title=None, original_prompt=None, adventure_id=None, **kwargs):
        captured["title"] = title
        captured["context"] = original_prompt or kwargs.get("context")
        captured["adventure_id"] = adventure_id
        return "/data/adventures/generated/cover.png"

    monkeypatch.setattr("backend.api.routes.adventures.assets.MediaEngine.generate_adventure_cover", fake_generate_adventure_cover)

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
    assert f"/protagonist/{ids['avatar_id']}_" in data["image_url"]
    assert data["image_url"].endswith(".png")

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

        state_res = await session.execute(select(SessionState).where(SessionState.template_id == ids["adventure_id"]))
        state = state_res.scalars().first()
        assert state is not None
        state.current_scene_id = "HALL"

        avatar = await session.get(Avatar, ids["avatar_id"])
        assert avatar is not None
        avatar.profile_image = protagonist_img

        await session.execute(delete(WorldScene).where(WorldScene.template_id == ids["adventure_id"]))
        await session.execute(delete(WorldEntity).where(WorldEntity.template_id == ids["adventure_id"]))

        session.add(
            WorldScene(
                id="HALL",
                template_id=ids["adventure_id"],
                label="Hall",
                description="A simple corridor",
                image_url=scene_img,
            )
        )
        session.add(
            WorldEntity(
                id="GUIDE",
                template_id=ids["adventure_id"],
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
                WorldScene.template_id == ids["adventure_id"],
                WorldScene.id == "HALL",
            )
        )
        hall_scene = hall_scene_res.scalars().first()
        assert hall_scene is not None
        assert hall_scene.image_url == scene_img

        guide_res = await session.execute(
            select(WorldEntity).where(
                WorldEntity.template_id == ids["adventure_id"],
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

    resp = await client.post("/api/adventures/", json=payload)
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

    resp = await client.post("/api/adventures/", json=payload)
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
    resp = await client.get("/api/adventures/sessions")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_adventures_returns_created(client: AsyncClient):
    """After creating two adventures, both appear in the list."""
    await _create_adventure(client, "Quest A")
    await _create_adventure(client, "Quest B")

    resp = await client.get("/api/adventures/sessions")
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
    assert del_resp.status_code == 200

    get_resp = await client.get(f"/api/adventures/{adv_id}")
    assert get_resp.status_code == 404


async def test_delete_adventure_not_found(client: AsyncClient):
    """Deleting a non-existent adventure returns 404."""
    resp = await client.delete("/api/adventures/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_delete_adventure_keeps_existing_sessions(client: AsyncClient):
    """Deleting a template must not remove or break already-started sessions."""
    ids = await _create_adventure(client, "Session Survival Quest")
    adv_id = ids["adventure_id"]

    start_resp = await client.post(f"/api/adventures/{adv_id}/sessions/start")
    assert start_resp.status_code == 201, start_resp.text
    started_game_id = start_resp.json()["game_id"]

    del_resp = await client.delete(f"/api/adventures/{adv_id}")
    assert del_resp.status_code == 200, del_resp.text

    sessions_resp = await client.get("/api/adventures/sessions")
    assert sessions_resp.status_code == 200, sessions_resp.text
    sessions = sessions_resp.json()
    assert any(s.get("game_id") == started_game_id for s in sessions)

    chat_resp = await client.get(f"/api/adventures/{started_game_id}/chat")
    assert chat_resp.status_code == 200, chat_resp.text


async def test_delete_adventure_removes_library_folder_even_with_sessions(client: AsyncClient, monkeypatch, tmp_path):
    """Deleting a template must remove its library folder, even when sessions still exist."""
    data_dir = tmp_path / "data"
    monkeypatch.setattr(settings, "DATA_DIR", str(data_dir))

    ids = await _create_adventure(client, "Folder Cleanup Quest")
    adv_id = ids["adventure_id"]

    library_dir = data_dir / "adventures" / "library" / adv_id
    os.makedirs(library_dir, exist_ok=True)
    cover_path = library_dir / "cover.png"
    cover_path.write_bytes(b"fake-cover")

    async with TestSessionLocal() as session:
        adventure = await session.get(Adventure, adv_id)
        assert adventure is not None
        adventure.image_url = f"/data/adventures/library/{adv_id}/cover.png"
        await session.commit()

    start_resp = await client.post(f"/api/adventures/{adv_id}/sessions/start")
    assert start_resp.status_code == 201, start_resp.text

    del_resp = await client.delete(f"/api/adventures/{adv_id}")
    assert del_resp.status_code == 200, del_resp.text

    assert not library_dir.exists()


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
    assert resp.status_code == 200, resp.text
    assert resp.json().get("status") == "success"

    templates_resp = await client.get("/api/adventures/templates")
    assert templates_resp.status_code == 200, templates_resp.text
    template_row = next(
        (row for row in templates_resp.json() if row.get("title") == "ADV File Import Quest"),
        None,
    )
    assert template_row is not None
    assert template_row.get("is_ready") is True
    assert template_row.get("creation_status") == "Ready"
    adventure_id = template_row["template_id"]

    debug_resp = await client.get(f"/api/adventures/{adventure_id}/debug")
    assert debug_resp.status_code == 200, debug_resp.text
    debug_data = debug_resp.json()

    assert len(debug_data.get("scenes", [])) == 2
    assert any(npc.get("id") == "NPC_A" for npc in debug_data.get("npcs", []))
    assert any(obj.get("id") == "OBJ_A" for obj in debug_data.get("objects", []))
    assert (debug_data.get("adventure") or {}).get("rule_enforcement_mode") == "story"


async def test_import_adv_file_missing_start_scene_id_uses_fallback(client: AsyncClient):
    """ADV import should not fail if start_scene_id is missing on NPCs/objects."""
    adv_payload = {
        "format": "taleweaver.adz",
        "version": "1.0",
        "type": "ADVENTURE_BLUEPRINT",
        "adventure": {
            "title": "ADV Missing Start Scene Import",
            "context": "Imported from file without explicit start scene ids",
            "strict_rules": True,
            "rule_enforcement_mode": "story",
            "time_per_turn": 5,
        },
        "protagonist": {
            "name": "Fallback Hero",
            "role": "Tester",
            "description": "Checks fallback behavior",
            "inventory": [],
            "equipment": {},
            "stats": {},
        },
        "scenes": [
            {"id": "ROOM_FALLBACK", "name": "Room Fallback", "description": "First room"},
            {"id": "ROOM_SECOND", "name": "Room Second", "description": "Second room"},
        ],
        "exits": [],
        "npcs": [
            {
                "id": "NPC_NO_START",
                "name": "Import NPC",
                "description": "No explicit start scene",
                "spatial_position": "near the door",
                "is_hidden": False,
            }
        ],
        "objects": [
            {
                "id": "OBJ_NO_START",
                "name": "Import Object",
                "description": "No explicit start scene",
                "spatial_position": "on the floor",
                "item_type": "PICKABLE",
                "is_hidden": False,
            }
        ],
    }

    file_bytes = json.dumps(adv_payload).encode("utf-8")
    resp = await client.post(
        "/api/adventures/import/adv",
        files={"file": ("import_missing_start_scene.adv", file_bytes, "application/json")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json().get("status") == "success"

    templates_resp = await client.get("/api/adventures/templates")
    assert templates_resp.status_code == 200, templates_resp.text
    template_row = next(
        (row for row in templates_resp.json() if row.get("title") == "ADV Missing Start Scene Import"),
        None,
    )
    assert template_row is not None
    assert template_row.get("is_ready") is True
    assert template_row.get("creation_status") == "Ready"
    adventure_id = template_row["template_id"]

    debug_resp = await client.get(f"/api/adventures/{adventure_id}/debug")
    assert debug_resp.status_code == 200, debug_resp.text
    debug_data = debug_resp.json()

    npc = next((n for n in debug_data.get("npcs", []) if n.get("id") == "NPC_NO_START"), None)
    obj = next((o for o in debug_data.get("objects", []) if o.get("id") == "OBJ_NO_START"), None)
    assert npc is not None
    assert obj is not None
    assert npc.get("current_scene_id") == "ROOM_FALLBACK"
    assert obj.get("current_scene_id") == "ROOM_FALLBACK"


async def test_import_adv_file_npc_inventory_dict_entries(client: AsyncClient):
    """ADV import should accept NPC inventory entries as object dictionaries."""
    adv_payload = {
        "format": "taleweaver.adz",
        "version": "1.0",
        "type": "ADVENTURE_BLUEPRINT",
        "adventure": {
            "title": "ADV NPC Inventory Dict Import",
            "context": "Inventory entries provided as dicts",
            "strict_rules": True,
        },
        "protagonist": {
            "name": "Inventory Hero",
            "role": "Tester",
            "description": "Checks NPC inventory import",
            "inventory": [],
            "equipment": {},
            "stats": {},
        },
        "scenes": [
            {"id": "ROOM_A", "name": "Room A", "description": "First room"},
        ],
        "exits": [],
        "npcs": [
            {
                "id": "NPC_WITH_INV",
                "name": "Keeper",
                "description": "Keeps one item",
                "start_scene_id": "ROOM_A",
                "inventory": [{"id": "OBJ_DICT"}],
            }
        ],
        "objects": [
            {
                "id": "OBJ_DICT",
                "name": "Ledger",
                "description": "A worn ledger",
                "start_scene_id": "ROOM_A",
                "item_type": "PICKABLE",
            }
        ],
    }

    file_bytes = json.dumps(adv_payload).encode("utf-8")
    resp = await client.post(
        "/api/adventures/import/adv",
        files={"file": ("import_npc_inventory_dict.adv", file_bytes, "application/json")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json().get("status") == "success"

    templates_resp = await client.get("/api/adventures/templates")
    assert templates_resp.status_code == 200, templates_resp.text
    template_row = next(
        (row for row in templates_resp.json() if row.get("title") == "ADV NPC Inventory Dict Import"),
        None,
    )
    assert template_row is not None


async def test_import_adz_file_marks_template_ready(client: AsyncClient):
    """ADZ import should create a ready template instead of entering generation polling state."""
    adz_manifest = {
        "format": "taleweaver.adz",
        "version": "1.0",
        "type": "ADVENTURE_BLUEPRINT",
        "adventure": {
            "title": "ADZ Ready Import Quest",
            "context": "Imported from bundled ADZ",
            "strict_rules": True,
            "rule_enforcement_mode": "rpg",
            "time_per_turn": 5,
        },
        "protagonist": {
            "name": "Archive Runner",
            "role": "Tester",
            "description": "Verifies ADZ readiness after import.",
            "inventory": [],
            "equipment": {},
            "stats": {},
        },
        "scenes": [
            {"id": "ENTRY", "name": "Entry Hall", "description": "A calm starting area."},
            {"id": "LIBRARY", "name": "Library", "description": "Shelves filled with lore."},
        ],
        "exits": [
            {
                "from_scene_id": "ENTRY",
                "to_scene_id": "LIBRARY",
                "label": "archway",
                "is_locked": False,
                "lock_description": None,
            }
        ],
        "npcs": [],
        "objects": [],
    }

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("adventure.adv", json.dumps(adz_manifest))
    zip_buffer.seek(0)

    resp = await client.post(
        "/api/adventures/import/adz",
        files={"file": ("ready_import.adz", zip_buffer.getvalue(), "application/zip")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json().get("status") == "success"

    templates_resp = await client.get("/api/adventures/templates")
    assert templates_resp.status_code == 200, templates_resp.text
    template_row = next(
        (row for row in templates_resp.json() if row.get("title") == "ADZ Ready Import Quest"),
        None,
    )
    assert template_row is not None
    assert template_row.get("is_ready") is True
    assert template_row.get("creation_status") == "Ready"


async def test_import_adv_preserves_item_stats_from_starting_inventory_dict(client: AsyncClient):
    """ADV import should keep item stat modifiers when they are present in starting_inventory item dicts."""
    adv_payload = {
        "format": "taleweaver.adz",
        "version": "1.0",
        "type": "ADVENTURE_BLUEPRINT",
        "adventure": {
            "title": "ADV Keep Item Stats",
            "context": "Stat roundtrip check",
            "strict_rules": True,
        },
        "protagonist": {
            "name": "Stat Hero",
            "role": "Tester",
            "description": "Carries a stat item",
            "starting_inventory": [
                {
                    "id": "OBJ_STAT_RING",
                    "name": "Silver Ring",
                    "description": "A ring that boosts charisma.",
                    "item_type": "WEARABLE",
                    "wearable_slots": ["Ring_1"],
                    "stat_modifier_charisma": 3,
                }
            ],
            "starting_equipment": {},
            "stats": {},
        },
        "scenes": [
            {"id": "ROOM_A", "name": "Room A", "description": "First room"},
        ],
        "exits": [],
        "npcs": [],
        "objects": [
            {
                "id": "OBJ_STAT_RING",
                "name": "Silver Ring",
                "description": "A ring that boosts charisma.",
                "start_scene_id": "ROOM_A",
                "item_type": "WEARABLE",
                "wearable_slots": ["Ring_1"],
            }
        ],
    }

    file_bytes = json.dumps(adv_payload).encode("utf-8")
    resp = await client.post(
        "/api/adventures/import/adv",
        files={"file": ("import_keep_item_stats.adv", file_bytes, "application/json")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json().get("status") == "success"

    templates_resp = await client.get("/api/adventures/templates")
    assert templates_resp.status_code == 200, templates_resp.text
    template_row = next(
        (row for row in templates_resp.json() if row.get("title") == "ADV Keep Item Stats"),
        None,
    )
    assert template_row is not None

    adventure_id = template_row["template_id"]
    debug_resp = await client.get(f"/api/adventures/{adventure_id}/debug")
    assert debug_resp.status_code == 200, debug_resp.text
    debug_data = debug_resp.json()

    stat_obj = next((o for o in debug_data.get("objects", []) if o.get("id") == "OBJ_STAT_RING"), None)
    assert stat_obj is not None
    assert stat_obj.get("stat_modifier_charisma") == 3


async def test_import_adv_preserves_consumable_effects_in_avatar_inventory(client: AsyncClient):
    """ADV import should keep consumable hp/mana/stamina effects inside protagonist inventory items."""
    adv_payload = {
        "format": "taleweaver.adz",
        "version": "1.0",
        "type": "ADVENTURE_BLUEPRINT",
        "adventure": {
            "title": "ADV Keep Consumable Effects",
            "context": "Consumable effect roundtrip check",
            "strict_rules": True,
        },
        "protagonist": {
            "name": "Potion Hero",
            "role": "Tester",
            "description": "Carries a healing potion",
            "starting_inventory": [
                {
                    "id": "HEILTRANK_1",
                    "name": "Heiltrank",
                    "description": "Ein kleiner Flakon mit roter Fluessigkeit.",
                    "item_type": "CONSUMABLE",
                    "hp_change": 50,
                    "stamina_change": 0,
                    "mana_change": 0,
                }
            ],
            "starting_equipment": {},
            "stats": {},
        },
        "scenes": [
            {"id": "ROOM_A", "name": "Room A", "description": "First room"},
        ],
        "exits": [],
        "npcs": [],
        "objects": [
            {
                "id": "HEILTRANK_1",
                "name": "Heiltrank",
                "description": "Ein kleiner Flakon mit roter Fluessigkeit.",
                "start_scene_id": "ROOM_A",
                "item_type": "CONSUMABLE",
            }
        ],
    }

    file_bytes = json.dumps(adv_payload).encode("utf-8")
    resp = await client.post(
        "/api/adventures/import/adv",
        files={"file": ("import_keep_consumable_effects.adv", file_bytes, "application/json")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json().get("status") == "success"

    templates_resp = await client.get("/api/adventures/templates")
    assert templates_resp.status_code == 200, templates_resp.text
    template_row = next(
        (row for row in templates_resp.json() if row.get("title") == "ADV Keep Consumable Effects"),
        None,
    )
    assert template_row is not None

    adventure_id = template_row["template_id"]
    debug_resp = await client.get(f"/api/adventures/{adventure_id}/debug")
    assert debug_resp.status_code == 200, debug_resp.text
    debug_data = debug_resp.json()

    inv_item = next(
        (item for item in (debug_data.get("protagonist") or {}).get("inventory", []) if item.get("id") == "HEILTRANK_1"),
        None,
    )
    assert inv_item is not None
    assert inv_item.get("hp_change") == 50
    assert inv_item.get("stamina_change") == 0
    assert inv_item.get("mana_change") == 0

    start_resp = await client.post(f"/api/adventures/{adventure_id}/sessions/start")
    assert start_resp.status_code == 201, start_resp.text
    game_id = start_resp.json()["game_id"]

    integrity_resp = await client.get(f"/api/adventures/sessions/{game_id}/integrity/items")
    assert integrity_resp.status_code == 200, integrity_resp.text
    integrity = integrity_resp.json()
    assert integrity["issue_count"] == 0


async def test_chat_snapshot_inventory_readable_uses_text_log_content(client: AsyncClient):
    """Session chat payload should include READABLE inventory text from metadata_json."""
    adv_payload = {
        "format": "taleweaver.adz",
        "version": "1.0",
        "type": "ADVENTURE_BLUEPRINT",
        "adventure": {
            "title": "ADV Readable Inventory Snapshot",
            "context": "Readable text log payload check",
            "strict_rules": True,
        },
        "protagonist": {
            "name": "Reader Hero",
            "role": "Technician",
            "description": "Carries a datapad",
            "starting_inventory": [
                {
                    "id": "DATAPAD",
                    "name": "Dienstliches Datapad",
                    "description": "Ein robustes Tablet mit gesprungenem Display.",
                    "item_type": "READABLE",
                }
            ],
            "starting_equipment": {},
            "stats": {},
        },
        "scenes": [
            {"id": "ROOM_A", "name": "Room A", "description": "First room"},
        ],
        "exits": [],
        "npcs": [],
        "objects": [
            {
                "id": "DATAPAD",
                "name": "Dienstliches Datapad",
                "description": "Ein robustes Tablet mit gesprungenem Display.",
                "start_scene_id": "ROOM_A",
                "item_type": "READABLE",
                "text_log_content": "ACHTUNG: Zugangscode 7391. Frequenz 733.3 kHz aktiv.",
                "text_log_format": "DOCUMENT",
            }
        ],
    }

    file_bytes = json.dumps(adv_payload).encode("utf-8")
    resp = await client.post(
        "/api/adventures/import/adv",
        files={"file": ("import_readable_inventory_snapshot.adv", file_bytes, "application/json")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json().get("status") == "success"

    templates_resp = await client.get("/api/adventures/templates")
    assert templates_resp.status_code == 200, templates_resp.text
    template_row = next(
        (row for row in templates_resp.json() if row.get("title") == "ADV Readable Inventory Snapshot"),
        None,
    )
    assert template_row is not None

    start_resp = await client.post(f"/api/adventures/{template_row['template_id']}/sessions/start")
    assert start_resp.status_code == 201, start_resp.text
    game_id = start_resp.json()["game_id"]

    chat_resp = await client.get(f"/api/adventures/{game_id}/chat")
    assert chat_resp.status_code == 200, chat_resp.text
    payload = chat_resp.json()

    inventory = ((payload.get("sheet") or {}).get("inventory") or [])
    datapad = next((item for item in inventory if item.get("id") == "DATAPAD"), None)
    assert datapad is not None
    assert datapad.get("item_type") == "READABLE"
    assert datapad.get("text_log_content") == "ACHTUNG: Zugangscode 7391. Frequenz 733.3 kHz aktiv."
    assert datapad.get("text_log_format") == "DOCUMENT"
    assert isinstance(datapad.get("metadata_json"), dict)
    assert datapad.get("metadata_json", {}).get("text_log_content") == "ACHTUNG: Zugangscode 7391. Frequenz 733.3 kHz aktiv."


async def test_export_adv_reimport_keeps_item_stats(client: AsyncClient):
    """Stats on objects should survive an ADV export and re-import cycle."""
    source_payload = {
        "format": "taleweaver.adz",
        "version": "1.0",
        "type": "ADVENTURE_BLUEPRINT",
        "adventure": {
            "title": "ADV Stat Roundtrip Source",
            "context": "Roundtrip stat test",
            "strict_rules": True,
        },
        "protagonist": {
            "name": "Roundtrip Hero",
            "role": "Tester",
            "description": "Checks export/import stat consistency",
            "inventory": [],
            "equipment": {},
            "stats": {},
        },
        "scenes": [
            {"id": "ROOM_A", "name": "Room A", "description": "First room"},
        ],
        "exits": [],
        "npcs": [],
        "objects": [
            {
                "id": "OBJ_ROUNDTRIP",
                "name": "Golden Charm",
                "description": "A charm with social aura.",
                "start_scene_id": "ROOM_A",
                "item_type": "WEARABLE",
                "wearable_slots": ["Neck"],
                "stat_modifier_charisma": 4,
            }
        ],
    }

    source_bytes = json.dumps(source_payload).encode("utf-8")
    source_import = await client.post(
        "/api/adventures/import/adv",
        files={"file": ("roundtrip_source.adv", source_bytes, "application/json")},
    )
    assert source_import.status_code == 200, source_import.text

    templates_resp = await client.get("/api/adventures/templates")
    assert templates_resp.status_code == 200, templates_resp.text
    source_template = next(
        (row for row in templates_resp.json() if row.get("title") == "ADV Stat Roundtrip Source"),
        None,
    )
    assert source_template is not None

    export_resp = await client.get(f"/api/adventures/{source_template['template_id']}/export/adv")
    assert export_resp.status_code == 200, export_resp.text
    exported_adv = export_resp.json()
    exported_adv["adventure"]["title"] = "ADV Stat Roundtrip Reimport"

    reimport_bytes = json.dumps(exported_adv).encode("utf-8")
    reimport_resp = await client.post(
        "/api/adventures/import/adv",
        files={"file": ("roundtrip_reimport.adv", reimport_bytes, "application/json")},
    )
    assert reimport_resp.status_code == 200, reimport_resp.text

    templates_resp_2 = await client.get("/api/adventures/templates")
    assert templates_resp_2.status_code == 200, templates_resp_2.text
    imported_template = next(
        (row for row in templates_resp_2.json() if row.get("title") == "ADV Stat Roundtrip Reimport"),
        None,
    )
    assert imported_template is not None

    debug_resp = await client.get(f"/api/adventures/{imported_template['template_id']}/debug")
    assert debug_resp.status_code == 200, debug_resp.text
    debug_data = debug_resp.json()
    obj = next((o for o in debug_data.get("objects", []) if o.get("id") == "OBJ_ROUNDTRIP"), None)
    assert obj is not None
    assert obj.get("stat_modifier_charisma") == 4

    async with TestSessionLocal() as session:
        ent_res = await session.execute(
            select(WorldEntity).where(
                WorldEntity.template_id == imported_template["template_id"],
                WorldEntity.id == "OBJ_ROUNDTRIP",
            )
        )
        entity = ent_res.scalars().first()
        assert entity is not None
        assert entity.stat_modifier_charisma == 4
        assert "stat_modifier_charisma" not in (entity.metadata_json or {})

async def test_list_templates_returns_created_template(client: AsyncClient):
    """Template endpoint returns template-centric records."""
    ids = await _create_adventure(client, "Template Listing Quest")

    resp = await client.get("/api/adventures/templates")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) >= 1
    row = next((entry for entry in data if entry["template_id"] == ids["adventure_id"]), None)
    assert row is not None
    assert row["title"] == "Template Listing Quest"


async def test_start_session_route_creates_additional_session(client: AsyncClient):
    """Starting a session for an existing template creates a new game session."""
    ids = await _create_adventure(client, "Session Multi Quest")

    resp = await client.post(f"/api/adventures/{ids['adventure_id']}/sessions/start")
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["game_id"] != ids["game_id"]
    assert data["template_id"] == ids["adventure_id"]
    started_game_id = data["game_id"]

    list_resp = await client.get("/api/adventures/sessions")
    assert list_resp.status_code == 200
    session_rows = [s for s in list_resp.json() if s["adventure_id"] == ids["adventure_id"]]
    assert any(s["game_id"] == started_game_id for s in session_rows)
    session_ids = [s["game_id"] for s in session_rows]
    assert len(session_ids) == len(set(session_ids))


async def test_start_session_persists_manifest_snapshot_copy(client: AsyncClient):
    """Starting a session stores a manifest snapshot copy in SessionState.entity_states."""
    ids = await _create_adventure(client, "Manifest Snapshot Quest")

    start_resp = await client.post(f"/api/adventures/{ids['adventure_id']}/sessions/start")
    assert start_resp.status_code == 201, start_resp.text
    game_id = start_resp.json()["game_id"]

    async with TestSessionLocal() as session:
        state_res = await session.execute(select(SessionState).where(SessionState.session_id == game_id))
        state = state_res.scalars().first()
        assert state is not None
        assert isinstance(state.entity_states, dict)

        snapshot = state.entity_states.get("__manifest_snapshot__")
        assert isinstance(snapshot, dict)

        adventure_snapshot = snapshot.get("adventure")
        assert isinstance(adventure_snapshot, dict)
        assert adventure_snapshot.get("id") == ids["adventure_id"]
        assert adventure_snapshot.get("title") == "Manifest Snapshot Quest"

        original_manifest_snapshot = snapshot.get("original_manifest")
        assert isinstance(original_manifest_snapshot, dict)


async def test_list_sessions_has_unique_game_ids(client: AsyncClient):
    """Session list should never contain duplicate entries for the same game_id."""
    ids = await _create_adventure(client, "Unique Session IDs Quest")

    start_resp = await client.post(f"/api/adventures/{ids['adventure_id']}/sessions/start")
    assert start_resp.status_code == 201, start_resp.text

    list_resp = await client.get("/api/adventures/sessions")
    assert list_resp.status_code == 200, list_resp.text

    game_ids = [row.get("game_id") for row in list_resp.json() if row.get("game_id")]
    assert len(game_ids) == len(set(game_ids))


async def test_get_chat_history_uses_session_scene_without_result_reuse_error(client: AsyncClient):
    """Chat history should not fail when scene image is loaded from a session-scoped world scene."""
    ids = await _create_adventure(client, "Session Scene Query Quest")

    start_resp = await client.post(f"/api/adventures/{ids['adventure_id']}/sessions/start")
    assert start_resp.status_code == 201, start_resp.text
    game_id = start_resp.json()["game_id"]

    async with TestSessionLocal() as session:
        state_res = await session.execute(select(SessionState).where(SessionState.session_id == game_id))
        state = state_res.scalars().first()
        assert state is not None

        # Force fallback to DB scene lookup path (instead of asset snapshot key).
        entity_states = dict(state.entity_states or {})
        asset_snapshot = dict(entity_states.get("__asset_snapshot__") or {})
        asset_snapshot.pop(state.current_scene_id, None)
        entity_states["__asset_snapshot__"] = asset_snapshot
        state.entity_states = entity_states
        await session.commit()

    chat_resp = await client.get(f"/api/adventures/{game_id}/chat")
    assert chat_resp.status_code == 200, chat_resp.text


async def test_delete_single_session_keeps_template(client: AsyncClient):
    """Deleting a session should not delete the corresponding adventure template."""
    ids = await _create_adventure(client, "Delete Session Quest")

    del_resp = await client.delete(f"/api/adventures/sessions/{ids['game_id']}")
    assert del_resp.status_code == 200, del_resp.text

    list_resp = await client.get("/api/adventures/sessions")
    assert list_resp.status_code == 200
    sessions = list_resp.json()
    assert all(entry["game_id"] != ids["game_id"] for entry in sessions)

    template_resp = await client.get(f"/api/adventures/{ids['adventure_id']}")
    assert template_resp.status_code == 200


async def test_delete_session_with_chat_messages_succeeds(client: AsyncClient):
    """Deleting a session with stored chat rows should not fail with FK/500 errors."""
    ids = await _create_adventure(client, "Delete Session With Chat")

    async with TestSessionLocal() as session:
        session.add(ChatMessage(session_id=ids["game_id"], role="user", content="hello there"))
        session.add(ChatMessage(session_id=ids["game_id"], role="assistant", content="general kenobi"))
        await session.commit()

    del_resp = await client.delete(f"/api/adventures/sessions/{ids['game_id']}")
    assert del_resp.status_code == 200, del_resp.text


async def test_delete_session_removes_session_folder(client: AsyncClient, monkeypatch, tmp_path):
    """Deleting a session should also remove its session-bound folder from DATA_DIR."""
    data_dir = tmp_path / "data"
    monkeypatch.setattr(settings, "DATA_DIR", str(data_dir))

    ids = await _create_adventure(client, "Delete Session Folder Quest")
    game_id = ids["game_id"]

    session_dir = data_dir / "adventures" / "sessions" / game_id
    os.makedirs(session_dir, exist_ok=True)
    (session_dir / "temp_asset.txt").write_bytes(b"dummy")
    assert session_dir.exists()

    del_resp = await client.delete(f"/api/adventures/sessions/{game_id}")
    assert del_resp.status_code == 200, del_resp.text
    assert not session_dir.exists()


async def test_started_session_persists_asset_snapshot(client: AsyncClient):
    """Newly started sessions store a template asset snapshot for isolation."""
    ids = await _create_adventure(client, "Snapshot Quest")

    start_resp = await client.post(f"/api/adventures/{ids['adventure_id']}/sessions/start")
    assert start_resp.status_code == 201, start_resp.text
    game_id = start_resp.json()["game_id"]

    async with TestSessionLocal() as session:
        state_res = await session.execute(select(GameState).where(GameState.session_id == game_id))
        state = state_res.scalars().first()
        assert state is not None
        assert isinstance(state.entity_states, dict)
        assert "__asset_snapshot__" in state.entity_states


async def test_started_session_copies_visuals_into_session_folder(client: AsyncClient, monkeypatch, tmp_path):
    """Starting a session copies template visuals into session-scoped storage and rewires URLs."""
    data_dir = tmp_path / "data"
    monkeypatch.setattr(settings, "DATA_DIR", str(data_dir))

    ids = await _create_adventure(client, "Session Visual Isolation Quest")
    adv_id = ids["adventure_id"]

    library_dir = data_dir / "adventures" / "library" / adv_id
    os.makedirs(library_dir / "scenes", exist_ok=True)
    os.makedirs(library_dir / "entities", exist_ok=True)

    cover_rel = f"adventures/library/{adv_id}/cover.png"
    hero_rel = f"adventures/library/{adv_id}/hero.png"
    scene_rel = f"adventures/library/{adv_id}/scenes/start.png"
    entity_rel = f"adventures/library/{adv_id}/entities/npc.png"

    (data_dir / cover_rel).write_bytes(b"cover")
    (data_dir / hero_rel).write_bytes(b"hero")
    (data_dir / scene_rel).write_bytes(b"scene")
    (data_dir / entity_rel).write_bytes(b"entity")

    async with TestSessionLocal() as session:
        adventure = await session.get(Adventure, adv_id)
        assert adventure is not None
        adventure.image_url = f"/data/{cover_rel}"

        avatar = await session.get(Avatar, ids["avatar_id"])
        assert avatar is not None
        avatar.profile_image = f"/data/{hero_rel}"

        scene_res = await session.execute(
            select(WorldScene).where(
                WorldScene.template_id == adv_id,
                WorldScene.session_id.is_(None),
            )
        )
        template_scene = scene_res.scalars().first()
        assert template_scene is not None
        template_scene.image_url = f"/data/{scene_rel}"

        session.add(
            WorldEntity(
                id="VISUAL_COPY_NPC",
                template_id=adv_id,
                session_id=None,
                entity_type="NPC",
                name="Visual Copy NPC",
                description="Entity image copy regression test",
                current_scene_id=template_scene.id,
                image_url=f"/data/{entity_rel}",
            )
        )
        await session.commit()

    start_resp = await client.post(f"/api/adventures/{adv_id}/sessions/start")
    assert start_resp.status_code == 201, start_resp.text
    game_id = start_resp.json()["game_id"]

    def _url_to_file_path(url: str) -> str:
        rel = url.replace("/data/", "", 1).lstrip("/")
        return os.path.join(str(data_dir), rel)

    async with TestSessionLocal() as session:
        session_row = await session.get(GameSession, game_id)
        assert session_row is not None
        assert session_row.adventure_image_url.startswith(f"/data/adventures/sessions/{game_id}/visuals/")
        assert os.path.isfile(_url_to_file_path(session_row.adventure_image_url))

        state_res = await session.execute(select(SessionState).where(SessionState.session_id == game_id))
        state = state_res.scalars().first()
        assert state is not None
        snapshot = dict((state.entity_states or {}).get("__asset_snapshot__") or {})
        assert snapshot.get("cover", "").startswith(f"/data/adventures/sessions/{game_id}/visuals/")
        assert snapshot.get("protagonist", "").startswith(f"/data/adventures/sessions/{game_id}/visuals/")
        assert snapshot.get("entity_images", {}).get("VISUAL_COPY_NPC", "").startswith(
            f"/data/adventures/sessions/{game_id}/visuals/"
        )

        avatar_res = await session.execute(select(Avatar).where(Avatar.id == session_row.avatar_id))
        session_avatar = avatar_res.scalars().first()
        assert session_avatar is not None
        assert session_avatar.profile_image.startswith(f"/data/adventures/sessions/{game_id}/visuals/")
        assert os.path.isfile(_url_to_file_path(session_avatar.profile_image))

        scene_res = await session.execute(
            select(WorldScene).where(
                WorldScene.session_id == game_id,
                WorldScene.id == "START",
            )
        )
        session_scene = scene_res.scalars().first()
        assert session_scene is not None
        assert session_scene.image_url.startswith(f"/data/adventures/sessions/{game_id}/visuals/")
        assert os.path.isfile(_url_to_file_path(session_scene.image_url))

        entity_res = await session.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == game_id,
                WorldEntity.id == "VISUAL_COPY_NPC",
            )
        )
        session_entity = entity_res.scalars().first()
        assert session_entity is not None
        assert session_entity.image_url.startswith(f"/data/adventures/sessions/{game_id}/visuals/")
        assert os.path.isfile(_url_to_file_path(session_entity.image_url))


async def test_copied_session_copies_visuals_into_new_session_folder(client: AsyncClient, monkeypatch, tmp_path):
    """Copying a session must re-copy visuals into the new target session folder."""
    data_dir = tmp_path / "data"
    monkeypatch.setattr(settings, "DATA_DIR", str(data_dir))

    ids = await _create_adventure(client, "Copied Session Visual Isolation Quest")
    adv_id = ids["adventure_id"]

    library_dir = data_dir / "adventures" / "library" / adv_id
    os.makedirs(library_dir / "scenes", exist_ok=True)
    os.makedirs(library_dir / "entities", exist_ok=True)

    cover_rel = f"adventures/library/{adv_id}/cover.png"
    hero_rel = f"adventures/library/{adv_id}/hero.png"
    scene_rel = f"adventures/library/{adv_id}/scenes/start.png"
    entity_rel = f"adventures/library/{adv_id}/entities/npc.png"

    (data_dir / cover_rel).write_bytes(b"cover")
    (data_dir / hero_rel).write_bytes(b"hero")
    (data_dir / scene_rel).write_bytes(b"scene")
    (data_dir / entity_rel).write_bytes(b"entity")

    async with TestSessionLocal() as session:
        adventure = await session.get(Adventure, adv_id)
        assert adventure is not None
        adventure.image_url = f"/data/{cover_rel}"

        avatar = await session.get(Avatar, ids["avatar_id"])
        assert avatar is not None
        avatar.profile_image = f"/data/{hero_rel}"

        scene_res = await session.execute(
            select(WorldScene).where(
                WorldScene.template_id == adv_id,
                WorldScene.session_id.is_(None),
            )
        )
        template_scene = scene_res.scalars().first()
        assert template_scene is not None
        template_scene.image_url = f"/data/{scene_rel}"

        session.add(
            WorldEntity(
                id="VISUAL_COPY_NPC_FOR_DUP",
                template_id=adv_id,
                session_id=None,
                entity_type="NPC",
                name="Visual Copy NPC",
                description="Entity image copy regression test",
                current_scene_id=template_scene.id,
                image_url=f"/data/{entity_rel}",
            )
        )
        await session.commit()

    start_resp = await client.post(f"/api/adventures/{adv_id}/sessions/start")
    assert start_resp.status_code == 201, start_resp.text
    source_game_id = start_resp.json()["game_id"]

    copy_resp = await client.post(f"/api/adventures/sessions/{source_game_id}/copy")
    assert copy_resp.status_code == 201, copy_resp.text
    copied_game_id = copy_resp.json()["game_id"]

    def _url_to_file_path(url: str) -> str:
        rel = url.replace("/data/", "", 1).lstrip("/")
        return os.path.join(str(data_dir), rel)

    async with TestSessionLocal() as session:
        source_session = await session.get(GameSession, source_game_id)
        copied_session = await session.get(GameSession, copied_game_id)
        assert source_session is not None
        assert copied_session is not None

        assert source_session.adventure_image_url.startswith(f"/data/adventures/sessions/{source_game_id}/visuals/")
        assert copied_session.adventure_image_url.startswith(f"/data/adventures/sessions/{copied_game_id}/visuals/")
        assert copied_session.adventure_image_url != source_session.adventure_image_url
        assert os.path.isfile(_url_to_file_path(copied_session.adventure_image_url))

        avatar_res = await session.execute(select(Avatar).where(Avatar.id == copied_session.avatar_id))
        copied_avatar = avatar_res.scalars().first()
        assert copied_avatar is not None
        assert copied_avatar.profile_image.startswith(f"/data/adventures/sessions/{copied_game_id}/visuals/")
        assert os.path.isfile(_url_to_file_path(copied_avatar.profile_image))

        copied_scene_res = await session.execute(
            select(WorldScene).where(
                WorldScene.session_id == copied_game_id,
                WorldScene.id == "START",
            )
        )
        copied_scene = copied_scene_res.scalars().first()
        assert copied_scene is not None
        assert copied_scene.image_url.startswith(f"/data/adventures/sessions/{copied_game_id}/visuals/")
        assert os.path.isfile(_url_to_file_path(copied_scene.image_url))

        copied_entity_res = await session.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == copied_game_id,
                WorldEntity.id == "VISUAL_COPY_NPC_FOR_DUP",
            )
        )
        copied_entity = copied_entity_res.scalars().first()
        assert copied_entity is not None
        assert copied_entity.image_url.startswith(f"/data/adventures/sessions/{copied_game_id}/visuals/")
        assert os.path.isfile(_url_to_file_path(copied_entity.image_url))


async def test_start_session_ignores_session_bound_template_rows(client: AsyncClient):
    """Starting a session must clone only template baseline world rows (session_id IS NULL)."""
    ids = await _create_adventure(client, "Session Baseline Isolation Quest")
    template_id = ids["adventure_id"]

    first_start = await client.post(f"/api/adventures/{template_id}/sessions/start")
    assert first_start.status_code == 201, first_start.text
    first_game_id = first_start.json()["game_id"]

    async with TestSessionLocal() as db:
        base_scene_count_res = await db.execute(
            select(func.count(WorldScene.pk)).where(
                WorldScene.template_id == template_id,
                WorldScene.session_id.is_(None),
            )
        )
        baseline_scene_count = int(base_scene_count_res.scalar_one())

        base_entity_count_res = await db.execute(
            select(func.count(WorldEntity.pk)).where(
                WorldEntity.template_id == template_id,
                WorldEntity.session_id.is_(None),
            )
        )
        baseline_entity_count = int(base_entity_count_res.scalar_one())

        # Simulate polluted data from imported/legacy session rows carrying template_id.
        db.add(
            WorldScene(
                id="POLLUTED_SCENE",
                template_id=template_id,
                session_id=first_game_id,
                label="Polluted Scene",
                description="Should never be treated as template baseline.",
                image_url=None,
            )
        )
        db.add(
            WorldEntity(
                id="POLLUTED_ITEM",
                template_id=template_id,
                session_id=first_game_id,
                entity_type="OBJECT",
                name="Polluted Item",
                description="Must not be cloned into a new session.",
                current_scene_id="POLLUTED_SCENE",
                spatial_position="on the floor",
                image_url=None,
                item_type="PICKABLE",
                wearable_slots=[],
                is_in_inventory=False,
                is_hidden=False,
                is_portable=True,
                combination_ingredients=[],
                reveals_item_id=None,
                is_final_state=False,
                state_comment=None,
                npc_type=None,
                movement_type=None,
                hp=None,
                max_hp=None,
                mana=None,
                max_mana=None,
                stamina=None,
                max_stamina=None,
                stat_modifier_strength=None,
                stat_modifier_dexterity=None,
                stat_modifier_intelligence=None,
                stat_modifier_wisdom=None,
                stat_modifier_charisma=None,
                stat_modifier_armor_class=None,
                inventory=[],
                metadata_json={},
            )
        )
        await db.commit()

    second_start = await client.post(f"/api/adventures/{template_id}/sessions/start")
    assert second_start.status_code == 201, second_start.text
    second_game_id = second_start.json()["game_id"]

    async with TestSessionLocal() as db:
        session_scene_count_res = await db.execute(
            select(func.count(WorldScene.pk)).where(WorldScene.session_id == second_game_id)
        )
        second_scene_count = int(session_scene_count_res.scalar_one())

        session_entity_count_res = await db.execute(
            select(func.count(WorldEntity.pk)).where(WorldEntity.session_id == second_game_id)
        )
        second_entity_count = int(session_entity_count_res.scalar_one())

        assert second_scene_count == baseline_scene_count
        assert second_entity_count == baseline_entity_count

    list_resp = await client.get("/api/adventures/sessions")
    assert list_resp.status_code == 200, list_resp.text
    game_ids = [row["game_id"] for row in list_resp.json()]
    assert len(game_ids) == len(set(game_ids))


async def test_started_sessions_keep_snapshot_images_after_template_avatar_edit(client: AsyncClient):
    """Started sessions keep their snapshot cover/protagonist images after later template edits."""
    ids = await _create_adventure(client, "Snapshot Image Isolation Quest")

    old_cover = "/data/adventures/test/cover_old.png"
    old_profile = "/data/adventures/test/protagonist_old.png"
    new_cover = "/data/adventures/test/cover_new.png"
    new_profile = "/data/adventures/test/protagonist_new.png"

    async with TestSessionLocal() as session:
        adventure = await session.get(Adventure, ids["adventure_id"])
        avatar = await session.get(Avatar, ids["avatar_id"])
        assert adventure is not None
        assert avatar is not None
        adventure.image_url = old_cover
        avatar.profile_image = old_profile
        await session.commit()

    game_ids: list[str] = []
    for _ in range(3):
        start_resp = await client.post(f"/api/adventures/{ids['adventure_id']}/sessions/start")
        assert start_resp.status_code == 201, start_resp.text
        game_ids.append(start_resp.json()["game_id"])

    async with TestSessionLocal() as session:
        adventure = await session.get(Adventure, ids["adventure_id"])
        avatar = await session.get(Avatar, ids["avatar_id"])
        assert adventure is not None
        assert avatar is not None
        adventure.image_url = new_cover
        avatar.profile_image = new_profile
        await session.commit()

    sessions_resp = await client.get("/api/adventures/sessions")
    assert sessions_resp.status_code == 200, sessions_resp.text
    sessions_data = {entry["game_id"]: entry for entry in sessions_resp.json()}

    for game_id in game_ids:
        assert game_id in sessions_data
        assert sessions_data[game_id]["image_url"] == old_cover

        chat_resp = await client.get(f"/api/adventures/{game_id}/chat")
        assert chat_resp.status_code == 200, chat_resp.text
        chat_data = chat_resp.json()
        assert chat_data["adventure_image"] == old_cover
        assert chat_data["sheet"]["profile_image"] == old_profile

async def test_update_adventure_frontend_payload(client: AsyncClient):
    """Patching with frontend payload should not give 422."""
    ids = await _create_adventure(client, "Test Quest")
    adv_id = ids["adventure_id"]

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





