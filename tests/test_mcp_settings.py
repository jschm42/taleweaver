"""Tests for MCP server settings, bearer token lifecycle, and feature scoping."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from backend.core.auth import create_access_token
from backend.core.mcp_settings import (
    MCP_BEARER_PREFIX,
    effective_mcp_features,
    verify_mcp_token_hash,
)
from backend.models.mcp_token import McpToken
from backend.models.server_settings import SERVER_SETTINGS_ID, ServerSettings
from backend.models.user import User
from tests.conftest import TestSessionLocal
from tests.server_settings_helpers import seed_server_settings


def _headers(username: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(data={'sub': username})}"}


async def _seed_users(*users: User) -> None:
    async with TestSessionLocal() as db:
        await seed_server_settings(db)
        db.add_all(users)
        await db.commit()


async def test_mcp_settings_defaults(client, setup_test_db):
    await _seed_users(User(username="admin", hashed_password="x", role="admin"))

    res = await client.get("/api/settings/mcp", headers=_headers("admin"))

    assert res.status_code == 200
    data = res.json()
    assert data["enabled"] is False
    assert data["endpoint_path"] == "/mcp"
    assert data["allow_destructive"] is False
    assert data["allow_cross_user_access"] is False
    assert data["features"] == {
        "read_adventures": True,
        "read_sessions": True,
        "edit_adventures": False,
        "generate_adventures": False,
        "generate_media": False,
        "diagnostics": True,
    }


async def test_mcp_settings_update_persists(client, setup_test_db):
    await _seed_users(User(username="admin", hashed_password="x", role="admin"))

    payload = {
        "enabled": True,
        "features": {
            "read_adventures": True,
            "read_sessions": False,
            "edit_adventures": True,
            "generate_adventures": True,
            "generate_media": False,
            "diagnostics": True,
        },
        "allow_destructive": True,
        "allow_cross_user_access": True,
    }
    res = await client.post("/api/settings/mcp", json=payload, headers=_headers("admin"))

    assert res.status_code == 200
    assert res.json()["enabled"] is True
    assert res.json()["features"]["edit_adventures"] is True
    assert res.json()["allow_destructive"] is True

    async with TestSessionLocal() as db:
        server = await db.get(ServerSettings, SERVER_SETTINGS_ID)
        assert server is not None
        assert server.mcp_settings["enabled"] is True
        assert server.mcp_settings["features"]["read_sessions"] is False

    get_res = await client.get("/api/settings/mcp", headers=_headers("admin"))
    assert get_res.status_code == 200
    assert get_res.json()["allow_cross_user_access"] is True


async def test_mcp_endpoints_require_admin(client, setup_test_db):
    await _seed_users(User(username="player", hashed_password="x", role="user"))
    headers = _headers("player")

    assert (await client.get("/api/settings/mcp", headers=headers)).status_code == 403
    assert (await client.post("/api/settings/mcp", json={}, headers=headers)).status_code == 403
    assert (await client.get("/api/settings/mcp/tokens", headers=headers)).status_code == 403
    assert (
        await client.post("/api/settings/mcp/tokens", json={"name": "test"}, headers=headers)
    ).status_code == 403
    assert (await client.delete("/api/settings/mcp/tokens/abc", headers=headers)).status_code == 403


async def test_create_list_and_revoke_mcp_token(client, setup_test_db):
    admin = User(username="admin", hashed_password="x", role="admin")
    await _seed_users(admin)

    create_res = await client.post(
        "/api/settings/mcp/tokens",
        json={"name": "Claude Code Laptop"},
        headers=_headers("admin"),
    )
    assert create_res.status_code == 201
    created = create_res.json()
    plain = created["plain_token"]
    token_meta = created["token"]

    assert plain.startswith(MCP_BEARER_PREFIX)
    assert token_meta["name"] == "Claude Code Laptop"
    assert token_meta["token_prefix"] == plain[:14]
    assert token_meta["username"] == "admin"
    assert token_meta["status"] == "active"
    assert token_meta["allowed_features"] is None

    async with TestSessionLocal() as db:
        row = (
            await db.execute(select(McpToken).where(McpToken.id == token_meta["id"]))
        ).scalar_one()
        assert row.token_hash != plain
        assert verify_mcp_token_hash(plain, row.token_hash) is True
        assert verify_mcp_token_hash("tw_mcp_wrong", row.token_hash) is False

    list_res = await client.get("/api/settings/mcp/tokens", headers=_headers("admin"))
    assert list_res.status_code == 200
    listed = list_res.json()
    assert len(listed) == 1
    assert listed[0]["id"] == token_meta["id"]
    assert "token_hash" not in listed[0]
    assert "plain_token" not in listed[0]

    revoke_res = await client.delete(
        f"/api/settings/mcp/tokens/{token_meta['id']}", headers=_headers("admin")
    )
    assert revoke_res.status_code == 200
    assert revoke_res.json()["status"] == "revoked"
    assert revoke_res.json()["revoked_at"] is not None


async def test_create_token_validation_and_expiry(client, setup_test_db):
    admin = User(username="admin", hashed_password="x", role="admin")
    player = User(username="player", hashed_password="x", role="user")
    await _seed_users(admin, player)

    blank = await client.post(
        "/api/settings/mcp/tokens", json={"name": "   "}, headers=_headers("admin")
    )
    assert blank.status_code == 400

    empty_scope = await client.post(
        "/api/settings/mcp/tokens",
        json={"name": "Empty", "allowed_features": []},
        headers=_headers("admin"),
    )
    assert empty_scope.status_code == 400

    missing_user = await client.post(
        "/api/settings/mcp/tokens",
        json={"name": "Ghost", "user_id": "non-existent"},
        headers=_headers("admin"),
    )
    assert missing_user.status_code == 404

    scoped = await client.post(
        "/api/settings/mcp/tokens",
        json={
            "name": "Player ReadOnly",
            "user_id": player.id,
            "allowed_features": ["diagnostics", "read_adventures", "diagnostics"],
            "expires_in_days": 30,
        },
        headers=_headers("admin"),
    )
    assert scoped.status_code == 201
    scoped_token = scoped.json()["token"]
    assert scoped_token["username"] == "player"
    assert scoped_token["allowed_features"] == ["read_adventures", "diagnostics"]
    assert scoped_token["expires_at"] is not None
    assert scoped_token["status"] == "active"

    # Simulate expiry in DB and confirm status reports expired.
    async with TestSessionLocal() as db:
        row = await db.get(McpToken, scoped_token["id"])
        assert row is not None
        row.expires_at = datetime.now(UTC) - timedelta(minutes=5)
        await db.commit()

    list_res = await client.get("/api/settings/mcp/tokens", headers=_headers("admin"))
    assert list_res.status_code == 200
    assert list_res.json()[0]["status"] == "expired"


def test_effective_mcp_features_logic():
    disabled_cfg = {"enabled": False, "features": {"read_adventures": True}}
    assert effective_mcp_features(disabled_cfg, None) == set()
    assert effective_mcp_features(disabled_cfg, ["read_adventures"]) == set()

    enabled_cfg = {
        "enabled": True,
        "features": {
            "read_adventures": True,
            "read_sessions": True,
            "edit_adventures": False,
            "generate_adventures": False,
            "generate_media": False,
            "diagnostics": True,
        },
    }
    assert effective_mcp_features(enabled_cfg, None) == {
        "read_adventures",
        "read_sessions",
        "diagnostics",
    }
    assert effective_mcp_features(enabled_cfg, ["read_adventures", "edit_adventures"]) == {
        "read_adventures"
    }
