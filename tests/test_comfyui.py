"""Experimental ComfyUI adapter contract without a GPU or external calls."""

import asyncio
import io
import json
from unittest.mock import AsyncMock

import httpx
import pytest
from PIL import Image
from pydantic import ValidationError

from backend.core.comfyui import ComfySettings, build_workflow
from backend.core.config import settings
from backend.engine.media import comfyui
from backend.engine.media.media_engine import MediaEngine
from backend.services.model_discovery.fetchers import fetch_comfyui
from backend.utils.path_security import data_url_to_local_path

# Keep the wrapper before the suite's autouse fixture replaces world image generation.
REAL_GENERATE_ENTITY = MediaEngine.generate_entity_image


def png():
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), "blue").save(buffer, format="PNG")
    return buffer.getvalue()


def transport(monkeypatch, handler):
    factory = httpx.AsyncClient
    monkeypatch.setattr(
        comfyui.httpx,
        "AsyncClient",
        lambda **kwargs: factory(**kwargs, transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(settings, "ALLOW_PRIVATE_NETWORK_MODELS", True)


def test_workflows_keep_prompts_opaque_and_profiles_independent():
    prompt = 'A lamp. {"workflow": "do not substitute"}'
    settings = ComfySettings(
        simple_comfyui_workflow="sd15", advanced_comfyui_workflow="sdxl"
    ).model_dump()
    first = build_workflow(
        prompt,
        "installed/simple.safetensors",
        {**settings, "comfyui_profile": "simple", "seed": 12},
    )
    second = build_workflow(
        prompt, "advanced.safetensors", {**settings, "comfyui_profile": "advanced"}
    )
    assert first["2"]["inputs"]["text"] == prompt
    assert first["1"]["inputs"]["ckpt_name"] == "installed/simple.safetensors"
    assert first["4"]["inputs"]["width"] == 512
    assert second["4"]["inputs"]["width"] == 1024
    assert first["5"]["inputs"]["seed"] == 12
    first["2"]["inputs"]["text"] = "changed"
    assert second["2"]["inputs"]["text"] == prompt


@pytest.mark.parametrize(
    "options",
    [{"comfyui_workflow": "unknown"}, {"width": 8192}, {"steps": 0}, {"cfg_scale": float("nan")}],
)
def test_invalid_graph_parameters_are_rejected(options):
    with pytest.raises((ValueError, ValidationError)):
        build_workflow("A lamp", "model.safetensors", options)


@pytest.mark.asyncio
async def test_queue_uses_configured_server_and_downloads_only_its_output(monkeypatch):
    calls = []

    async def handler(request):
        calls.append(request)
        assert request.url.host == "my-comfy.example" and request.url.port == 9191
        assert request.url.path.startswith("/custom/")
        if request.url.path.endswith("/prompt"):
            payload = json.loads(request.content)
            assert payload["prompt"]["1"]["inputs"]["ckpt_name"] == "chosen.safetensors"
            return httpx.Response(200, json={"prompt_id": "our-job"})
        if request.url.path.endswith("/history/our-job"):
            return httpx.Response(
                200,
                json={
                    "other-job": {"status": {"status_str": "error"}},
                    "our-job": {
                        "outputs": {
                            "7": {
                                "images": [
                                    {"filename": "result.png", "subfolder": "", "type": "output"}
                                ]
                            }
                        }
                    },
                },
            )
        assert request.url.path.endswith("/view")
        assert request.url.params["filename"] == "result.png"
        return httpx.Response(200, content=png())

    transport(monkeypatch, handler)
    result = await comfyui.render(
        "A lamp", "chosen.safetensors", {"comfyui_url": "http://my-comfy.example:9191/custom"}
    )
    assert result == png()
    assert [r.method for r in calls] == ["POST", "GET", "GET"]


@pytest.mark.asyncio
async def test_generation_saves_media_and_thumbnail_without_api_key(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    render = AsyncMock(return_value=png())
    monkeypatch.setattr(comfyui, "render", render)
    url = await MediaEngine.generate_image(
        "A lamp",
        "model.safetensors",
        None,
        provider="comfyui",
        target_dir=str(tmp_path / "images"),
        filename="lamp.png",
        provider_options={"image_format": "png"},
    )
    assert url
    with Image.open(data_url_to_local_path(url)) as saved:
        assert saved.size == (16, 16)
    assert (tmp_path / "images/lamp_thumb.png").exists()
    assert render.await_args.args[1] == "model.safetensors"


@pytest.mark.asyncio
async def test_checkpoint_discovery_uses_the_given_url():
    async def handler(request):
        assert str(request.url) == "http://selected.example:9191/object_info/CheckpointLoaderSimple"
        return httpx.Response(
            200,
            json={
                "CheckpointLoaderSimple": {
                    "input": {
                        "required": {"ckpt_name": [["one.safetensors", "folder/two.safetensors"]]}
                    }
                }
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await fetch_comfyui(client, None, "http://selected.example:9191")
    assert [model.id for model in result] == ["one.safetensors", "folder/two.safetensors"]


@pytest.mark.asyncio
async def test_timeout_cleans_only_own_queued_job(monkeypatch):
    calls = []

    async def handler(request):
        calls.append(request)
        if request.url.path == "/prompt":
            return httpx.Response(200, json={"prompt_id": "our-job"})
        if request.url.path == "/queue":
            assert json.loads(request.content) == {"delete": ["our-job"]}
            return httpx.Response(200, json={})
        return httpx.Response(200, json={})

    transport(monkeypatch, handler)
    with pytest.raises(asyncio.TimeoutError):
        await comfyui.render("A lamp", "model.safetensors", {"comfyui_timeout": 1})
    assert sum(r.url.path == "/prompt" for r in calls) == 1
    assert calls[-1].url.path == "/queue"
    assert all(r.url.path != "/interrupt" for r in calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["rejected", "execution", "empty", "oversized"])
async def test_failures_are_not_retried_or_replaced_with_another_image(monkeypatch, failure):
    calls = []

    async def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/prompt":
            return httpx.Response(400 if failure == "rejected" else 200, json={"prompt_id": "job"})
        if request.url.path == "/history/job":
            job = {
                "status": {
                    "completed": True,
                    "status_str": "error" if failure == "execution" else "success",
                }
            }
            if failure == "oversized":
                job["outputs"] = {
                    "7": {"images": [{"filename": "result.png", "subfolder": "", "type": "output"}]}
                }
            return httpx.Response(200, json={"job": job})
        return httpx.Response(200, content=b"oversized image")

    transport(monkeypatch, handler)
    monkeypatch.setattr(comfyui, "MAX_IMAGE_BYTES", 8)
    with pytest.raises(ValueError):
        await comfyui.render("A lamp", "model.safetensors", {})
    assert calls.count("/prompt") == 1


@pytest.mark.asyncio
async def test_private_endpoint_policy_is_preserved(monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_PRIVATE_NETWORK_MODELS", False)
    with pytest.raises(ValueError, match="private/loopback"):
        await comfyui.render(
            "A lamp", "model.safetensors", {"comfyui_url": "http://127.0.0.1:8188"}
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("advanced", [True, False])
async def test_existing_asset_quality_routing_selects_the_correct_comfy_profile(
    monkeypatch, advanced
):
    generate = AsyncMock(return_value="/data/image.png")
    monkeypatch.setattr(MediaEngine, "generate_image", generate)
    await REAL_GENERATE_ENTITY(
        "A lamp",
        "adventure",
        "lamp",
        "OBJECT",
        {
            "t2i_settings": {
                "simple_model_provider": "comfyui",
                "advanced_model_provider": "comfyui",
                "simple_model": "fast.safetensors",
                "advanced_model": "quality.safetensors",
                "simple_comfyui_workflow": "sd15",
                "advanced_comfyui_workflow": "sdxl",
                "comfyui_url": "http://chosen.example:9191",
            }
        },
        {},
        use_advanced_model=advanced,
    )
    request = generate.await_args.kwargs
    assert request["model"] == ("quality.safetensors" if advanced else "fast.safetensors")
    assert request["provider_options"]["comfyui_profile"] == ("advanced" if advanced else "simple")
    assert request["provider_options"]["comfyui_url"] == "http://chosen.example:9191"


@pytest.mark.asyncio
async def test_settings_roundtrip_and_keyless_test_use_selected_url(auth_client, monkeypatch):
    payload = {
        "provider": "comfyui",
        "simple_model_provider": "comfyui",
        "advanced_model_provider": "comfyui",
        "simple_model": "fast.safetensors",
        "advanced_model": "quality.safetensors",
        "comfyui_url": "http://selected-gpu.example:9191/comfy",
        "comfyui_timeout": 720,
        "simple_comfyui_workflow": "sd15",
        "advanced_comfyui_workflow": "sdxl",
    }
    saved = await auth_client.post("/api/settings/t2i", json=payload)
    assert saved.status_code == 200, saved.text
    loaded = (await auth_client.get("/api/settings")).json()["t2i_settings"]
    for key, value in payload.items():
        assert loaded[key] == value
    generate = AsyncMock(return_value="/data/test.png")
    monkeypatch.setattr(MediaEngine, "generate_image", generate)
    result = await auth_client.post(
        "/api/settings/test-vision",
        json={
            "provider": "comfyui",
            "model": "fast.safetensors",
            "comfyui_workflow": "sd15",
            "comfyui_url": payload["comfyui_url"],
            "comfyui_timeout": 720,
        },
    )
    assert result.json()["status"] == "success", result.text
    options = generate.await_args.kwargs["provider_options"]
    assert options["comfyui_url"] == payload["comfyui_url"]
    assert options["comfyui_timeout"] == 720 and options["comfyui_workflow"] == "sd15"
    assert max(options["width"], options["height"]) == 512


@pytest.mark.asyncio
async def test_cancellation_never_interrupts_another_job(monkeypatch):
    waiting = asyncio.Event()
    calls = []

    async def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/prompt":
            return httpx.Response(200, json={"prompt_id": "our-job"})
        if request.url.path == "/queue":
            assert json.loads(request.content) == {"delete": ["our-job"]}
            return httpx.Response(200, json={})
        waiting.set()
        await asyncio.Event().wait()

    transport(monkeypatch, handler)
    task = asyncio.create_task(comfyui.render("A lamp", "model.safetensors", {}))
    await asyncio.wait_for(waiting.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls[-1] == "/queue" and "/interrupt" not in calls


def test_comfy_profile_sampling_is_used_for_catalog_and_account_images():
    graph = build_workflow(
        "A lamp",
        "model.safetensors",
        {
            "simple_steps": 35,
            "simple_cfg_scale": 6.0,
            "simple_sampler_name": "euler_ancestral",
            "simple_scheduler": "normal",
            "steps": None,
            "simple_comfyui_workflow": "sd15",
        },
    )
    assert graph["5"]["inputs"]["steps"] == 35
    assert graph["5"]["inputs"]["sampler_name"] == "euler_ancestral"
    assert graph["5"]["inputs"]["cfg"] == 6.0
