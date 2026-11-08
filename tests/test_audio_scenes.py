"""Audio library: Lyria provider, editor tab (generate, upload, scene tracks), playback across
scenes, ADZ round trip, World-Builder fields."""

import base64
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import delete, select

from backend.api.routes.adventures import audio_snapshot, editor_audio
from backend.core.config import settings
from backend.engine.adventures.adventure_exporter import AdventureExporter
from backend.engine.adventures.adventure_importer import AdventureTemplateImporter
from backend.engine.audio import lyria_audio
from backend.engine.audio.audio_assets import map_imported_audio, save_library_audio
from backend.engine.audio.audio_prompt_context import LOOP_INSTRUCTION, ensure_loopable
from backend.engine.audio.audio_providers import lyria_model_for, render_track
from backend.engine.audio.audio_state import apply_audio_ops
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
        lyria_audio.httpx,
        "AsyncClient",
        lambda **kwargs: factory(**kwargs, transport=httpx.MockTransport(handler)),
    )
    track = {"prompt": "dark ambient drone", "negative_prompt": "drums"}

    # Act
    data, extension = await render_track(track, LYRIA_SETTINGS, "secret-key")

    # Assert
    assert seen["url"] == lyria_audio.INTERACTIONS_URL and seen["key"] == "secret-key"
    assert seen["body"]["model"] == "lyria-3-clip-preview"
    assert "Avoid: drums." in seen["body"]["input"]
    assert lyria_audio.INSTRUMENTAL_NOTE in seen["body"]["input"]
    assert (data, extension) == (b"ID3-mp3", "mp3")


def test_long_tracks_use_the_full_model_and_ask_for_the_length():
    # Act
    model, full = lyria_model_for({"duration": 90}, LYRIA_SETTINGS)
    prompt = lyria_audio.lyria_prompt("epic battle", "", 90, full)

    # Assert
    assert (model, full) == ("lyria-3.5", True)
    assert "About 90 seconds long." in prompt


def test_lyria_reply_without_audio_explains_the_safety_filter():
    with pytest.raises(ValueError, match="safety filter"):
        lyria_audio.parse_lyria_reply({"steps": [{"type": "model_output", "content": []}]}, False)


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


# --- editor: audio library --------------------------------------------------------------------


