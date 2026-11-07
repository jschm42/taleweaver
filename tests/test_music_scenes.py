"""Music library: Lyria provider, editor tab (generate, upload, scene tracks), playback across
scenes, ADZ round trip, World-Builder fields."""

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
from backend.engine.world.world_schemas import WorldManifesto, WorldSceneSchema
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


# --- editor: music library --------------------------------------------------------------------


async def _seed(owner_id: str, template_id: str = "music-adv", tracks=None) -> None:
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
                music_tracks=tracks,
                original_manifest={"scenes": [{"id": "CRYPT"}, {"id": "HALL"}]},
            )
        )
        for scene_id, label in (("CRYPT", "Crypt"), ("HALL", "Hall")):
            db.add(
                WorldScene(
                    id=scene_id,
                    template_id=template_id,
                    label=label,
                    description=f"A cold {label}.",
                )
            )
        await db.commit()


async def _owner_id() -> str:
    async with TestSessionLocal() as db:
        return (await db.execute(select(User.id).limit(1))).scalar_one()


async def _enable_music(provider: str = "lyria") -> None:
    from backend.core.global_settings import get_server_settings_for_update

    async with TestSessionLocal() as db:
        server = await get_server_settings_for_update(db)
        server.music_settings = {"enabled": True, "provider": provider}
        await db.commit()


@pytest.mark.asyncio
async def test_prompt_suggestion_uses_tone_and_reference_scene(
    auth_client, setup_test_db, monkeypatch
):
    # Arrange
    await _seed(await _owner_id())
    llm = AsyncMock(return_value="Slow cello drones, 60 bpm.")
    monkeypatch.setattr(editor_music.GameMasterLLM, "aexecute_simple_task", llm)

    # Act
    response = await auth_client.post(
        "/api/adventures/music-adv/music/suggest-prompt", json={"reference_scene_id": "CRYPT"}
    )

    # Assert
    assert response.status_code == 200
    assert response.json()["suggested_prompt"].endswith(LOOP_INSTRUCTION)
    user_prompt = llm.await_args.kwargs["user_prompt"]
    assert "Dark - Grim and slow" in user_prompt and "A cold Crypt." in user_prompt


@pytest.mark.asyncio
async def test_generated_track_renders_in_background_and_scenes_pick_it(
    auth_client, setup_test_db, monkeypatch, tmp_path
):
    # Arrange
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    await _seed(await _owner_id())
    await _enable_music()
    monkeypatch.setattr(editor_music, "session_factory", TestSessionLocal)
    monkeypatch.setattr(editor_music, "music_api_key", lambda _user, _settings: "key")
    monkeypatch.setattr(editor_music, "render_exclusive", AsyncMock(return_value=(b"ID3", "mp3")))
    base = "/api/adventures/music-adv/music"

    # Act
    created = (
        await auth_client.post(
            f"{base}/tracks",
            json={"name": "Crypt Theme", "prompt": "cello loop", "reference_scene_id": "CRYPT"},
        )
    ).json()
    await editor_music.editor_jobs.tasks[created["job"]["id"]]
    track_id = created["track"]["id"]
    assigned = await auth_client.post(f"{base}/scenes/CRYPT/track", json={"track_id": track_id})
    unknown = await auth_client.post(f"{base}/scenes/HALL/track", json={"track_id": "nope"})
    library = (await auth_client.get(base)).json()

    # Assert
    track = library["tracks"][0]
    assert track["name"] == "Crypt Theme" and track["reference_scene_id"] == "CRYPT"
    assert track["url"].startswith(f"/data/adventures/library/music-adv/music/{track_id}_")
    assert assigned.status_code == 200 and unknown.status_code == 404
    assert library["scene_usage"] == {track_id: ["CRYPT"]}
    assert library["jobs"][track_id]["status"] == "done"
    async with TestSessionLocal() as db:
        adventure = await db.get(AdventureTemplate, "music-adv")
        assert adventure.original_manifest["music_tracks"][0]["id"] == track_id
        assert adventure.original_manifest["scenes"][0]["music_track_id"] == track_id


