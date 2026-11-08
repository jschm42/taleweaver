"""Audio generation: settings, ComfyUI workflow filling and transport, tw.audio, session state."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from backend.api.routes.adventures import audio_snapshot
from backend.core.audio_settings import (
    is_audio_available,
    normalize_audio_settings,
    public_audio_settings,
    validate_audio_workflow,
)
from backend.core.config import settings
from backend.engine.audio import audio_generation, audio_providers, comfyui_audio
from backend.engine.audio.audio_state import (
    AUDIO_STATE_KEY,
    apply_audio_ops,
    read_audio_state,
)
from backend.engine.audio.audio_workflow import fill_audio_workflow
from backend.engine.audio.comfyui_audio import AudioResult, audio_parameters, render_audio
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
    audio_generation._jobs.clear()
    audio_generation._errors.clear()
    yield
    audio_generation._jobs.clear()
    audio_generation._errors.clear()


# --- settings & workflow ----------------------------------------------------------------


def test_workflow_validation_rejects_ui_format_and_missing_prompt():
    # Arrange
    ui_format = {"nodes": [], "links": [], "version": 0.4}
    no_prompt = {"1": {"class_type": "SaveAudio", "inputs": {}}}

    # Act / Assert
    validate_audio_workflow(WORKFLOW)
    with pytest.raises(ValueError, match="Export"):
        validate_audio_workflow(ui_format)
    with pytest.raises(ValueError, match="prompt"):
        validate_audio_workflow(no_prompt)


def test_public_settings_hide_the_workflow_and_availability_needs_one():
    # Arrange
    stored = normalize_audio_settings({"enabled": True, "comfyui_workflow": WORKFLOW})

    # Act
    public = public_audio_settings(stored)

    # Assert
    assert "comfyui_workflow" not in public
    assert public["has_workflow"] is True and public["workflow_node_count"] == 4
    assert is_audio_available(stored)
    assert not is_audio_available({"enabled": True})


def test_fill_keeps_links_and_inserts_typed_values():
    # Arrange
    prompt = 'storm ", "class_type": "Evil'

    # Act
    graph = fill_audio_workflow(WORKFLOW, prompt=prompt, seed=7, duration=45)

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
async def test_render_audio_submits_graph_and_downloads_audio(monkeypatch):
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
        comfyui_audio.httpx,
        "AsyncClient",
        lambda **kwargs: factory(**kwargs, transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(settings, "ALLOW_PRIVATE_NETWORK_MODELS", True)

    # Act
    result = await render_audio(WORKFLOW, comfyui_url="http://comfy.example:8188", timeout=10)

    # Assert
    assert result == AudioResult(b"ID3-audio", "mp3")
    assert [r.method for r in calls] == ["POST", "GET", "GET"]


# --- tw.audio & session state -----------------------------------------------------------


def test_script_api_records_ops_and_replays_into_entity_states():
    # Arrange
    ctx = GameContext()
    code = (
        "first = tw.audio.generate('dark cave ambience', name='cave', duration=40)\n"
        "again = tw.audio.generate('ignored prompt', name='cave')\n"
        "tw.vars.set('same', first == again)\n"
        "tw.vars.set('has', tw.audio.has('cave'))\n"
        "tw.vars.set('current', tw.audio.current)\n"
        "tw.audio.set_volume(0.4)\n"
        "tw.audio.stop()\n"
        "tw.vars.set('playing', tw.audio.is_playing)\n"
    )

    # Act
    ScriptRunner([]).execute_code(code, {"tw": ctx})
    entity_states: dict = {}
    changed = apply_audio_ops(entity_states, ctx.changeset.audio_ops)
    audio = read_audio_state(entity_states)

    # Assert
    assert changed and ctx.changeset.has_changes
    assert ctx.changeset.var_updates == {
        "same": True,
        "has": True,
        "current": "cave",
        "playing": False,
    }
    assert len(audio["tracks"]) == 1
    track = next(iter(audio["tracks"].values()))
    assert track["prompt"] == "dark cave ambience" and track["duration"] == 40
    assert audio["volume"] == 0.4 and audio["now"] is None
    assert audio["rev"] == len(ctx.changeset.audio_ops)


def test_play_reuses_named_tracks_from_the_session_state():
    # Arrange
    first = GameContext()
    track_id = first.audio.generate("tavern folk", name="tavern", play=False)
    states: dict = {}
    apply_audio_ops(states, first.changeset.audio_ops)
    second = GameContext(audio=read_audio_state(states))

    # Act
    played = second.audio.play("tavern")
    missing = second.audio.play("unknown")
    apply_audio_ops(states, second.changeset.audio_ops)

    # Assert
    assert played and not missing
    assert states[AUDIO_STATE_KEY]["now"]["id"] == track_id
    assert second.audio.tracks == ["tavern"]


def test_empty_prompt_is_rejected():
    ctx = GameContext()
    assert ctx.audio.generate("  ") is None
    assert ctx.changeset.audio_ops == []


# --- background generation & snapshot ---------------------------------------------------


@pytest.mark.asyncio
async def test_snapshot_starts_generation_and_reports_ready_track(monkeypatch, tmp_path):
    # Arrange
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    render = AsyncMock(return_value=AudioResult(b"fLaC", "flac"))
    monkeypatch.setattr(audio_providers, "render_audio", render)
    server = SimpleNamespace(audio_settings={"enabled": True, "comfyui_workflow": WORKFLOW})
    monkeypatch.setattr(audio_snapshot, "read_server_settings", AsyncMock(return_value=server))
    ctx = GameContext()
    track_id = ctx.audio.generate("battle drums", name="battle")
    states: dict = {}
    apply_audio_ops(states, ctx.changeset.audio_ops)
    state = SimpleNamespace(session_id="session-1", entity_states=states)

    # Act
    pending = await audio_snapshot.build_audio_snapshot(None, state)
    await audio_generation._jobs[f"session-1:{track_id}"]
    ready = await audio_snapshot.build_audio_snapshot(None, state)

    # Assert
    assert pending["now"]["status"] == "pending" and pending["enabled"]
    assert ready["now"]["status"] == "ready"
    assert ready["now"]["url"] == f"/data/adventures/sessions/session-1/audio/{track_id}.flac"
    graph = render.await_args.args[0]
    assert graph["1"]["inputs"]["tags"] == "battle drums, game score"
    assert graph["2"]["inputs"]["seconds"] == 30


@pytest.mark.asyncio
async def test_snapshot_enforces_the_session_generation_limit(monkeypatch, tmp_path):
    # Arrange
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    raw = {"enabled": True, "comfyui_workflow": WORKFLOW, "max_generations_per_session": 0}
    server = SimpleNamespace(audio_settings=raw)
    monkeypatch.setattr(audio_snapshot, "read_server_settings", AsyncMock(return_value=server))
    ctx = GameContext()
    ctx.audio.generate("rain")
    states: dict = {}
    apply_audio_ops(states, ctx.changeset.audio_ops)

    # Act
    snapshot = await audio_snapshot.build_audio_snapshot(
        None, SimpleNamespace(session_id="s2", entity_states=states)
    )

    # Assert
    assert snapshot["now"]["status"] == "failed"
    assert snapshot["now"]["error"] == audio_snapshot.LIMIT_MESSAGE
    assert audio_generation._jobs == {}


@pytest.mark.asyncio
async def test_no_snapshot_without_any_audio(setup_test_db):
    from tests.conftest import TestSessionLocal

    state = SimpleNamespace(
        session_id="s3", template_id="t3", current_scene_id="NOWHERE", entity_states={}
    )
    async with TestSessionLocal() as db:
        assert await audio_snapshot.build_audio_snapshot(db, state) is None


# --- admin API --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_uploads_workflow_and_saves_settings(auth_client, setup_test_db):
    # Arrange
    upload = {"file": ("ace_step.json", json.dumps(WORKFLOW), "application/json")}
    ui_export = {"file": ("ui.json", json.dumps({"nodes": [], "links": []}), "application/json")}

    # Act
    stored = await auth_client.post("/api/settings/audio/workflow", files=upload)
    rejected = await auth_client.post("/api/settings/audio/workflow", files=ui_export)
    saved = await auth_client.post(
        "/api/settings/audio", json={"enabled": True, "default_duration": 45}
    )
    reloaded = (await auth_client.get("/api/settings/audio")).json()
    removed = (await auth_client.delete("/api/settings/audio/workflow")).json()

    # Assert
    assert stored.status_code == 200 and stored.json()["comfyui_workflow_name"] == "ace_step.json"
    assert rejected.status_code == 400 and "Export (API)" in rejected.json()["detail"]
    assert saved.status_code == 200
    assert reloaded["enabled"] and reloaded["has_workflow"] and reloaded["default_duration"] == 45
    assert removed["has_workflow"] is False and removed["enabled"] is True


@pytest.mark.asyncio
async def test_admin_test_run_without_workflow_is_a_clear_error(auth_client, setup_test_db):
    # Act
    response = await auth_client.post("/api/settings/audio/test", json={"prompt": "calm harp"})

    # Assert
    assert response.status_code == 400
    assert "workflow" in response.json()["detail"]


@pytest.mark.asyncio
async def test_admin_test_run_renders_in_background_and_is_polled(
    auth_client, setup_test_db, monkeypatch, tmp_path
):
    # Arrange
    from backend.engine.audio import audio_test_runs

    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    release = asyncio.Event()

    async def slow_render(track, _settings, _api_key=None):
        await release.wait()
        return b"fLaC", "flac"

    monkeypatch.setattr(audio_test_runs, "render_exclusive", slow_render)
    upload = {"file": ("wf.json", json.dumps(WORKFLOW), "application/json")}
    await auth_client.post("/api/settings/audio/workflow", files=upload)

    # Act
    started = (await auth_client.post("/api/settings/audio/test", json={"prompt": "harp"})).json()
    running = (await auth_client.get(f"/api/settings/audio/test/{started['id']}")).json()
    release.set()
    await audio_test_runs.test_jobs.tasks[started["id"]]
    finished = (await auth_client.get(f"/api/settings/audio/test/{started['id']}")).json()
    unknown = await auth_client.get("/api/settings/audio/test/0123456789abcdef")

    # Assert
    assert started["status"] == "running" and running["status"] == "running"
    assert finished["status"] == "done" and finished["bytes"] == 4
    assert finished["url"].startswith("/data/scratch/audio_test/")
    assert unknown.status_code == 404


@pytest.mark.asyncio
async def test_slow_status_poll_while_loading_model_is_retried(monkeypatch):
    # Arrange
    polls = {"count": 0}

    async def handler(request):
        if request.url.path == "/prompt":
            return httpx.Response(200, json={"prompt_id": "job-2"})
        if request.url.path == "/history/job-2":
            polls["count"] += 1
            if polls["count"] == 1:
                raise httpx.ReadTimeout("model loading", request=request)
            entry = {"filename": "a.flac", "subfolder": "", "type": "output"}
            return httpx.Response(200, json={"job-2": {"outputs": {"4": {"audio": [entry]}}}})
        return httpx.Response(200, content=b"fLaC")

    factory = httpx.AsyncClient
    monkeypatch.setattr(
        comfyui_audio.httpx,
        "AsyncClient",
        lambda **kwargs: factory(**kwargs, transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(comfyui_audio, "POLL_SECONDS", 0)
    monkeypatch.setattr(settings, "ALLOW_PRIVATE_NETWORK_MODELS", True)

    # Act
    result = await render_audio(WORKFLOW, comfyui_url="http://comfy.example:8188", timeout=10)

    # Assert
    assert result.data == b"fLaC" and polls["count"] == 2
