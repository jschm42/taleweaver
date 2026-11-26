"""Tests for Phase 4 MCP generation and media rendering tools."""

import asyncio
import base64
from io import BytesIO

from PIL import Image

import backend.api.routes.adventures.editing.validation as editing_validation
import backend.api.routes.adventures.templates as template_routes
from backend.api.routes.adventures import adventure_creation
from backend.api.routes.adventures.editing import ai_fix_suggest, section_generation
from backend.api.routes.adventures.schemas import StoryIdeaSuggestionResponse
from backend.core.config import settings
from backend.core.mcp_settings import generate_mcp_token
from backend.engine.media.media_engine import MediaEngine
from backend.engine.world.sections import default_section
from backend.mcp import tools_media
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.mcp_token import McpToken
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldScene
from backend.schemas.validation import AIFixSuggestionsResponse, ValidationRunResponse
from tests.conftest import TestSessionLocal
from tests.server_settings_helpers import seed_server_settings


def _rpc(method: str, params: dict | None = None, req_id: int = 1) -> dict:
    payload: dict = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        payload["params"] = params
    return payload


def _png_b64() -> str:
    buf = BytesIO()
    Image.new("RGB", (16, 16), color=(30, 80, 120)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


async def _seed_gen_media(*, gen: bool = True, media: bool = True) -> dict[str, str]:
    plain, prefix, digest = generate_mcp_token()
    async with TestSessionLocal() as db:
        await seed_server_settings(
            db,
            mcp_settings={
                "enabled": True,
                "features": {
                    "read_adventures": True,
                    "read_sessions": True,
                    "edit_adventures": True,
                    "generate_adventures": gen,
                    "generate_media": media,
                    "diagnostics": True,
                },
                "allow_destructive": False,
                "allow_cross_user_access": False,
            },
        )
        user = User(username="creator", hashed_password="x", role="admin")
        db.add(user)
        await db.flush()
        db.add(
            McpToken(
                name="Creator Token",
                token_prefix=prefix,
                token_hash=digest,
                user_id=user.id,
            )
        )
        sections = [
            default_section("Star Harbor"),
            {
                "id": "DOCKS",
                "label": "Old Docks",
                "description": "Foggy piers.",
                "status": "stub",
                "brief": "Smuggler dock",
                "planned_links": [],
            },
        ]
        tpl = AdventureTemplate(
            owner_id=user.id,
            title="Star Harbor",
            origin_id="star-harbor",
            world_sections=sections,
            is_ready=True,
            creation_status="Ready",
            generation_logs=[{"step": "init", "message": "done"}],
            audio_tracks=[{"id": "HARBOR_THEME", "name": "Harbor", "prompt": "cello, 80 bpm"}],
        )
        db.add(tpl)
        await db.flush()
        db.add(Avatar(user_id=user.id, template_id=tpl.id, name="Lyra", role="Pilot"))
        db.add(
            WorldScene(
                id="PLAZA",
                template_id=tpl.id,
                label="Star Plaza",
                description="Stone square.",
                section_id="MAIN",
            )
        )
        db.add(
            WorldEntity(
                id="RECIPE_COMPASS",
                template_id=tpl.id,
                entity_type="OBJECT",
                item_type="CONSTRUCTABLE",
                name="Star Compass Recipe",
                description="Recipe",
                current_scene_id="PLAZA",
            )
        )
        await db.commit()
        return {"token": plain, "template_id": tpl.id}


async def _call(client, token: str, name: str, arguments: dict) -> dict:
    res = await client.post(
        "/mcp",
        json=_rpc("tools/call", {"name": name, "arguments": arguments}),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    return res.json()["result"]


async def test_mcp_generation_and_media_feature_gates(client, setup_test_db):
    seeded = await _seed_gen_media(gen=False, media=False)
    tok = seeded["token"]

    tools_res = await client.post(
        "/mcp", json=_rpc("tools/list"), headers={"Authorization": f"Bearer {tok}"}
    )
    names = {t["name"] for t in tools_res.json()["result"]["tools"]}
    assert "generate_adventure" not in names
    assert "generate_visual" not in names

    denied_gen = await _call(client, tok, "suggest_story_idea", {"title": "Test"})
    assert denied_gen["isError"] is True
    denied_media = await _call(
        client,
        tok,
        "generate_visual",
        {"adventure": seeded["template_id"], "target_type": "cover"},
    )
    assert denied_media["isError"] is True


async def test_mcp_generation_tools(client, setup_test_db, monkeypatch):
    seeded = await _seed_gen_media(gen=True, media=False)
    tok = seeded["token"]
    tpl_id = seeded["template_id"]

    async def fake_suggest(_payload, current_user=None):
        return StoryIdeaSuggestionResponse(title="Glass Tide", story_idea="A harbor mystery.")

    monkeypatch.setattr(template_routes, "suggest_story_idea", fake_suggest)
    sug = await _call(client, tok, "suggest_story_idea", {"title": "Glass Tide"})
    assert sug["structuredContent"]["story_idea"] == "A harbor mystery."

    bg_calls: list[str] = []

    async def fake_bg_gen(job):
        bg_calls.append(job.template_id)

    monkeypatch.setattr(adventure_creation, "run_background_generation", fake_bg_gen)
    gen_res = await _call(
        client,
        tok,
        "generate_adventure",
        {"title": "Glass Tide", "original_prompt": "A harbor mystery.", "skip_generation": False},
    )
    gen_sc = gen_res["structuredContent"]
    assert gen_sc["status"] == "generating"
    await asyncio.sleep(0)
    assert bg_calls == [gen_sc["template_id"]]

    status_res = await _call(
        client, tok, "get_generation_status", {"adventure": tpl_id, "include_logs": True}
    )
    assert status_res["structuredContent"]["is_ready"] is True
    assert len(status_res["structuredContent"]["logs"]) == 1

    cancel_res = await _call(client, tok, "cancel_generation", {"adventure": gen_sc["template_id"]})
    assert cancel_res["structuredContent"]["status"] == "cancelled"

    async def fake_start_section(tid, section_id, _req, db=None, current_user=None):
        return {"status": "generating", "section_id": section_id}

    monkeypatch.setattr(section_generation, "start_section_generation", fake_start_section)
    reg_res = await _call(
        client,
        tok,
        "generate_region",
        {"adventure": tpl_id, "section_id": "DOCKS", "brief": "Piers"},
    )
    assert reg_res["structuredContent"]["section_id"] == "DOCKS"

    async def fake_val_run(_db, _tid, _user, _inc):
        return ValidationRunResponse(
            structural_findings=[], ai_findings=[], run_at="2026-11-26T00:00:00Z"
        )

    async def fake_suggest_fix(_tid, _req, force_refresh=False, db=None, current_user=None):
        return AIFixSuggestionsResponse(
            finding_signature="sig1", proposals=[], generated_at="2026-11-26T00:00:00Z"
        )

    monkeypatch.setattr(editing_validation, "execute_validation_run", fake_val_run)
    monkeypatch.setattr(ai_fix_suggest, "ai_suggest_fix_for_finding", fake_suggest_fix)

    val_res = await _call(client, tok, "ai_validate_and_suggest_fixes", {"adventure": tpl_id})
    assert val_res["structuredContent"]["mode"] == "validate"
    fix_res = await _call(
        client,
        tok,
        "ai_validate_and_suggest_fixes",
        {"adventure": tpl_id, "finding_code": "dead_end", "finding_message": "No exit"},
    )
    assert fix_res["structuredContent"]["mode"] == "suggest_fix"


async def test_mcp_media_tools(client, setup_test_db, tmp_path, monkeypatch):
    seeded = await _seed_gen_media(gen=False, media=True)
    tok = seeded["token"]
    tpl_id = seeded["template_id"]
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))

    regen_calls: list[tuple[str, str]] = []

    async def fake_regen(tid, req, db=None, current_user=None):
        regen_calls.append((req.target_type, req.target_id))
        return {"status": "success", "image_url": f"/data/{req.target_type}_{req.target_id}.webp"}

    async def fake_slide(tid, req, db=None, current_user=None):
        return {"url": f"/data/slide_{tid}.webp", "prompt": req.prompt}

    monkeypatch.setattr(tools_media.visual_assets, "regenerate_visual", fake_regen)
    monkeypatch.setattr(tools_media.cutscene_routes, "generate_slide_image", fake_slide)

    vis = await _call(
        client,
        tok,
        "generate_visual",
        {"adventure": tpl_id, "target_type": "scene", "target_id": "PLAZA"},
    )
    assert vis["structuredContent"]["image_url"] == "/data/scene_PLAZA.webp"

    slide = await _call(
        client,
        tok,
        "generate_visual",
        {"adventure": tpl_id, "target_type": "cutscene_slide", "prompt": "Ship in fog"},
    )
    assert slide["structuredContent"]["image_url"] == f"/data/slide_{tpl_id}.webp"

    # Batch sync: skips CONSTRUCTABLE recipe
    regen_calls.clear()
    batch_sync = await _call(
        client,
        tok,
        "generate_adventure_visuals",
        {"adventure": tpl_id, "run_async": False, "only_missing": True},
    )
    assert batch_sync["structuredContent"]["status"] == "done"
    assert batch_sync["structuredContent"]["total"] == 3
    assert all(tid != "RECIPE_COMPASS" for _, tid in regen_calls)

    # Batch async + polling
    batch_async = await _call(
        client,
        tok,
        "generate_adventure_visuals",
        {"adventure": tpl_id, "run_async": True, "targets": ["cover"]},
    )
    job_id = batch_async["structuredContent"]["job_id"]
    await asyncio.sleep(0.05)
    job_status = await _call(client, tok, "get_visual_job_status", {"job_id": job_id})
    assert job_status["structuredContent"]["status"] == "done"
    assert job_status["structuredContent"]["completed"] == 1

    # Upload visual + path traversal guard
    bad_b64 = await _call(
        client,
        tok,
        "upload_visual",
        {"adventure": tpl_id, "target_type": "cover", "image_base64": "!!!"},
    )
    assert bad_b64["isError"] is True

    bad_target = await _call(
        client,
        tok,
        "upload_visual",
        {
            "adventure": tpl_id,
            "target_type": "scene",
            "target_id": "../evil",
            "image_base64": _png_b64(),
        },
    )
    assert bad_target["isError"] is True

    up_ok = await _call(
        client,
        tok,
        "upload_visual",
        {
            "adventure": tpl_id,
            "target_type": "scene",
            "target_id": "PLAZA",
            "image_base64": _png_b64(),
            "mime_type": "image/png",
        },
    )
    assert up_ok["structuredContent"]["status"] == "uploaded"
    assert up_ok["structuredContent"]["image_url"].startswith("/data/")

    # Audio render & poll
    async def fake_render_again(tid, _payload, track_id="", db=None, current_user=None):
        return {"id": "0123456789abcdef", "status": "running", "elapsed": 0}

    async def fake_get_audio_job(tid, job_id="", db=None, current_user=None):
        return {"id": job_id, "status": "done", "track_id": "HARBOR_THEME"}

    monkeypatch.setattr(tools_media.editor_audio, "render_track_again", fake_render_again)
    monkeypatch.setattr(tools_media.editor_audio, "get_audio_job", fake_get_audio_job)

    ren = await _call(
        client, tok, "render_audio_track", {"adventure": tpl_id, "track_id": "HARBOR_THEME"}
    )
    assert ren["structuredContent"]["job"]["id"] == "0123456789abcdef"
    aud_poll = await _call(
        client, tok, "get_audio_job_status", {"adventure": tpl_id, "job_id": "0123456789abcdef"}
    )
    assert aud_poll["structuredContent"]["status"] == "done"

    # Thumbnails
    thumb_calls: list[str] = []

    async def fake_thumbs(tid: str):
        thumb_calls.append(tid)

    monkeypatch.setattr(MediaEngine, "ensure_thumbnails", staticmethod(fake_thumbs))
    th_res = await _call(client, tok, "regenerate_thumbnails", {"adventure": tpl_id})
    assert th_res["structuredContent"]["processed_count"] == 1
    assert thumb_calls == [tpl_id]
