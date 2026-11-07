"""Scene and main theme music: Lyria provider, editor flow, playback priority, ADZ round trip,
World-Builder fields."""

import base64
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import delete, select

from backend.api.routes.adventures import editor_music, music_snapshot
from backend.core.config import settings
from backend.engine.adventures.adventure_exporter import AdventureExporter
from backend.engine.adventures.adventure_importer import AdventureTemplateImporter
from backend.engine.audio import lyria_music
from backend.engine.audio.music_assets import map_imported_music, save_library_music
from backend.engine.audio.music_prompt_context import LOOP_INSTRUCTION, ensure_loopable
from backend.engine.audio.music_providers import lyria_model_for, render_track
from backend.engine.audio.music_state import apply_music_ops
from backend.engine.blueprint import analyze_blueprint
from backend.engine.scripting.context import GameContext
from backend.engine.world.world_schemas import WorldSceneSchema
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldScene
from tests.conftest import TestSessionLocal

LYRIA_SETTINGS = {
    "provider": "lyria",
    "default_duration": 30,
    "max_duration": 120,
    "lyria_clip_model": "lyria-3-clip-preview",
    "lyria_full_model": "lyria-3.5",
    "lyria_timeout": 60,
    "lyria_wav": False,
}


def _lyria_reply(data: bytes = b"ID3-mp3") -> dict:
    audio = {"type": "audio", "data": base64.b64encode(data).decode("ascii")}
    return {"steps": [{"type": "thought"}, {"type": "model_output", "content": [audio]}]}


# --- Lyria ------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lyria_request_uses_interactions_api_and_clip_model(monkeypatch):
    # Arrange
    seen = {}

    async def handler(request):
        seen["url"] = str(request.url)
        seen["key"] = request.headers["x-goog-api-key"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_lyria_reply())

    factory = httpx.AsyncClient
    monkeypatch.setattr(
        lyria_music.httpx,
        "AsyncClient",
        lambda **kwargs: factory(**kwargs, transport=httpx.MockTransport(handler)),
    )
    track = {"prompt": "dark ambient drone", "negative_prompt": "drums"}

    # Act
    data, extension = await render_track(track, LYRIA_SETTINGS, "secret-key")

    # Assert
    assert seen["url"] == lyria_music.INTERACTIONS_URL and seen["key"] == "secret-key"
    assert seen["body"]["model"] == "lyria-3-clip-preview"
    assert "Avoid: drums." in seen["body"]["input"]
    assert lyria_music.INSTRUMENTAL_NOTE in seen["body"]["input"]
    assert (data, extension) == (b"ID3-mp3", "mp3")


def test_long_tracks_use_the_full_model_and_ask_for_the_length():
    # Act
    model, full = lyria_model_for({"duration": 90}, LYRIA_SETTINGS)
    prompt = lyria_music.lyria_prompt("epic battle", "", 90, full)

    # Assert
    assert (model, full) == ("lyria-3.5", True)
    assert "About 90 seconds long." in prompt


def test_lyria_reply_without_audio_explains_the_safety_filter():
    with pytest.raises(ValueError, match="safety filter"):
        lyria_music.parse_lyria_reply({"steps": [{"type": "model_output", "content": []}]}, False)


# --- prompt suggestion ------------------------------------------------------------------------


def test_suggested_prompts_always_become_loopable():
    # Act
    added = ensure_loopable('"slow harp, 70 bpm."')
    kept = ensure_loopable("calm strings, seamless loop without intro")

    # Assert
    assert added == f"slow harp, 70 bpm. {LOOP_INSTRUCTION}"
    assert kept == "calm strings, seamless loop without intro"
    assert len(ensure_loopable("x" * 2000)) <= 1000
    assert ensure_loopable("x" * 2000).endswith(LOOP_INSTRUCTION)


# --- editor flow ------------------------------------------------------------------------------


async def _seed(owner_id: str, template_id: str = "music-adv") -> None:
    async with TestSessionLocal() as db:
        await db.execute(delete(WorldScene).where(WorldScene.template_id == template_id))
        await db.execute(delete(AdventureTemplate).where(AdventureTemplate.id == template_id))
        db.add(
            AdventureTemplate(
                id=template_id,
                owner_id=owner_id,
                title="Music Test",
                teaser="Bells under the sea.",
                selected_tone={"id": "dark", "name": "Dark", "description": "Grim and slow"},
            )
        )
        db.add(
            WorldScene(
                id="CRYPT", template_id=template_id, label="Crypt", description="A cold crypt."
            )
        )
        await db.commit()


async def _owner_id() -> str:
    async with TestSessionLocal() as db:
        return (await db.execute(select(User.id).limit(1))).scalar_one()