@pytest.mark.asyncio
async def test_upload_rename_and_delete_track(auth_client, setup_test_db, monkeypatch, tmp_path):
    # Arrange
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    await _seed(await _owner_id())
    base = "/api/adventures/music-adv/music"
    wav = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 32

    # Act
    uploaded = await auth_client.post(
        f"{base}/tracks/upload", files={"file": ("../../harbor.wav", wav, "audio/wav")}
    )
    fake = await auth_client.post(
        f"{base}/tracks/upload", files={"file": ("evil.mp3", b"<html>", "audio/mpeg")}
    )
    track = uploaded.json()["track"]
    await auth_client.post(f"{base}/scenes/HALL/track", json={"track_id": track["id"]})
    renamed = await auth_client.patch(f"{base}/tracks/{track['id']}", json={"name": "Harbor"})
    deleted = (await auth_client.delete(f"{base}/tracks/{track['id']}")).json()

    # Assert
    assert uploaded.status_code == 200 and track["source"] == "uploaded"
    assert track["name"] == "harbor" and track["url"].endswith(".wav")
    assert fake.status_code == 400
    assert renamed.json()["track"]["name"] == "Harbor"
    assert deleted["tracks"] == [] and deleted["scene_usage"] == {}
    assert not os.listdir(tmp_path / "adventures/library/music-adv/music")
    async with TestSessionLocal() as db:
        hall = (await db.execute(select(WorldScene).where(WorldScene.id == "HALL"))).scalar_one()
        assert hall.music_track_id is None


@pytest.mark.asyncio
async def test_generation_is_rejected_while_music_is_off(auth_client, setup_test_db):
    await _seed(await _owner_id())
    response = await auth_client.post(
        "/api/adventures/music-adv/music/tracks", json={"name": "x", "prompt": "harp"}
    )
    assert response.status_code == 400 and "switched off" in response.json()["detail"]


# --- playback ---------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scene_tracks_keep_playing_switch_or_fade_out(
    auth_client, setup_test_db, monkeypatch, tmp_path
):
    # Arrange
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    calm = save_library_music("music-adv", "calm", "aa", b"ID3", "mp3")
    storm = save_library_music("music-adv", "storm", "bb", b"ID3", "mp3")
    tracks = [
        {"id": "calm", "name": "Calm", "url": calm},
        {"id": "storm", "name": "Storm", "url": storm},
    ]
    await _seed(await _owner_id(), tracks=tracks)
    async with TestSessionLocal() as db:
        for scene in (await db.execute(select(WorldScene))).scalars():
            scene.music_track_id = "calm"
        db.add(WorldScene(id="CAVE", template_id="music-adv", label="Cave", description="."))
        db.add(
            WorldScene(
                id="PEAK",
                template_id="music-adv",
                label="Peak",
                description=".",
                music_track_id="storm",
            )
        )
        await db.commit()
    server = SimpleNamespace(music_settings={"enabled": False})
    monkeypatch.setattr(music_snapshot, "read_server_settings", AsyncMock(return_value=server))
    state = SimpleNamespace(
        session_id="sess", template_id="music-adv", current_scene_id="CRYPT", entity_states={}
    )

    async def snapshot_in(scene_id: str) -> dict:
        state.current_scene_id = scene_id
        async with TestSessionLocal() as db:
            return await music_snapshot.build_music_snapshot(db, state)

    # Act
    crypt, hall, peak, cave = [await snapshot_in(s) for s in ("CRYPT", "HALL", "PEAK", "CAVE")]
    ctx = GameContext()
    ctx.music.stop()
    apply_music_ops(state.entity_states, ctx.changeset.music_ops)
    silenced = await snapshot_in("CRYPT")

    # Assert
    assert crypt["now"]["url"] == hall["now"]["url"] == calm  # same track: keeps playing
    assert crypt["now"]["id"] == hall["now"]["id"] == "track:calm"
    assert peak["now"]["url"] == storm  # another track: cross-fade
    assert cave is not None and cave["now"] is None  # no track: fade out
    assert silenced["now"] is None


