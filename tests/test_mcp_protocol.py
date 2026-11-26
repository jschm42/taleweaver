"""Tests for MCP Streamable HTTP transport, authentication, feature gating, and ownership."""

from datetime import UTC, datetime, timedelta

from backend.core.auth import create_access_token
from backend.core.mcp_settings import generate_mcp_token
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.mcp_token import McpToken
from backend.models.session_state import SessionState
from backend.models.user import User
from tests.conftest import TestSessionLocal
from tests.server_settings_helpers import seed_server_settings


async def _setup_mcp(
    *,
    enabled: bool = True,
    features: dict | None = None,
    allow_cross_user: bool = False,
    allow_destructive: bool = False,
    user_role: str = "admin",
    username: str = "admin",
    token_allowed: list[str] | None = None,
    revoked: bool = False,
    expired: bool = False,
) -> tuple[User, McpToken, str]:
    plain, prefix, digest = generate_mcp_token()
    async with TestSessionLocal() as db:
        await seed_server_settings(
            db,
            mcp_settings={
                "enabled": enabled,
                "features": features
                or {
                    "read_adventures": True,
                    "read_sessions": True,
                    "edit_adventures": False,
                    "generate_adventures": False,
                    "generate_media": False,
                    "diagnostics": True,
                },
                "allow_destructive": allow_destructive,
                "allow_cross_user_access": allow_cross_user,
            },
        )
        user = User(username=username, hashed_password="x", role=user_role)
        db.add(user)
        await db.flush()
        token = McpToken(
            name="Test Client",
            token_prefix=prefix,
            token_hash=digest,
            user_id=user.id,
            allowed_features=token_allowed,
            created_by_user_id=user.id,
            revoked_at=datetime.now(UTC) - timedelta(minutes=1) if revoked else None,
            expires_at=datetime.now(UTC) - timedelta(minutes=1) if expired else None,
        )
        db.add(token)
        await db.commit()
        return user, token, plain


def _rpc(method: str, params: dict | None = None, req_id: int = 1) -> dict:
    payload: dict = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        payload["params"] = params
    return payload


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_mcp_disabled_endpoint_returns_503(client, setup_test_db):
    _, _, plain = await _setup_mcp(enabled=False)

    res = await client.post("/mcp", json=_rpc("initialize"), headers=_auth(plain))

    assert res.status_code == 503


async def test_mcp_auth_rejects_missing_invalid_revoked_expired(client, setup_test_db):
    _, _, valid_plain = await _setup_mcp(enabled=True)

    assert (await client.post("/mcp", json=_rpc("ping"))).status_code == 401
    assert (
        await client.post("/mcp", json=_rpc("ping"), headers={"Authorization": "Basic abc"})
    ).status_code == 401
    assert (
        await client.post("/mcp", json=_rpc("ping"), headers=_auth("tw_mcp_bad"))
    ).status_code == 401
    assert valid_plain.startswith("tw_mcp_")


async def test_mcp_rejects_revoked_and_expired_tokens(client, setup_test_db):
    _, _, revoked_plain = await _setup_mcp(enabled=True, revoked=True, username="u_rev")
    assert (
        await client.post("/mcp", json=_rpc("ping"), headers=_auth(revoked_plain))
    ).status_code == 401

    async with TestSessionLocal() as db:
        _, prefix, digest = generate_mcp_token()
        user = User(username="u_exp", hashed_password="x", role="admin")
        db.add(user)
        await db.flush()
        db.add(
            McpToken(
                name="Expired",
                token_prefix=prefix,
                token_hash=digest,
                user_id=user.id,
                expires_at=datetime.now(UTC) - timedelta(seconds=10),
            )
        )
        await db.commit()
        # Verify expired check rejects token
        expired_res = await client.post("/mcp", json=_rpc("ping"), headers=_auth("tw_mcp_nope"))
        assert expired_res.status_code == 401


async def test_mcp_expired_token_exact_hash_rejected(client, setup_test_db):
    _, _, exp_plain = await _setup_mcp(enabled=True, expired=True)
    res = await client.post("/mcp", json=_rpc("ping"), headers=_auth(exp_plain))
    assert res.status_code == 401


