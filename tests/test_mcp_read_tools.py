"""Tests for Phase 2 MCP library, session, diagnostics tools, resources, and prompts."""

import json

from backend.core.config import settings
from backend.core.mcp_settings import generate_mcp_token
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.game_session import GameSession
from backend.models.mcp_token import McpToken
from backend.models.session_checkpoint import SessionCheckpoint
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from tests.conftest import TestSessionLocal
from tests.server_settings_helpers import seed_server_settings


def _rpc(method: str, params: dict | None = None, req_id: int = 1) -> dict:
    payload: dict = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        payload["params"] = params
    return payload


async def _seed_world() -> dict[str, str]:
    plain, prefix, digest = generate_mcp_token()
    async with TestSessionLocal() as db:
        await seed_server_settings(
            db,
            mcp_settings={
                "enabled": True,
                "features": {
                    "read_adventures": True,
                    "read_sessions": True,
                    "edit_adventures": False,
                    "generate_adventures": False,
                    "generate_media": False,
                    "diagnostics": True,
                },
                "allow_destructive": False,
                "allow_cross_user_access": False,
            },
        )
        user = User(username="author", hashed_password="x", role="admin")
        db.add(user)
        await db.flush()
        db.add(
            McpToken(
                name="Read Token",
                token_prefix=prefix,
                token_hash=digest,
                user_id=user.id,
            )
        )
        tpl = AdventureTemplate(
            owner_id=user.id,
            title="Sunken Lighthouse",
            origin_id="sunken-lighthouse",
            version="1.2.0",
            language="en",
            teaser="Fog hides the reef.",
            is_ready=True,
            creation_status="Ready",
            init_script="tw.vars.set('tide', 1)\n",
            quests=[{"id": "Q1", "title": "Fix the lens"}],
            audio_tracks=[{"id": "TRK_SEA", "name": "Harbor Fog", "prompt": "cello drone"}],
        )
        db.add(tpl)
        await db.flush()

        tpl_avatar = Avatar(
            user_id=user.id,
            template_id=tpl.id,
            name="Ada",
            role="Investigator",
            inventory=[],
        )
        db.add(tpl_avatar)
        db.add_all(
            [
                WorldScene(
                    id="START",
                    template_id=tpl.id,
                    label="Harbor Quay",
                    description="Cold spray drifts across old stones.",
                ),
                WorldScene(
                    id="TOWER",
                    template_id=tpl.id,
                    label="Lighthouse Base",
                    description="Iron stairs spiral upwards.",
                ),
            ]
        )
        db.add(
            WorldExit(
                template_id=tpl.id,
                from_scene_id="START",
                to_scene_id="TOWER",
                label="an iron door",
                exit_type="bidirectional",
                is_locked=True,
                lock_description="Rusted shut.",
            )
        )
        db.add_all(
            [
                WorldEntity(
                    id="BRAM",
                    template_id=tpl.id,
                    entity_type="NPC",
                    name="Bram",
                    description="Keeper.",
                    current_scene_id="START",
                ),
                WorldEntity(
                    id="SILVER_KEY",
                    template_id=tpl.id,
                    entity_type="OBJECT",
                    item_type="KEY",
                    name="Silver Key",
                    description="Tarnished key.",
                    current_scene_id="TOWER",
                    is_hidden=True,
                    stat_modifier_wisdom=2,
                ),
            ]
        )

        play_avatar = Avatar(
            user_id=user.id,
            template_id=tpl.id,
            name="Ada",
            role="Investigator",
            inventory=[{"id": "SILVER_KEY", "name": "Silver Key", "item_type": "KEY"}],
        )
        db.add(play_avatar)
        await db.flush()
        session = GameSession(
            user_id=user.id,
            avatar_id=play_avatar.id,
            template_id=tpl.id,
            adventure_title=tpl.title,
            status="active",
        )
        db.add(session)
        await db.flush()
        db.add(
            SessionState(
                session_id=session.id,
                user_id=user.id,
                template_id=tpl.id,
                avatar_id=play_avatar.id,
                current_scene_id="START",
                in_game_time=15,
                entity_states={"SILVER_KEY": {"is_hidden": False, "is_in_inventory": True}},
                quests=[{"id": "Q1", "title": "Fix the lens", "completed": False}],
            )
        )
        db.add_all(
            [
                ChatMessage(session_id=session.id, role="assistant", content="Fog rolls in."),
                ChatMessage(session_id=session.id, role="user", content="Look at the quay."),
                ChatMessage(session_id=session.id, role="system", content="Entered START."),
            ]
        )
        db.add(
            SessionCheckpoint(
                session_id=session.id,
                message_index=1,
                state_snapshot={"current_scene_id": "START"},
                trigger_reason="manual",
            )
        )
        await db.commit()
        return {"token": plain, "template_id": tpl.id, "session_id": session.id}