@pytest.mark.asyncio
async def test_no_music_payload_without_library_or_when_author_switched_it_off(
    auth_client, setup_test_db, monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    url = save_library_music("music-adv", "calm", "aa", b"ID3", "mp3")
    await _seed(await _owner_id(), tracks=[{"id": "calm", "name": "Calm", "url": url}])
    async with TestSessionLocal() as db:
        adventure = await db.get(AdventureTemplate, "music-adv")
        adventure.music_enabled = False
        await db.commit()
    state = SimpleNamespace(
        session_id="s", template_id="music-adv", current_scene_id="CRYPT", entity_states={}
    )
    async with TestSessionLocal() as db:
        assert await music_snapshot.build_music_snapshot(db, state) is None


# --- ADZ round trip, import safety, World-Builder ---------------------------------------------


@pytest.mark.asyncio
async def test_music_library_survives_adz_export_and_import(
    auth_client, setup_test_db, monkeypatch, tmp_path
):
    # Arrange
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    owner = await _owner_id()
    url = save_library_music("music-export", "calm", "cc", b"CALM", "mp3")
    tracks = [
        {"id": "calm", "name": "Calm", "prompt": "harp", "url": url, "source": "generated"},
        {"id": "PLANNED", "name": "Planned", "prompt": "drums"},
    ]
    await _seed(owner, "music-export", tracks=tracks)
    async with TestSessionLocal() as db:
        scene = (
            await db.execute(
                select(WorldScene).where(
                    WorldScene.template_id == "music-export", WorldScene.id == "CRYPT"
                )
            )
        ).scalar_one()
        scene.music_track_id = "calm"
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
        crypt = (
            await db.execute(
                select(WorldScene).where(
                    WorldScene.template_id == imported.id, WorldScene.id == "CRYPT"
                )
            )
        ).scalar_one()

    # Assert
    by_id = {t["id"]: t for t in imported.music_tracks}
    assert crypt.music_track_id == "calm"
    assert by_id["PLANNED"]["url"] is None and by_id["PLANNED"]["source"] == "planned"
    assert by_id["calm"]["url"].startswith(f"/data/adventures/library/{imported.id}/")
    with open(tmp_path / by_id["calm"]["url"].removeprefix("/data/"), "rb") as handle:
        assert handle.read() == b"CALM"


def test_music_urls_are_bound_to_the_owning_adventure(monkeypatch, tmp_path):
    # Arrange
    from backend.engine.audio.music_assets import delete_library_music, local_music_url
    from backend.engine.audio.music_library import normalize_tracks

    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    victim = save_library_music("victim-adv", "CRYPT", "ee", b"VICTIM", "mp3")
    own = save_library_music("own-adv", "CRYPT", "ff", b"OWN", "mp3")
    manifest = {"adventure": {"music_tracks": [{"id": "a", "url": victim}]}}

    # Act
    map_imported_music(manifest, {})
    delete_library_music(victim, "own-adv")
    foreign = normalize_tracks([{"id": "x", "url": victim}], "own-adv")

    # Assert
    assert manifest["adventure"]["music_tracks"][0]["url"] is None
    assert foreign[0]["url"] is None
    assert local_music_url(victim, "own-adv") is None
    assert local_music_url(own, "own-adv") == own
    assert (tmp_path / victim.removeprefix("/data/")).exists()
    delete_library_music(own, "own-adv")
    assert not (tmp_path / own.removeprefix("/data/")).exists()


def test_world_builder_plans_tracks_and_scenes_reference_them():
    # Act
    manifest = WorldManifesto.model_json_schema()
    scene = WorldSceneSchema(id="CRYPT", name="Crypt", description="Cold.", music_track_id="DRONE")
    blueprint, missing = analyze_blueprint(
        "[Music: DRONE] Crypt Drone\nprompt: dark cello drone, 60 bpm\n"
        "[Scene: CRYPT] Crypt\nCold.\nmusic: DRONE\n"
    )

    # Assert
    assert "music_tracks" in manifest["properties"]
    assert scene.music_track_id == "DRONE"
    assert not [i for i in blueprint.issues if i.severity == "error"] and missing == []
    assert blueprint.first("music").fields["prompt"].value == "dark cello drone, 60 bpm"
    assert blueprint.first("scene").fields["music_track_id"].value == "DRONE"


def test_blueprint_merge_recreates_dropped_tracks():
    from backend.engine.blueprint.merge import apply_blueprint

    blueprint, _ = analyze_blueprint("[Music: DRONE] Crypt Drone\nprompt: cello drone\n")
    manifest: dict = {"scenes": []}
    apply_blueprint(manifest, blueprint)
    assert manifest["music_tracks"][0]["id"] == "DRONE"
    assert manifest["music_tracks"][0]["prompt"] == "cello drone"


@pytest.mark.asyncio
async def test_manifest_apply_merges_tracks_and_keeps_rendered_audio(
    auth_client, setup_test_db, monkeypatch, tmp_path
):
    from backend.engine.manifest_apply.adventure_meta import _apply_music_tracks

    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    url = save_library_music("music-adv", "calm", "aa", b"ID3", "mp3")
    adventure = SimpleNamespace(music_tracks=[{"id": "CALM", "name": "Calm", "url": url}])
    ctx = SimpleNamespace(
        template_id="music-adv",
        manifest={
            "music_tracks": [
                {"id": "CALM", "name": "Calm v2", "prompt": "harp"},
                {"id": "NEW", "name": "New", "prompt": "drums"},
            ]
        },
    )
    _apply_music_tracks(ctx, adventure)
    by_id = {t["id"]: t for t in adventure.music_tracks}
    assert by_id["CALM"]["url"] == url and by_id["CALM"]["name"] == "Calm v2"
    assert by_id["NEW"]["source"] == "planned"