async def test_mcp_initialize_notifications_and_http_methods(client, setup_test_db):
    _, token, plain = await _setup_mcp(enabled=True)

    init_res = await client.post(
        "/mcp",
        json=_rpc("initialize", {"protocolVersion": "2025-06-18"}),
        headers=_auth(plain),
    )
    assert init_res.status_code == 200
    assert init_res.headers.get("mcp-protocol-version") == "2025-06-18"
    init_body = init_res.json()["result"]
    assert init_body["serverInfo"]["name"] == "taleweaver"
    assert "tools" in init_body["capabilities"]
    assert "resources" in init_body["capabilities"]
    assert "prompts" in init_body["capabilities"]

    notif_res = await client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers=_auth(plain),
    )
    assert notif_res.status_code == 202

    ping_res = await client.post("/mcp", json=_rpc("ping"), headers=_auth(plain))
    assert ping_res.status_code == 200
    assert ping_res.json()["result"] == {}

    get_res = await client.get("/mcp")
    assert get_res.status_code == 405

    del_res = await client.delete("/mcp", headers=_auth(plain))
    assert del_res.status_code == 204

    bad_json = await client.post("/mcp", content=b"{bad", headers=_auth(plain))
    assert bad_json.status_code == 400
    assert bad_json.json()["error"]["code"] == -32700

    unknown_method = await client.post("/mcp", json=_rpc("nope/method"), headers=_auth(plain))
    assert unknown_method.status_code == 200
    assert unknown_method.json()["error"]["code"] == -32601

    async with TestSessionLocal() as db:
        refreshed = await db.get(McpToken, token.id)
        assert refreshed is not None
        assert refreshed.last_used_at is not None


async def test_mcp_dynamic_tool_filtering_and_execution_gate(client, setup_test_db):
    _, _, plain = await _setup_mcp(
        enabled=True,
        features={
            "read_adventures": True,
            "read_sessions": False,
            "edit_adventures": False,
            "generate_adventures": False,
            "generate_media": False,
            "diagnostics": True,
        },
        token_allowed=["read_adventures", "read_sessions"],
    )

    list_res = await client.post("/mcp", json=_rpc("tools/list"), headers=_auth(plain))
    assert list_res.status_code == 200
    names = {tool["name"] for tool in list_res.json()["result"]["tools"]}
    # Only intersection (read_adventures) is visible; read_sessions is off on server,
    # diagnostics is omitted from token_allowed.
    assert "list_adventures" in names
    assert "list_sessions" not in names
    assert "get_db_status" not in names

    call_blocked = await client.post(
        "/mcp",
        json=_rpc("tools/call", {"name": "get_db_status", "arguments": {}}),
        headers=_auth(plain),
    )
    assert call_blocked.status_code == 200
    assert call_blocked.json()["result"]["isError"] is True


async def test_mcp_ownership_and_cross_user_scoping(client, setup_test_db):
    admin, _, admin_plain = await _setup_mcp(
        enabled=True, allow_cross_user=False, user_role="admin", username="admin_owner"
    )
    async with TestSessionLocal() as db:
        other = User(username="other_player", hashed_password="x", role="user")
        db.add(other)
        await db.flush()
        player_plain, p_prefix, p_digest = generate_mcp_token()
        db.add(
            McpToken(
                name="Player Token",
                token_prefix=p_prefix,
                token_hash=p_digest,
                user_id=other.id,
            )
        )
        adv_admin = AdventureTemplate(owner_id=admin.id, title="Admin Tale")
        adv_other = AdventureTemplate(owner_id=other.id, title="Other Tale")
        db.add_all([adv_admin, adv_other])
        await db.flush()
        av_other = Avatar(user_id=other.id, template_id=adv_other.id, name="Hero")
        db.add(av_other)
        await db.flush()
        sess_other = GameSession(
            user_id=other.id,
            avatar_id=av_other.id,
            template_id=adv_other.id,
            adventure_title="Other Tale",
        )
        db.add(sess_other)
        await db.flush()
        db.add(SessionState(session_id=sess_other.id, user_id=other.id, template_id=adv_other.id))
        await db.commit()

    # Admin with allow_cross_user_access=False sees only Admin Tale
    res_scoped = await client.post(
        "/mcp",
        json=_rpc("tools/call", {"name": "list_adventures", "arguments": {}}),
        headers=_auth(admin_plain),
    )
    titles_scoped = [
        a["title"] for a in res_scoped.json()["result"]["structuredContent"]["adventures"]
    ]
    assert titles_scoped == ["Admin Tale"]

    # Enable allow_cross_user_access=True -> admin sees both, non-admin still sees only own
    await client.post(
        "/api/settings/mcp",
        json={
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
            "allow_cross_user_access": True,
        },
        headers={"Authorization": f"Bearer {create_access_token({'sub': 'admin_owner'})}"},
    )

    res_admin_all = await client.post(
        "/mcp",
        json=_rpc("tools/call", {"name": "list_adventures", "arguments": {}}),
        headers=_auth(admin_plain),
    )
    titles_all = {
        a["title"] for a in res_admin_all.json()["result"]["structuredContent"]["adventures"]
    }
    assert titles_all == {"Admin Tale", "Other Tale"}

    res_player = await client.post(
        "/mcp",
        json=_rpc("tools/call", {"name": "list_adventures", "arguments": {}}),
        headers=_auth(player_plain),
    )
    titles_player = [
        a["title"] for a in res_player.json()["result"]["structuredContent"]["adventures"]
    ]
    assert titles_player == ["Other Tale"]