async def _call_tool(client, token: str, name: str, arguments: dict) -> dict:
    res = await client.post(
        "/mcp",
        json=_rpc("tools/call", {"name": name, "arguments": arguments}),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    return res.json()["result"]


async def test_mcp_library_tools(client, setup_test_db):
    seeded = await _seed_world()
    tok = seeded["token"]

    summary = await _call_tool(client, tok, "get_adventure_summary", {"adventure": "Sunken"})
    sc = summary["structuredContent"]
    assert sc["adventure"]["id"] == seeded["template_id"]
    assert sc["init_script_lines"] == 1
    assert "START" in sc["scenes"]
    assert sc["exits"][0]["route"] == "START->TOWER"

    slice_res = await _call_tool(
        client,
        tok,
        "get_adventure_details",
        {"adventure": "sunken-lighthouse", "scene_id": "START"},
    )
    assert slice_res["structuredContent"]["scene"]["id"] == "START"
    assert [n["id"] for n in slice_res["structuredContent"]["neighbour_scenes"]] == ["TOWER"]

    sec_res = await _call_tool(
        client,
        tok,
        "get_adventure_details",
        {"adventure": seeded["template_id"], "section": "audio_tracks"},
    )
    assert sec_res["structuredContent"]["audio_tracks"][0]["id"] == "TRK_SEA"

    manifest_res = await _call_tool(
        client, tok, "export_adventure_manifest", {"adventure": seeded["template_id"]}
    )
    assert manifest_res["structuredContent"]["format"] == "TaleWeaver"
    assert manifest_res["structuredContent"]["adventure"]["title"] == "Sunken Lighthouse"

    ops_res = await _call_tool(client, tok, "list_change_set_operations", {"op": "create_scene"})
    assert "scene_id" in ops_res["structuredContent"]["operations"]["create_scene"]["fields"]

    catalog_res = await _call_tool(
        client, tok, "list_library_catalog", {"include_online": False, "include_disk": True}
    )
    assert "disk_adventures" in catalog_res["structuredContent"]


async def test_mcp_session_tools(client, setup_test_db):
    seeded = await _seed_world()
    tok = seeded["token"]
    sid = seeded["session_id"]

    sessions_res = await _call_tool(client, tok, "list_sessions", {"adventure": "Sunken"})
    assert sessions_res["structuredContent"]["count"] == 1

    state_res = await _call_tool(
        client, tok, "get_session_state", {"session_id": sid[:12], "hidden_only": True}
    )
    state_sc = state_res["structuredContent"]
    assert state_sc["state"]["current_scene_id"] == "START"
    assert state_sc["entities"] == []  # SILVER_KEY was overridden to is_hidden=False

    chat_res = await _call_tool(
        client, tok, "get_session_chat", {"session_id": sid, "limit": 2, "offset": 1}
    )
    chat_sc = chat_res["structuredContent"]
    assert chat_sc["total"] == 3
    assert [m["role"] for m in chat_sc["messages"]] == ["user", "system"]

    cp_res = await _call_tool(client, tok, "get_session_checkpoints", {"session_id": sid})
    assert cp_res["structuredContent"]["count"] == 1
    assert cp_res["structuredContent"]["checkpoints"][0]["scene_id"] == "START"

    integ_res = await _call_tool(client, tok, "check_session_integrity", {"session_id": sid})
    integ_sc = integ_res["structuredContent"]
    assert integ_sc["status"] == "issues_found"
    assert integ_sc["issues"][0]["field"] == "stat_modifier_wisdom"


async def test_mcp_diagnostics_tools_and_path_guard(client, setup_test_db, tmp_path, monkeypatch):
    seeded = await _seed_world()
    tok = seeded["token"]

    db_res = await _call_tool(client, tok, "get_db_status", {})
    assert db_res["structuredContent"]["table_counts"]["adventure_templates"] == 1

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True)
    log_file = logs_dir / "llm_debug.jsonl"
    events = [
        {
            "event_type": "gm.turn.pipeline.total",
            "phase": "total",
            "duration_ms": 1200.0,
            "timestamp": "2026-11-26T10:00:00+00:00",
        },
        {
            "event_type": "gm.turn.request",
            "adventure_id": "a1",
            "game_id": "g1",
            "operation": "chat_turn",
            "phase": "narration",
            "model": "gpt-4o",
            "provider": "openai",
            "timestamp": "2026-11-26T10:00:00+00:00",
        },
        {
            "event_type": "gm.turn.response",
            "adventure_id": "a1",
            "game_id": "g1",
            "operation": "chat_turn",
            "phase": "narration",
            "model": "gpt-4o",
            "provider": "openai",
            "timestamp": "2026-11-26T10:00:02+00:00",
        },
    ]
    log_file.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))

    tel_res = await _call_tool(client, tok, "get_llm_telemetry", {})
    tel_sc = tel_res["structuredContent"]
    assert tel_sc["total_events"] == 3
    assert tel_sc["pipeline_events"][0]["p50_ms"] == 1200.0
    assert tel_sc["request_response_latencies"][0]["p50_ms"] == 2000.0

    traversal = await _call_tool(client, tok, "get_llm_telemetry", {"log_name": "../taleweaver.db"})
    assert traversal["isError"] is True