@pytest.mark.asyncio
async def test_editor_suggests_loopable_prompt_from_tone_and_scene(
    auth_client, setup_test_db, monkeypatch
):
    # Arrange
    await _seed(await _owner_id())
    llm = AsyncMock(return_value="Slow cello drones, 60 bpm.")
    monkeypatch.setattr(editor_music.GameMasterLLM, "aexecute_simple_task", llm)

    # Act
    response = await auth_client.post(
        "/api/adventures/music-adv/music/suggest-prompt",
        json={"target_type": "scene", "target_id": "CRYPT"},
    )

    # Assert
    assert response.status_code == 200
    assert response.json()["suggested_prompt"].endswith(LOOP_INSTRUCTION)
    user_prompt = llm.await_args.kwargs["user_prompt"]
    assert "Dark - Grim and slow" in user_prompt and "A cold crypt." in user_prompt


@pytest.mark.asyncio
async def test_editor_generates_scene_music_in_background_and_stores_it(
    auth_client, setup_test_db, monkeypatch, tmp_path
):
    # Arrange
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    await _seed(await _owner_id())
    async with TestSessionLocal() as db:
        from backend.core.global_settings import get_server_settings_for_update

        server = await get_server_settings_for_update(db)
        server.music_settings = {"enabled": True, "provider": "lyria"}
        await db.commit()
    monkeypatch.setattr(editor_music, "session_factory", TestSessionLocal)
    monkeypatch.setattr(editor_music, "music_api_key", lambda _user, _settings: "key")
    monkeypatch.setattr(editor_music, "render_exclusive", AsyncMock(return_value=(b"ID3", "mp3")))
    target = {"target_type": "scene", "target_id": "CRYPT"}

    # Act
    started = await auth_client.post(
        "/api/adventures/music-adv/music/generate", json={**target, "prompt": "cello loop"}
    )
    job_id = started.json()["id"]
    await editor_music.editor_jobs.tasks[job_id]
    status = (await auth_client.get(f"/api/adventures/music-adv/music/jobs/{job_id}")).json()
    async with TestSessionLocal() as db:
        scene = (
            await db.execute(select(WorldScene).where(WorldScene.template_id == "music-adv"))
        ).scalar_one()
    removed = (await auth_client.post("/api/adventures/music-adv/music/remove", json=target)).json()

    # Assert
    assert started.status_code == 200 and status["status"] == "done"
    assert scene.music_prompt == "cello loop"
    assert scene.music_url.startswith("/data/adventures/library/music-adv/music/CRYPT_")
    assert status["url"] == scene.music_url
    assert removed["music_url"] is None and removed["music_prompt"] == "cello loop"
    assert not os.listdir(tmp_path / "adventures/library/music-adv/music")


@pytest.mark.asyncio
async def test_editor_rejects_generation_while_music_is_off(auth_client, setup_test_db):
    await _seed(await _owner_id())
    response = await auth_client.post(
        "/api/adventures/music-adv/music/generate",
        json={"target_type": "theme", "prompt": "harp"},
    )
    assert response.status_code == 400 and "switched off" in response.json()["detail"]


# --- playback priority ------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scene_music_plays_until_a_script_takes_over_or_stops(
    auth_client, setup_test_db, monkeypatch, tmp_path
):
    # Arrange
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    await _seed(await _owner_id())
    scene_url = save_library_music("music-adv", "CRYPT", "aa", b"ID3", "mp3")
    theme_url = save_library_music("music-adv", "theme", "bb", b"ID3", "mp3")
    async with TestSessionLocal() as db:
        scene = (await db.execute(select(WorldScene))).scalars().first()
        scene.music_url = scene_url
        adventure = await db.get(AdventureTemplate, "music-adv")
        adventure.music_url = theme_url
        await db.commit()
    server = SimpleNamespace(music_settings={"enabled": False})
    monkeypatch.setattr(music_snapshot, "read_server_settings", AsyncMock(return_value=server))
    states: dict = {}
    state = SimpleNamespace(
        session_id="sess", template_id="music-adv", current_scene_id="CRYPT", entity_states=states
    )
    ctx = GameContext()
    ctx.music.stop()

    async with TestSessionLocal() as db:
        adventure = await db.get(AdventureTemplate, "music-adv")
        # Act
        in_scene = await music_snapshot.build_music_snapshot(db, state, adventure)
        state.current_scene_id = "HALL"
        theme = await music_snapshot.build_music_snapshot(db, state, adventure)
        apply_music_ops(states, ctx.changeset.music_ops)
        silenced = await music_snapshot.build_music_snapshot(db, state, adventure)
        released = GameContext()
        released.music.release()
        apply_music_ops(states, released.changeset.music_ops)
        back = await music_snapshot.build_music_snapshot(db, state, adventure)
        adventure.music_enabled = False
        author_off = await music_snapshot.build_music_snapshot(db, state, adventure)

    # Assert
    assert in_scene["now"]["source"] == "scene" and in_scene["now"]["url"] == scene_url
    assert theme["now"]["source"] == "theme" and theme["now"]["url"] == theme_url
    assert silenced["now"] is None
    assert back["now"]["source"] == "theme"
    assert author_off is None


