"""Tests for Phase 3 MCP editor, validation, change-set, import, audio, cutscene, and delete tools."""

from sqlalchemy import select

from backend.core.mcp_settings import generate_mcp_token
from backend.engine.world.sections import default_section
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.mcp_token import McpToken
from backend.models.user import User
from backend.models.world_entity import WorldScene
from tests.conftest import TestSessionLocal
from tests.server_settings_helpers import seed_server_settings


def _rpc(method: str, params: dict | None = None, req_id: int = 1) -> dict:
    payload: dict = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        payload["params"] = params
    return payload


async def _seed_editor_world(
    *, allow_destructive: bool = False, allow_gen: bool = False
) -> dict[str, str]:
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
                    "generate_adventures": allow_gen,
                    "generate_media": False,
                    "diagnostics": True,
                },
                "allow_destructive": allow_destructive,
                "allow_cross_user_access": False,
            },
        )
        user = User(username="editor_user", hashed_password="x", role="admin")
        db.add(user)
        await db.flush()
        db.add(
            McpToken(
                name="Editor Token",
                token_prefix=prefix,
                token_hash=digest,
                user_id=user.id,
            )
        )
        tpl = AdventureTemplate(
            owner_id=user.id,
            title="Moon Temple",
            origin_id="moon-temple",
            version="1.0.0",
            language="en",
            world_sections=[default_section("Moon Temple")],
            is_ready=True,
            creation_status="Ready",
        )
        db.add(tpl)
        await db.flush()
        db.add(Avatar(user_id=user.id, template_id=tpl.id, name="Ada", role="Explorer"))
        db.add(
            WorldScene(
                id="HALL",
                template_id=tpl.id,
                label="Entry Hall",
                description="Stone pillars frame a silent archway.",
                section_id="MAIN",
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


async def test_mcp_validate_blueprint_and_adventure(client, setup_test_db):
    seeded = await _seed_editor_world(allow_gen=False)
    tok = seeded["token"]

    bp_ok = await _call(
        client,
        tok,
        "validate_blueprint",
        {
            "text": (
                "[World]\nwin: Escape\n\n[Protagonist] Ada\n\n"
                "[Sequence: 1] Start\ngoal_scene: HALL\n\n[Scene: HALL] Hall\n"
            )
        },
    )
    assert bp_ok["structuredContent"]["has_tags"] is True
    assert bp_ok["structuredContent"]["errors"] == []
    assert bp_ok["structuredContent"]["counts"]["scene"] == 1

    bp_bad = await _call(
        client,
        tok,
        "validate_blueprint",
        {"text": "[Script: S1] Broken\ntrigger: on_init\ncode: def _bad(): pass\n"},
    )
    assert bp_bad["structuredContent"]["errors"]

    val_struct = await _call(
        client, tok, "validate_adventure", {"adventure": "Moon Temple", "include_ai": False}
    )
    assert val_struct["structuredContent"]["ai_skipped_reason"] == "ai_not_requested"

    val_ai_denied = await _call(
        client, tok, "validate_adventure", {"adventure": "Moon Temple", "include_ai": True}
    )
    assert val_ai_denied["isError"] is True


async def test_mcp_apply_changes_dry_run_commit_and_security(client, setup_test_db):
    seeded = await _seed_editor_world()
    tok = seeded["token"]
    tpl_id = seeded["template_id"]

    ops = [
        {
            "op": "create_scene",
            "scene_id": "CRYPT",
            "label": "Moon Crypt",
            "description": "Cold air drifts from a cracked ceiling.",
        },
        {
            "op": "create_exit",
            "ref": "crypt_gate",
            "from_scene_id": "HALL",
            "to_scene_id": "CRYPT",
            "label": "crescent gate",
            "exit_type": "bidirectional",
        },
    ]

    # Dry run (default) should roll back
    dry_res = await _call(
        client, tok, "apply_adventure_changes", {"adventure": tpl_id, "operations": ops}
    )
    dry_sc = dry_res["structuredContent"]
    assert dry_sc["dry_run"] is True
    assert dry_sc["committed"] is False
    assert "crypt_gate" in dry_sc["refs"]

    async with TestSessionLocal() as db:
        scenes = (
            (await db.execute(select(WorldScene).where(WorldScene.template_id == tpl_id)))
            .scalars()
            .all()
        )
        assert [s.id for s in scenes] == ["HALL"]

    # Commit persists new scene and exit
    commit_res = await _call(
        client,
        tok,
        "apply_adventure_changes",
        {"adventure": tpl_id, "operations": ops, "commit": True},
    )
    assert commit_res["structuredContent"]["committed"] is True

    async with TestSessionLocal() as db:
        scenes = (
            (await db.execute(select(WorldScene).where(WorldScene.template_id == tpl_id)))
            .scalars()
            .all()
        )
        assert {s.id for s in scenes} == {"HALL", "CRYPT"}

    # Operation introducing a new validation error blocks commit when allow_errors=False
    bad_ops = [
        {
            "op": "create_exit",
            "from_scene_id": "HALL",
            "to_scene_id": "CRYPT",
            "label": "locked arch",
            "is_locked": True,
            "lock_description": "Locked tight.",
            "item_to_unlock": "NONEXISTENT_KEY",
        }
    ]
    blocked = await _call(
        client,
        tok,
        "apply_adventure_changes",
        {"adventure": tpl_id, "operations": bad_ops, "commit": True},
    )
    assert blocked["structuredContent"]["committed"] is False
    assert blocked["structuredContent"]["blocked_by_errors"] is True

    # $file references are rejected (CWE-22)
    file_ref = await _call(
        client,
        tok,
        "apply_adventure_changes",
        {
            "adventure": tpl_id,
            "operations": [{"op": "set_init_script", "code": {"$file": "secret.py"}}],
        },
    )
    assert file_ref["isError"] is True


async def test_mcp_import_cutscenes_audio_and_delete(client, setup_test_db):
    seeded = await _seed_editor_world(allow_destructive=False)
    tok = seeded["token"]
    tpl_id = seeded["template_id"]

    # Import minimal .adv manifest
    manifest = {
        "format": "TaleWeaver",
        "version": "1.5.0",
        "adventure": {"title": "Clockwork Vault", "teaser": "Ticking gears."},
        "protagonist": {"name": "Iris", "role": "Tinker"},
        "scenes": [
            {"id": "FOYER", "label": "Foyer", "description": "Brass lamps hum softly."},
        ],
        "exits": [],
        "npcs": [],
        "objects": [],
    }
    imp_res = await _call(
        client, tok, "import_adventure_manifest", {"manifest": manifest, "validate_after": True}
    )
    imp_sc = imp_res["structuredContent"]
    assert imp_sc["title"] == "Clockwork Vault"
    imported_id = imp_sc["template_id"]

    # Duplicate import without overwrite fails cleanly
    dup_res = await _call(
        client, tok, "import_adventure_manifest", {"manifest": manifest, "overwrite": False}
    )
    assert dup_res["isError"] is True

    # Cutscenes set & get
    cs_set = await _call(
        client,
        tok,
        "manage_cutscenes",
        {
            "adventure": tpl_id,
            "action": "set",
            "cutscenes": [
                {"id": "INTRO", "title": "Opening", "slides": [{"text": "Moonlight falls."}]}
            ],
            "intro_cutscene_id": "INTRO",
        },
    )
    assert cs_set["structuredContent"]["intro_cutscene_id"] == "INTRO"
    cs_get = await _call(client, tok, "manage_cutscenes", {"adventure": tpl_id, "action": "get"})
    assert cs_get["structuredContent"]["cutscenes"][0]["id"] == "INTRO"

    # Audio tracks CRUD + scene/title assignment
    trk = await _call(
        client,
        tok,
        "manage_audio_tracks",
        {
            "adventure": tpl_id,
            "action": "create",
            "track_id": "MOON_THEME",
            "name": "Moon Theme",
            "prompt": "slow cello and harp, 72 bpm, seamless loop",
        },
    )
    assert trk["structuredContent"]["track"]["id"] == "MOON_THEME"
    assert trk["structuredContent"]["track"]["source"] == "planned"

    await _call(
        client,
        tok,
        "manage_audio_tracks",
        {
            "adventure": tpl_id,
            "action": "assign_scene",
            "scene_id": "HALL",
            "track_id": "MOON_THEME",
        },
    )
    await _call(
        client,
        tok,
        "manage_audio_tracks",
        {"adventure": tpl_id, "action": "set_title", "track_id": "MOON_THEME"},
    )
    listed = await _call(
        client, tok, "manage_audio_tracks", {"adventure": tpl_id, "action": "list"}
    )
    assert listed["structuredContent"]["title_track_id"] == "MOON_THEME"
    assert listed["structuredContent"]["scene_usage"]["MOON_THEME"] == ["HALL"]

    await _call(
        client,
        tok,
        "manage_audio_tracks",
        {"adventure": tpl_id, "action": "delete", "track_id": "MOON_THEME"},
    )
    listed_after = await _call(
        client, tok, "manage_audio_tracks", {"adventure": tpl_id, "action": "list"}
    )
    assert listed_after["structuredContent"]["tracks"] == []
    assert listed_after["structuredContent"]["title_track_id"] is None

    # delete_adventure is hidden and rejected when allow_destructive=False
    tools_res = await client.post(
        "/mcp", json=_rpc("tools/list"), headers={"Authorization": f"Bearer {tok}"}
    )
    assert "delete_adventure" not in {t["name"] for t in tools_res.json()["result"]["tools"]}
    del_blocked = await _call(
        client,
        tok,
        "delete_adventure",
        {"adventure": imported_id, "confirm_title": "Clockwork Vault"},
    )
    assert del_blocked["isError"] is True

    # Enable allow_destructive=True -> confirm mismatch fails, exact title deletes
    async with TestSessionLocal() as db:
        await seed_server_settings(
            db,
            mcp_settings={
                "enabled": True,
                "features": {
                    "read_adventures": True,
                    "read_sessions": True,
                    "edit_adventures": True,
                    "generate_adventures": False,
                    "generate_media": False,
                    "diagnostics": True,
                },
                "allow_destructive": True,
                "allow_cross_user_access": False,
            },
        )
        await db.commit()

    bad_confirm = await _call(
        client, tok, "delete_adventure", {"adventure": imported_id, "confirm_title": "Wrong Title"}
    )
    assert bad_confirm["isError"] is True

    deleted = await _call(
        client,
        tok,
        "delete_adventure",
        {"adventure": imported_id, "confirm_title": "Clockwork Vault"},
    )
    assert deleted["structuredContent"]["status"] == "deleted"