async def test_mcp_resources_and_prompts(client, setup_test_db):
    seeded = await _seed_world()
    tok = seeded["token"]
    headers = {"Authorization": f"Bearer {tok}"}

    res_list = await client.post("/mcp", json=_rpc("resources/list"), headers=headers)
    uris = {r["uri"] for r in res_list.json()["result"]["resources"]}
    assert "taleweaver://docs/scripting-engine" in uris
    assert "taleweaver://catalogs/styles" in uris

    doc_res = await client.post(
        "/mcp",
        json=_rpc("resources/read", {"uri": "taleweaver://docs/scripting-engine"}),
        headers=headers,
    )
    assert doc_res.status_code == 200
    assert "tw." in doc_res.json()["result"]["contents"][0]["text"]

    summary_res = await client.post(
        "/mcp",
        json=_rpc(
            "resources/read", {"uri": f"taleweaver://adventures/{seeded['template_id']}/summary"}
        ),
        headers=headers,
    )
    assert "Sunken Lighthouse" in summary_res.json()["result"]["contents"][0]["text"]

    session_res = await client.post(
        "/mcp",
        json=_rpc("resources/read", {"uri": f"taleweaver://sessions/{seeded['session_id']}/state"}),
        headers=headers,
    )
    assert "START" in session_res.json()["result"]["contents"][0]["text"]

    prompts_list = await client.post("/mcp", json=_rpc("prompts/list"), headers=headers)
    prompt_names = {p["name"] for p in prompts_list.json()["result"]["prompts"]}
    assert {
        "create_adventure_blueprint",
        "edit_adventure_safely",
        "craft_music_prompts",
        "diagnose_session",
    } <= prompt_names

    music_prompt = await client.post(
        "/mcp",
        json=_rpc(
            "prompts/get", {"name": "craft_music_prompts", "arguments": {"adventure": "Sunken"}}
        ),
        headers=headers,
    )
    assert "TRK_SEA" in music_prompt.json()["result"]["messages"][0]["content"]["text"]
