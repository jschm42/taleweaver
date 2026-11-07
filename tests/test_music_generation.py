"""Music generation: settings, ComfyUI workflow filling and transport, tw.music, session state."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from backend.api.routes.adventures import music_snapshot
from backend.core.config import settings
from backend.core.music_settings import (
    is_music_available,
    normalize_music_settings,
    public_music_settings,
    validate_music_workflow,
)
from backend.engine.audio import comfyui_music, music_generation
from backend.engine.audio.comfyui_music import AudioResult, audio_parameters, render_music
from backend.engine.audio.music_state import (
    MUSIC_STATE_KEY,
    apply_music_ops,
    read_music_state,
)
from backend.engine.audio.music_workflow import fill_music_workflow
from backend.engine.scripting.context import GameContext
from backend.engine.scripting.runner import ScriptRunner

WORKFLOW = {
    "1": {"class_type": "TextEncodeAceStepAudio", "inputs": {"tags": "{{prompt}}, game score"}},
    "2": {"class_type": "EmptyAceStepLatentAudio", "inputs": {"seconds": "{{duration}}"}},
    "3": {
        "class_type": "KSampler",
        "inputs": {"seed": "{{seed}}", "positive": ["1", 0], "latent_image": ["2", 0]},
    },
    "4": {"class_type": "SaveAudio", "inputs": {"audio": ["3", 0], "filename_prefix": "tw"}},
}


@pytest.fixture(autouse=True)
def _reset_jobs():
    music_generation._jobs.clear()
    music_generation._errors.clear()
    yield
    music_generation._jobs.clear()
    music_generation._errors.clear()


# --- settings & workflow ----------------------------------------------------------------


def test_workflow_validation_rejects_ui_format_and_missing_prompt():
    # Arrange
    ui_format = {"nodes": [], "links": [], "version": 0.4}
    no_prompt = {"1": {"class_type": "SaveAudio", "inputs": {}}}

    # Act / Assert
    validate_music_workflow(WORKFLOW)
    with pytest.raises(ValueError, match="Export"):
        validate_music_workflow(ui_format)
    with pytest.raises(ValueError, match="prompt"):
        validate_music_workflow(no_prompt)


def test_public_settings_hide_the_workflow_and_availability_needs_one():
    # Arrange
    stored = normalize_music_settings({"enabled": True, "comfyui_workflow": WORKFLOW})

    # Act
    public = public_music_settings(stored)

    # Assert
    assert "comfyui_workflow" not in public
    assert public["has_workflow"] is True and public["workflow_node_count"] == 4
    assert is_music_available(stored)
    assert not is_music_available({"enabled": True})


def test_fill_keeps_links_and_inserts_typed_values():
    # Arrange
    prompt = 'storm ", "class_type": "Evil'

    # Act
    graph = fill_music_workflow(WORKFLOW, prompt=prompt, seed=7, duration=45)

    # Assert
    assert graph["1"]["inputs"]["tags"] == f"{prompt}, game score"
    assert graph["2"]["inputs"]["seconds"] == 45
    assert graph["3"]["inputs"]["seed"] == 7
    assert graph["3"]["inputs"]["positive"] == ["1", 0]
    assert WORKFLOW["1"]["inputs"]["tags"] == "{{prompt}}, game score"


# --- ComfyUI transport ------------------------------------------------------------------


def test_audio_parameters_validate_output():
    # Arrange
    job = {"outputs": {"4": {"audio": [{"filename": "a.flac", "subfolder": "", "type": "output"}]}}}
    bad = {"outputs": {"4": {"audio": [{"filename": "../a.flac", "type": "output"}]}}}

    # Act
    found = audio_parameters(job)

    # Assert
    assert found == ({"filename": "a.flac", "subfolder": "", "type": "output"}, "flac")
    assert audio_parameters({"outputs": {}}) is None
    with pytest.raises(ValueError):
        audio_parameters(bad)
    with pytest.raises(ValueError, match="SaveAudio"):
        audio_parameters({"status": {"completed": True}, "outputs": {}})


@pytest.mark.asyncio
async def test_render_music_submits_graph_and_downloads_audio(monkeypatch):
    # Arrange
    calls = []

    async def handler(request):
        calls.append(request)
        if request.url.path == "/prompt":
            assert json.loads(request.content)["prompt"]["1"]["class_type"]
            return httpx.Response(200, json={"prompt_id": "job-1"})
        if request.url.path == "/history/job-1":
            entry = {"filename": "tw_0001.mp3", "subfolder": "audio", "type": "output"}
            return httpx.Response(200, json={"job-1": {"outputs": {"4": {"audio": [entry]}}}})
        assert request.url.params["filename"] == "tw_0001.mp3"
        return httpx.Response(200, content=b"ID3-audio")

    factory = httpx.AsyncClient
    monkeypatch.setattr(
        comfyui_music.httpx,
        "AsyncClient",
        lambda **kwargs: factory(**kwargs, transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(settings, "ALLOW_PRIVATE_NETWORK_MODELS", True)

    # Act
    result = await render_music(WORKFLOW, comfyui_url="http://comfy.example:8188", timeout=10)

    # Assert
    assert result == AudioResult(b"ID3-audio", "mp3")
    assert [r.method for r in calls] == ["POST", "GET", "GET"]


# --- tw.music & session state -----------------------------------------------------------


def test_script_api_records_ops_and_replays_into_entity_states():
    # Arrange
    ctx = GameContext()
    code = (
        "first = tw.music.generate('dark cave ambience', name='cave', duration=40)\n"
        "again = tw.music.generate('ignored prompt', name='cave')\n"
        "tw.vars.set('same', first == again)\n"
        "tw.vars.set('has', tw.music.has('cave'))\n"
        "tw.vars.set('current', tw.music.current)\n"
        "tw.music.set_volume(0.4)\n"
        "tw.music.stop()\n"
        "tw.vars.set('playing', tw.music.is_playing)\n"
    )

    # Act
    ScriptRunner([]).execute_code(code, {"tw": ctx})
    entity_states: dict = {}
    changed = apply_music_ops(entity_states, ctx.changeset.music_ops)
    music = read_music_state(entity_states)

    # Assert
    assert changed and ctx.changeset.has_changes
    assert ctx.changeset.var_updates == {
        "same": True,
        "has": True,
        "current": "cave",
        "playing": False,
    }
    assert len(music["tracks"]) == 1
    track = next(iter(music["tracks"].values()))
    assert track["prompt"] == "dark cave ambience" and track["duration"] == 40
    assert music["volume"] == 0.4 and music["now"] is None
    assert music["rev"] == len(ctx.changeset.music_ops)


def test_play_reuses_named_tracks_from_the_session_state():
    # Arrange
    first = GameContext()
    track_id = first.music.generate("tavern folk", name="tavern", play=False)
    states: dict = {}
    apply_music_ops(states, first.changeset.music_ops)
    second = GameContext(music=read_music_state(states))

    # Act
    played = second.music.play("tavern")
    missing = second.music.play("unknown")
    apply_music_ops(states, second.changeset.music_ops)

    # Assert
    assert played and not missing
    assert states[MUSIC_STATE_KEY]["now"]["id"] == track_id
    assert second.music.tracks == ["tavern"]


def test_empty_prompt_is_rejected():
    ctx = GameContext()
    assert ctx.music.generate("  ") is None
    assert ctx.changeset.music_ops == []


# --- background generation & snapshot ---------------------------------------------------


@pytest.mark.asyncio
async def test_snapshot_starts_generation_and_reports_ready_track(monkeypatch, tmp_path):
    # Arrange
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    render = AsyncMock(return_value=AudioResult(b"fLaC", "flac"))
    monkeypatch.setattr(music_generation, "render_music", render)
    server = SimpleNamespace(music_settings={"enabled": True, "comfyui_workflow": WORKFLOW})
    monkeypatch.setattr(music_snapshot, "read_server_settings", AsyncMock(return_value=server))
    ctx = GameContext()
    track_id = ctx.music.generate("battle drums", name="battle")
    states: dict = {}
    apply_music_ops(states, ctx.changeset.music_ops)
    state = SimpleNamespace(session_id="session-1", entity_states=states)

    # Act
    pending = await music_snapshot.build_music_snapshot(None, state)
    await music_generation._jobs[f"session-1:{track_id}"]
    ready = await music_snapshot.build_music_snapshot(None, state)

    # Assert
    assert pending["now"]["status"] == "pending" and pending["enabled"]
    assert ready["now"]["status"] == "ready"
    assert ready["now"]["url"] == f"/data/adventures/sessions/session-1/music/{track_id}.flac"
    graph = render.await_args.args[0]
    assert graph["1"]["inputs"]["tags"] == "battle drums, game score"
    assert graph["2"]["inputs"]["seconds"] == 30


@pytest.mark.asyncio
async def test_snapshot_enforces_the_session_generation_limit(monkeypatch, tmp_path):
    # Arrange
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    raw = {"enabled": True, "comfyui_workflow": WORKFLOW, "max_generations_per_session": 0}
    server = SimpleNamespace(music_settings=raw)
    monkeypatch.setattr(music_snapshot, "read_server_settings", AsyncMock(return_value=server))
    ctx = GameContext()
    ctx.music.generate("rain")
    states: dict = {}
    apply_music_ops(states, ctx.changeset.music_ops)

    # Act
    snapshot = await music_snapshot.build_music_snapshot(
        None, SimpleNamespace(session_id="s2", entity_states=states)
    )

    # Assert
    assert snapshot["now"]["status"] == "failed"
    assert snapshot["now"]["error"] == music_snapshot.LIMIT_MESSAGE
    assert music_generation._jobs == {}


@pytest.mark.asyncio
async def test_no_snapshot_without_requested_music():
    state = SimpleNamespace(session_id="s3", entity_states={})
    assert await music_snapshot.build_music_snapshot(None, state) is None


# --- admin API --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_uploads_workflow_and_saves_settings(auth_client, setup_test_db):
    # Arrange
    upload = {"file": ("ace_step.json", json.dumps(WORKFLOW), "application/json")}
    ui_export = {"file": ("ui.json", json.dumps({"nodes": [], "links": []}), "application/json")}

    # Act
    stored = await auth_client.post("/api/settings/music/workflow", files=upload)
    rejected = await auth_client.post("/api/settings/music/workflow", files=ui_export)
    saved = await auth_client.post(
        "/api/settings/music", json={"enabled": True, "default_duration": 45}
    )
    reloaded = (await auth_client.get("/api/settings/music")).json()
    removed = (await auth_client.delete("/api/settings/music/workflow")).json()

    # Assert
    assert stored.status_code == 200 and stored.json()["comfyui_workflow_name"] == "ace_step.json"
    assert rejected.status_code == 400 and "Export (API)" in rejected.json()["detail"]
    assert saved.status_code == 200
    assert reloaded["enabled"] and reloaded["has_workflow"] and reloaded["default_duration"] == 45
    assert removed["has_workflow"] is False and removed["enabled"] is True


@pytest.mark.asyncio
async def test_admin_test_run_without_workflow_is_a_clear_error(auth_client, setup_test_db):
    # Act
    response = await auth_client.post("/api/settings/music/test", json={"prompt": "calm harp"})

    # Assert
    assert response.status_code == 400
    assert "workflow" in response.json()["detail"]