async def _seed(owner_id: str, template_id: str = "audio-adv", tracks=None) -> None:
    async with TestSessionLocal() as db:
        await db.execute(delete(WorldScene).where(WorldScene.template_id == template_id))
        await db.execute(delete(AdventureTemplate).where(AdventureTemplate.id == template_id))
        db.add(
            AdventureTemplate(
                id=template_id,
                owner_id=owner_id,
                title="Audio Test",
                teaser="Bells under the sea.",
                selected_tone={"id": "dark", "name": "Dark", "description": "Grim and slow"},
                audio_tracks=tracks,
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


async def _enable_audio(provider: str = "lyria") -> None:
    from backend.core.global_settings import get_server_settings_for_update

    async with TestSessionLocal() as db:
        server = await get_server_settings_for_update(db)
        server.audio_settings = {"enabled": True, "provider": provider}
        await db.commit()


@pytest.mark.asyncio
async def test_prompt_suggestion_uses_tone_and_reference_scene(
    auth_client, setup_test_db, monkeypatch
):
    # Arrange
    await _seed(await _owner_id())
    llm = AsyncMock(return_value="Slow cello drones, 60 bpm.")
    monkeypatch.setattr(editor_audio.GameMasterLLM, "aexecute_simple_task", llm)

    # Act
    response = await auth_client.post(
        "/api/adventures/audio-adv/audio/suggest-prompt", json={"reference_scene_id": "CRYPT"}
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
    await _enable_audio()
    monkeypatch.setattr(editor_audio, "session_factory", TestSessionLocal)
    monkeypatch.setattr(editor_audio, "audio_api_key", lambda _user, _settings: "key")
    monkeypatch.setattr(editor_audio, "render_exclusive", AsyncMock(return_value=(b"ID3", "mp3")))
    base = "/api/adventures/audio-adv/audio"

    # Act
    created = (
        await auth_client.post(
            f"{base}/tracks",
            json={"name": "Crypt Theme", "prompt": "cello loop", "reference_scene_id": "CRYPT"},
        )
    ).json()
    await editor_audio.editor_jobs.tasks[created["job"]["id"]]
    track_id = created["track"]["id"]
    assigned = await auth_client.post(f"{base}/scenes/CRYPT/track", json={"track_id": track_id})
    unknown = await auth_client.post(f"{base}/scenes/HALL/track", json={"track_id": "nope"})
    library = (await auth_client.get(base)).json()

    # Assert
    track = library["tracks"][0]
    assert track["name"] == "Crypt Theme" and track["reference_scene_id"] == "CRYPT"
    assert track["url"].startswith(f"/data/adventures/library/audio-adv/audio/{track_id}_")
    assert assigned.status_code == 200 and unknown.status_code == 404
    assert library["scene_usage"] == {track_id: ["CRYPT"]}
    assert library["jobs"][track_id]["status"] == "done"
    async with TestSessionLocal() as db:
        adventure = await db.get(AdventureTemplate, "audio-adv")
        assert adventure.original_manifest["audio_tracks"][0]["id"] == track_id
        assert adventure.original_manifest["scenes"][0]["audio_track_id"] == track_id


@pytest.mark.asyncio
async def test_upload_rename_and_delete_track(auth_client, setup_test_db, monkeypatch, tmp_path):
    # Arrange
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    await _seed(await _owner_id())
    base = "/api/adventures/audio-adv/audio"
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
    assert not os.listdir(tmp_path / "adventures/library/audio-adv/audio")
    async with TestSessionLocal() as db:
        hall = (await db.execute(select(WorldScene).where(WorldScene.id == "HALL"))).scalar_one()
        assert hall.audio_track_id is None


@pytest.mark.asyncio
async def test_generation_is_rejected_while_audio_is_off(auth_client, setup_test_db):
    await _seed(await _owner_id())
    response = await auth_client.post(
        "/api/adventures/audio-adv/audio/tracks", json={"name": "x", "prompt": "harp"}
    )
    assert response.status_code == 400 and "switched off" in response.json()["detail"]


# --- playback ---------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scene_tracks_keep_playing_switch_or_fade_out(
    auth_client, setup_test_db, monkeypatch, tmp_path
):
    # Arrange
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    calm = save_library_audio("audio-adv", "calm", "aa", b"ID3", "mp3")
    storm = save_library_audio("audio-adv", "storm", "bb", b"ID3", "mp3")
    tracks = [
        {"id": "calm", "name": "Calm", "url": calm},
        {"id": "storm", "name": "Storm", "url": storm},
    ]
    await _seed(await _owner_id(), tracks=tracks)
    async with TestSessionLocal() as db:
        for scene in (await db.execute(select(WorldScene))).scalars():
            scene.audio_track_id = "calm"
        db.add(WorldScene(id="CAVE", template_id="audio-adv", label="Cave", description="."))
        db.add(
            WorldScene(
                id="PEAK",
                template_id="audio-adv",
                label="Peak",
                description=".",
                audio_track_id="storm",
            )
        )
        await db.commit()
    server = SimpleNamespace(audio_settings={"enabled": False})
    monkeypatch.setattr(audio_snapshot, "read_server_settings", AsyncMock(return_value=server))
    state = SimpleNamespace(
        session_id="sess", template_id="audio-adv", current_scene_id="CRYPT", entity_states={}
    )

    async def snapshot_in(scene_id: str) -> dict:
        state.current_scene_id = scene_id
        async with TestSessionLocal() as db:
            return await audio_snapshot.build_audio_snapshot(db, state)

    # Act
    crypt, hall, peak, cave = [await snapshot_in(s) for s in ("CRYPT", "HALL", "PEAK", "CAVE")]
    ctx = GameContext()
    ctx.audio.stop()
    apply_audio_ops(state.entity_states, ctx.changeset.audio_ops)
    silenced = await snapshot_in("CRYPT")

    # Assert
    assert crypt["now"]["url"] == hall["now"]["url"] == calm  # same track: keeps playing
    assert crypt["now"]["id"] == hall["now"]["id"] == "track:calm"
    assert peak["now"]["url"] == storm  # another track: cross-fade
    assert cave is not None and cave["now"] is None  # no track: fade out
    assert silenced["now"] is None


@pytest.mark.asyncio
async def test_no_audio_payload_without_library_or_when_author_switched_it_off(
    auth_client, setup_test_db, monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    url = save_library_audio("audio-adv", "calm", "aa", b"ID3", "mp3")
    await _seed(await _owner_id(), tracks=[{"id": "calm", "name": "Calm", "url": url}])
    async with TestSessionLocal() as db:
        adventure = await db.get(AdventureTemplate, "audio-adv")
        adventure.audio_enabled = False
        await db.commit()
    state = SimpleNamespace(
        session_id="s", template_id="audio-adv", current_scene_id="CRYPT", entity_states={}
    )
    async with TestSessionLocal() as db:
        assert await audio_snapshot.build_audio_snapshot(db, state) is None


# --- ADZ round trip, import safety, World-Builder ---------------------------------------------


@pytest.mark.asyncio
async def test_audio_library_survives_adz_export_and_import(
    auth_client, setup_test_db, monkeypatch, tmp_path
):
    # Arrange
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    owner = await _owner_id()
    url = save_library_audio("audio-export", "calm", "cc", b"CALM", "mp3")
    tracks = [
        {"id": "calm", "name": "Calm", "prompt": "harp", "url": url, "source": "generated"},
        {"id": "PLANNED", "name": "Planned", "prompt": "drums"},
    ]
    await _seed(owner, "audio-export", tracks=tracks)
    async with TestSessionLocal() as db:
        scene = (
            await db.execute(
                select(WorldScene).where(
                    WorldScene.template_id == "audio-export", WorldScene.id == "CRYPT"
                )
            )
        ).scalar_one()
        scene.audio_track_id = "calm"
        (await db.get(AdventureTemplate, "audio-export")).title_track_id = "calm"
        await db.commit()

        # Act
        adz = await AdventureExporter.export_adz(db, "audio-export")
        await db.execute(delete(WorldScene).where(WorldScene.template_id == "audio-export"))
        await db.execute(delete(AdventureTemplate).where(AdventureTemplate.id == "audio-export"))
        await db.commit()
        assert await AdventureTemplateImporter.import_adz(db, adz, owner_id=owner)
        imported = (
            await db.execute(
                select(AdventureTemplate).where(AdventureTemplate.title == "Audio Test")
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
    by_id = {t["id"]: t for t in imported.audio_tracks}
    assert crypt.audio_track_id == "calm"
    assert imported.title_track_id == "calm"
    assert by_id["PLANNED"]["url"] is None and by_id["PLANNED"]["source"] == "planned"
    assert by_id["calm"]["url"].startswith(f"/data/adventures/library/{imported.id}/")
    with open(tmp_path / by_id["calm"]["url"].removeprefix("/data/"), "rb") as handle:
        assert handle.read() == b"CALM"


def test_audio_urls_are_bound_to_the_owning_adventure(monkeypatch, tmp_path):
    # Arrange
    from backend.engine.audio.audio_assets import delete_library_audio, local_audio_url
    from backend.engine.audio.audio_library import normalize_tracks

    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    victim = save_library_audio("victim-adv", "CRYPT", "ee", b"VICTIM", "mp3")
    own = save_library_audio("own-adv", "CRYPT", "ff", b"OWN", "mp3")
    manifest = {"adventure": {"audio_tracks": [{"id": "a", "url": victim}]}}

    # Act
    map_imported_audio(manifest, {})
    delete_library_audio(victim, "own-adv")
    foreign = normalize_tracks([{"id": "x", "url": victim}], "own-adv")

    # Assert
    assert manifest["adventure"]["audio_tracks"][0]["url"] is None
    assert foreign[0]["url"] is None
    assert local_audio_url(victim, "own-adv") is None
    assert local_audio_url(own, "own-adv") == own
    assert (tmp_path / victim.removeprefix("/data/")).exists()
    delete_library_audio(own, "own-adv")
    assert not (tmp_path / own.removeprefix("/data/")).exists()


def test_world_builder_plans_tracks_and_scenes_reference_them():
    # Act
    manifest = WorldManifesto.model_json_schema()
    scene = WorldSceneSchema(id="CRYPT", name="Crypt", description="Cold.", audio_track_id="DRONE")
    blueprint, missing = analyze_blueprint(
        "[World]\ntitle_audio: DRONE\n"
        "[Audio: DRONE] Crypt Drone\nprompt: dark cello drone, 60 bpm\n"
        "[Scene: CRYPT] Crypt\nCold.\naudio: DRONE\n"
    )

    # Assert
    assert "audio_tracks" in manifest["properties"]
    assert scene.audio_track_id == "DRONE"
    assert not [i for i in blueprint.issues if i.severity == "error"] and missing == []
    assert blueprint.first("audio").fields["prompt"].value == "dark cello drone, 60 bpm"
    assert blueprint.first("scene").fields["audio_track_id"].value == "DRONE"
    assert blueprint.first("world").fields["title_track_id"].value == "DRONE"
    assert "title_track_id" in manifest["properties"]


def test_blueprint_merge_recreates_dropped_tracks():
    from backend.engine.blueprint.merge import apply_blueprint

    blueprint, _ = analyze_blueprint("[Audio: DRONE] Crypt Drone\nprompt: cello drone\n")
    manifest: dict = {"scenes": []}
    apply_blueprint(manifest, blueprint)
    assert manifest["audio_tracks"][0]["id"] == "DRONE"
    assert manifest["audio_tracks"][0]["prompt"] == "cello drone"


@pytest.mark.asyncio
async def test_manifest_apply_merges_tracks_and_keeps_rendered_audio(
    auth_client, setup_test_db, monkeypatch, tmp_path
):
    from backend.engine.manifest_apply.adventure_meta import _apply_audio_tracks

    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    url = save_library_audio("audio-adv", "calm", "aa", b"ID3", "mp3")
    adventure = SimpleNamespace(audio_tracks=[{"id": "CALM", "name": "Calm", "url": url}])
    ctx = SimpleNamespace(
        template_id="audio-adv",
        manifest={
            "audio_tracks": [
                {"id": "CALM", "name": "Calm v2", "prompt": "harp"},
                {"id": "NEW", "name": "New", "prompt": "drums"},
            ]
        },
    )
    _apply_audio_tracks(ctx, adventure)
    by_id = {t["id"]: t for t in adventure.audio_tracks}
    assert by_id["CALM"]["url"] == url and by_id["CALM"]["name"] == "Calm v2"
    assert by_id["NEW"]["source"] == "planned"


@pytest.mark.asyncio
async def test_title_song_is_the_library_tile_preview_and_is_cleared_on_delete(
    auth_client, setup_test_db, monkeypatch, tmp_path
):
    # Arrange
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    url = save_library_audio("audio-adv", "calm", "aa", b"ID3", "mp3")
    await _seed(await _owner_id(), tracks=[{"id": "calm", "name": "Calm", "url": url}])
    async with TestSessionLocal() as db:
        for scene in (await db.execute(select(WorldScene))).scalars():
            scene.audio_track_id = "calm"  # scene audio alone must not make the tile play
        await db.commit()
    base = "/api/adventures/audio-adv/audio"

    def tile(templates: list) -> dict:
        return next(t for t in templates if t["template_id"] == "audio-adv")

    # Act
    no_title = tile((await auth_client.get("/api/adventures/templates")).json())
    unknown = await auth_client.post(f"{base}/title", json={"track_id": "nope"})
    await auth_client.post(f"{base}/title", json={"track_id": "calm"})
    with_title = tile((await auth_client.get("/api/adventures/templates")).json())
    library = (await auth_client.get(base)).json()
    await auth_client.delete(f"{base}/tracks/calm")
    after_delete = tile((await auth_client.get("/api/adventures/templates")).json())

    # Assert
    assert no_title["preview_audio_url"] is None
    assert unknown.status_code == 404
    assert with_title["preview_audio_url"] == url
    assert library["title_track_id"] == "calm"
    assert after_delete["preview_audio_url"] is None
    async with TestSessionLocal() as db:
        assert (await db.get(AdventureTemplate, "audio-adv")).title_track_id is None


# --- names from before the rename to "audio" -----------------------------------------------------


def test_former_music_names_keep_working(monkeypatch, tmp_path):
    # Arrange
    from backend.engine.audio.audio_assets import delete_library_audio, legacy_library_audio_dir
    from backend.engine.audio.audio_state import read_audio_state

    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    legacy_states = {"__music__": {"rev": 4, "volume": 0.3, "tracks": {}, "library": {}}}
    ctx = GameContext()
    old_file = os.path.join(legacy_library_audio_dir("old-adv"), "calm_aa.mp3")
    os.makedirs(os.path.dirname(old_file), exist_ok=True)
    with open(old_file, "wb") as handle:
        handle.write(b"ID3")

    # Act
    legacy = read_audio_state(legacy_states)
    ctx.music.stop()  # tw.music is an alias of tw.audio
    apply_audio_ops(legacy_states, ctx.changeset.audio_ops)
    blueprint, missing = analyze_blueprint(
        "[World]\ntitle_music: DRONE\n[Music: DRONE] Drone\nprompt: cello\n"
        "[Scene: CRYPT] Crypt\nCold.\nmusic: DRONE\n"
    )
    delete_library_audio("/data/adventures/library/old-adv/music/calm_aa.mp3", "old-adv")

    # Assert
    assert legacy["rev"] == 4 and legacy["volume"] == 0.3
    assert "__music__" not in legacy_states and legacy_states["__audio__"]["silenced"] is True
    assert missing == [] and blueprint.first("audio").ref == "DRONE"
    assert blueprint.first("scene").fields["audio_track_id"].value == "DRONE"
    assert blueprint.first("world").fields["title_track_id"].value == "DRONE"
    assert not os.path.exists(old_file)


def test_manifests_with_former_music_fields_are_imported(monkeypatch, tmp_path):
    from backend.engine.manifest_apply.adventure_meta import _apply_audio_tracks
    from backend.engine.world.scene_fields import scene_content_from_dict

    adventure = SimpleNamespace(audio_tracks=None, title_track_id=None)
    ctx = SimpleNamespace(
        template_id="old-adv",
        manifest={"music_tracks": [{"id": "OLD", "name": "Old", "prompt": "harp"}]},
    )
    _apply_audio_tracks(ctx, adventure)
    assert adventure.audio_tracks[0]["id"] == "OLD"
    content = scene_content_from_dict({"id": "CRYPT", "music_track_id": "OLD"})
    assert content["audio_track_id"] == "OLD"