# --- ADZ round trip & World-Builder -----------------------------------------------------------


@pytest.mark.asyncio
async def test_scene_and_theme_music_survive_adz_export_and_import(
    auth_client, setup_test_db, monkeypatch, tmp_path
):
    # Arrange
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    owner = await _owner_id()
    await _seed(owner, "music-export")
    async with TestSessionLocal() as db:
        scene = (
            await db.execute(select(WorldScene).where(WorldScene.template_id == "music-export"))
        ).scalar_one()
        scene.music_prompt = "cello loop"
        scene.music_url = save_library_music("music-export", "CRYPT", "cc", b"SCENE", "mp3")
        adventure = await db.get(AdventureTemplate, "music-export")
        adventure.music_prompt = "harp theme"
        adventure.music_url = save_library_music("music-export", "theme", "dd", b"THEME", "mp3")
        await db.commit()

        # Act
        adz = await AdventureExporter.export_adz(db, "music-export")
        await db.execute(delete(WorldScene).where(WorldScene.template_id == "music-export"))
        await db.execute(delete(AdventureTemplate).where(AdventureTemplate.id == "music-export"))
        await db.commit()
        assert await AdventureTemplateImporter.import_adz(db, adz, owner_id=owner)
        imported = (
            await db.execute(
                select(AdventureTemplate).where(AdventureTemplate.title == "Music Test")
            )
        ).scalar_one()
        new_scene = (
            await db.execute(select(WorldScene).where(WorldScene.template_id == imported.id))
        ).scalar_one()

    # Assert
    assert imported.music_prompt == "harp theme" and new_scene.music_prompt == "cello loop"
    for url, content in ((imported.music_url, b"THEME"), (new_scene.music_url, b"SCENE")):
        assert url.startswith(f"/data/adventures/library/{imported.id}/")
        with open(tmp_path / url.removeprefix("/data/"), "rb") as handle:
            assert handle.read() == content


def test_import_mapping_drops_music_urls_that_are_not_local():
    manifest = {
        "adventure": {"music_url": "assets/theme.mp3"},
        "scenes": [{"music_url": "https://evil.example/x.mp3"}, {"music_url": "assets/a.mp3"}],
    }
    map_imported_music(manifest, {"assets/theme.mp3": "/data/adventures/library/n/theme.mp3"})
    assert manifest["adventure"]["music_url"] == "/data/adventures/library/n/theme.mp3"
    assert [s["music_url"] for s in manifest["scenes"]] == [None, None]


def test_world_builder_fields_reach_the_schema_and_blueprint():
    # Act
    scene = WorldSceneSchema(id="CRYPT", name="Crypt", description="Cold.", music_prompt="drone")
    blueprint, _ = analyze_blueprint(
        "[World]\nmusic: harp theme\n[Scene: CRYPT] Crypt\nCold.\nmusic: cello drone\n"
    )

    # Assert
    assert scene.music_prompt == "drone"
    assert blueprint.first("world").fields["music_prompt"].value == "harp theme"
    assert blueprint.first("scene").fields["music_prompt"].value == "cello drone"


def test_music_urls_are_bound_to_the_owning_adventure(monkeypatch, tmp_path):
    # Arrange
    from backend.engine.audio.music_assets import delete_library_music, local_music_url

    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    victim = save_library_music("victim-adv", "CRYPT", "ee", b"VICTIM", "mp3")
    own = save_library_music("own-adv", "CRYPT", "ff", b"OWN", "mp3")
    manifest = {"adventure": {"music_url": victim}, "scenes": [{"music_url": victim}]}

    # Act
    map_imported_music(manifest, {})
    delete_library_music(victim, "own-adv")

    # Assert
    assert manifest["adventure"]["music_url"] is None
    assert manifest["scenes"][0]["music_url"] is None
    assert local_music_url(victim, "own-adv") is None
    assert local_music_url(own, "own-adv") == own
    assert (tmp_path / victim.removeprefix("/data/")).exists()
    delete_library_music(own, "own-adv")
    assert not (tmp_path / own.removeprefix("/data/")).exists()
