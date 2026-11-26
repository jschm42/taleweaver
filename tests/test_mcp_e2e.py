"""End-to-end integration tests driving Admin REST APIs + /mcp Streamable HTTP JSON-RPC."""

from backend.core.auth import create_access_token
from backend.models.user import User
from tests.conftest import TestSessionLocal
from tests.server_settings_helpers import seed_server_settings

_ALL_FEATURES = {
    "read_adventures": True,
    "read_sessions": True,
    "edit_adventures": True,
    "generate_adventures": True,
    "generate_media": True,
    "diagnostics": True,
}


def _admin_headers(username: str = "mcp_admin") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(data={'sub': username})}"}


def _rpc(method: str, params: dict | None = None, req_id: int = 1) -> dict:
    payload: dict = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        payload["params"] = params
    return payload


async def _mcp_call(client, token: str, tool_name: str, arguments: dict) -> dict:
    res = await client.post(
        "/mcp",
        json=_rpc("tools/call", {"name": tool_name, "arguments": arguments}),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    return res.json()["result"]


async def _seed_admin() -> None:
    async with TestSessionLocal() as db:
        await seed_server_settings(db)
        db.add(User(username="mcp_admin", hashed_password="x", role="admin"))
        await db.commit()


async def test_mcp_full_admin_to_client_lifecycle(client, setup_test_db):
    await _seed_admin()
    admin_hdr = _admin_headers()

    # 1. Endpoint rejects traffic while disabled
    disabled_res = await client.post("/mcp", json=_rpc("initialize"))
    assert disabled_res.status_code == 503

    # 2. Admin enables MCP and all feature groups (destructive deletes off)
    cfg_res = await client.post(
        "/api/settings/mcp",
        json={
            "enabled": True,
            "features": _ALL_FEATURES,
            "allow_destructive": False,
            "allow_cross_user_access": False,
        },
        headers=admin_hdr,
    )
    assert cfg_res.status_code == 200

    # 3. Admin issues a bearer token
    tok_res = await client.post(
        "/api/settings/mcp/tokens",
        json={"name": "E2E Client"},
        headers=admin_hdr,
    )
    assert tok_res.status_code == 201
    plain_token = tok_res.json()["plain_token"]
    token_id = tok_res.json()["token"]["id"]
    mcp_hdr = {"Authorization": f"Bearer {plain_token}"}

    # 4. Initialize & discover full surface (32 tools without delete_adventure, 7+2 resources, 4 prompts)
    init_res = await client.post("/mcp", json=_rpc("initialize"), headers=mcp_hdr)
    assert init_res.status_code == 200
    assert init_res.json()["result"]["serverInfo"]["name"] == "taleweaver"

    tools_res = await client.post("/mcp", json=_rpc("tools/list"), headers=mcp_hdr)
    tool_names = {t["name"] for t in tools_res.json()["result"]["tools"]}
    assert len(tool_names) == 32
    assert "delete_adventure" not in tool_names

    res_list = await client.post("/mcp", json=_rpc("resources/list"), headers=mcp_hdr)
    assert len(res_list.json()["result"]["resources"]) == 7

    tmpl_list = await client.post("/mcp", json=_rpc("resources/templates/list"), headers=mcp_hdr)
    assert len(tmpl_list.json()["result"]["resourceTemplates"]) == 2

    prompt_list = await client.post("/mcp", json=_rpc("prompts/list"), headers=mcp_hdr)
    assert len(prompt_list.json()["result"]["prompts"]) == 4

    # 5. Import adventure, dry-run edit, commit edit, validate, and read live resource
    manifest = {
        "format": "TaleWeaver",
        "version": "1.5.0",
        "adventure": {"title": "E2E Manor", "teaser": "Dusty portraits."},
        "protagonist": {"name": "Nora", "role": "Archivist"},
        "scenes": [{"id": "PORCH", "label": "Front Porch", "description": "Rain patters softly."}],
        "exits": [],
        "npcs": [],
        "objects": [],
    }
    imported = await _mcp_call(
        client, plain_token, "import_adventure_manifest", {"manifest": manifest}
    )
    tpl_id = imported["structuredContent"]["template_id"]

    ops = [{"op": "update", "target_type": "scene", "target_id": "PORCH", "name": "Lantern Porch"}]
    dry = await _mcp_call(
        client,
        plain_token,
        "apply_adventure_changes",
        {"adventure": tpl_id, "operations": ops, "commit": False},
    )
    assert dry["structuredContent"]["committed"] is False

    committed = await _mcp_call(
        client,
        plain_token,
        "apply_adventure_changes",
        {"adventure": tpl_id, "operations": ops, "commit": True},
    )
    assert committed["structuredContent"]["committed"] is True

    val = await _mcp_call(
        client, plain_token, "validate_adventure", {"adventure": tpl_id, "include_ai": False}
    )
    assert val["isError"] is not True

    summary_res = await client.post(
        "/mcp",
        json=_rpc("resources/read", {"uri": f"taleweaver://adventures/{tpl_id}/summary"}),
        headers=mcp_hdr,
    )
    assert "Lantern Porch" in summary_res.json()["result"]["contents"][0]["text"]

    # 6. Enable allow_destructive -> 33 tools visible -> mismatch rejected -> exact title deletes
    cfg_destr = await client.post(
        "/api/settings/mcp",
        json={
            "enabled": True,
            "features": _ALL_FEATURES,
            "allow_destructive": True,
            "allow_cross_user_access": False,
        },
        headers=admin_hdr,
    )
    assert cfg_destr.status_code == 200

    tools_full = await client.post("/mcp", json=_rpc("tools/list"), headers=mcp_hdr)
    full_names = {t["name"] for t in tools_full.json()["result"]["tools"]}
    assert len(full_names) == 33
    assert "delete_adventure" in full_names

    bad_del = await _mcp_call(
        client,
        plain_token,
        "delete_adventure",
        {"adventure": tpl_id, "confirm_title": "Wrong"},
    )
    assert bad_del["isError"] is True

    ok_del = await _mcp_call(
        client,
        plain_token,
        "delete_adventure",
        {"adventure": tpl_id, "confirm_title": "E2E Manor"},
    )
    assert ok_del["structuredContent"]["status"] == "deleted"

    # 7. Revoking token immediately blocks subsequent MCP calls with 401
    rev_res = await client.delete(f"/api/settings/mcp/tokens/{token_id}", headers=admin_hdr)
    assert rev_res.status_code == 200

    after_revoke = await client.post("/mcp", json=_rpc("tools/list"), headers=mcp_hdr)
    assert after_revoke.status_code == 401


async def test_mcp_readonly_token_scope_enforced_end_to_end(client, setup_test_db):
    await _seed_admin()
    admin_hdr = _admin_headers()

    await client.post(
        "/api/settings/mcp",
        json={
            "enabled": True,
            "features": _ALL_FEATURES,
            "allow_destructive": True,
            "allow_cross_user_access": False,
        },
        headers=admin_hdr,
    )
    tok_res = await client.post(
        "/api/settings/mcp/tokens",
        json={
            "name": "Read-Only Agent",
            "allowed_features": ["read_adventures", "read_sessions"],
        },
        headers=admin_hdr,
    )
    assert tok_res.status_code == 201
    mcp_hdr = {"Authorization": f"Bearer {tok_res.json()['plain_token']}"}

    tools_res = await client.post("/mcp", json=_rpc("tools/list"), headers=mcp_hdr)
    tool_names = {t["name"] for t in tools_res.json()["result"]["tools"]}
    assert len(tool_names) == 11
    assert "apply_adventure_changes" not in tool_names
    assert "get_db_status" not in tool_names

    denied_edit = await client.post(
        "/mcp",
        json=_rpc("tools/call", {"name": "apply_adventure_changes", "arguments": {}}),
        headers=mcp_hdr,
    )
    assert denied_edit.status_code == 200
    assert denied_edit.json()["result"]["isError"] is True

    denied_diag = await client.post(
        "/mcp",
        json=_rpc("tools/call", {"name": "get_db_status", "arguments": {}}),
        headers=mcp_hdr,
    )
    assert denied_diag.status_code == 200
    assert denied_diag.json()["result"]["isError"] is True
