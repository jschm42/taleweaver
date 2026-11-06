"""Personal API keys and the key policy: resolution, env precedence, isolation, endpoints."""

import copy

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from backend.api.routes import api_keys_api
from backend.core.api_keys import (
    SOURCE_DISABLED,
    SOURCE_MISSING,
    SOURCE_PERSONAL,
    SOURCE_SERVER,
    PersonalKeyRequiredError,
    build_effective_keys,
    key_source,
    resolve_api_key,
)
from backend.core.auth import create_access_token, get_current_user
from backend.core.config import settings
from backend.core.security import encryption_util
from backend.core.turn_key_preflight import ensure_turn_providers_available
from backend.models.user import User
from tests.conftest import TestSessionLocal
from tests.server_settings_helpers import seed_server_settings

pytestmark = pytest.mark.asyncio

SERVER_KEY = encryption_util.encrypt_key("server-openai")
PERSONAL_KEY = encryption_util.encrypt_key("personal-openai")


def _headers(username: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token(data={'sub': username})}"}


@pytest.fixture
def no_env_keys(monkeypatch):
    monkeypatch.setattr(type(settings), "get_env_api_key", lambda self, provider: None)


@pytest.fixture
def accept_any_key(monkeypatch):
    async def _verify(provider, api_key, client=None):
        return True, None

    monkeypatch.setattr(api_keys_api, "verify_api_key", _verify)


async def _seed(policy=None, **users_personal) -> None:
    async with TestSessionLocal() as db:
        await seed_server_settings(
            db,
            encrypted_api_keys={"openai": SERVER_KEY},
            api_key_policy=policy,
            llm_settings={"small_model_provider": "openai", "complex_model_provider": "openai"},
        )
        db.add(User(username="admin", hashed_password="x", role="admin"))
        for name, personal in users_personal.items():
            db.add(
                User(username=name, hashed_password="x", role="user", personal_api_keys=personal)
            )
        await db.commit()


async def _load(username: str) -> User:
    async with TestSessionLocal() as db:
        return await get_current_user(create_access_token({"sub": username}), db)


# --- Resolution (policy table) --------------------------------------------------------------


@pytest.mark.parametrize(
    "policy,personal,expected_source,expected_key",
    [
        (None, None, SOURCE_SERVER, SERVER_KEY),
        (None, PERSONAL_KEY, SOURCE_SERVER, SERVER_KEY),
        ("user_optional", None, SOURCE_SERVER, SERVER_KEY),
        ("user_optional", PERSONAL_KEY, SOURCE_PERSONAL, PERSONAL_KEY),
        ("user_required", None, SOURCE_MISSING, None),
        ("user_required", PERSONAL_KEY, SOURCE_PERSONAL, PERSONAL_KEY),
        ("disabled", PERSONAL_KEY, SOURCE_DISABLED, None),
    ],
)
async def test_policy_table(policy, personal, expected_source, expected_key):
    keys = build_effective_keys(
        {"openai": SERVER_KEY},
        {"openai": policy} if policy else None,
        {"openai": personal} if personal else None,
    )

    assert key_source(keys, "openai") == expected_source
    assert keys.get("openai") == expected_key


async def test_user_override_beats_server_policy():
    keys = build_effective_keys(
        {"openai": SERVER_KEY}, {"openai": "user_required"}, None, {"openai": "server"}
    )

    assert key_source(keys, "openai") == SOURCE_SERVER


async def test_personal_key_beats_env_key(monkeypatch):
    monkeypatch.setattr(type(settings), "get_env_api_key", lambda self, provider: "env-openai")
    personal = build_effective_keys({}, {"openai": "user_optional"}, {"openai": PERSONAL_KEY})
    server = build_effective_keys({}, None)

    assert resolve_api_key(personal, "openai") == "personal-openai"
    assert resolve_api_key(server, "openai") == "env-openai"


async def test_env_key_is_never_used_for_a_blocked_provider(monkeypatch):
    monkeypatch.setattr(type(settings), "get_env_api_key", lambda self, provider: "env-openai")
    keys = build_effective_keys({}, {"openai": "user_required"})

    with pytest.raises(PersonalKeyRequiredError):
        resolve_api_key(keys, "openai")


async def test_sources_survive_the_image_pipeline_copy():
    keys = build_effective_keys({}, {"openai": "user_required"})

    assert key_source(copy.copy(keys), "openai") == SOURCE_MISSING


async def test_plain_dicts_keep_server_semantics(no_env_keys):
    assert resolve_api_key({"openai": SERVER_KEY}, "openai") == "server-openai"


async def test_personal_keys_never_leak_to_other_users(setup_test_db, no_env_keys):
    await _seed({"openai": "user_optional"}, alice={"openai": PERSONAL_KEY}, bob=None)

    alice = await _load("alice")
    bob = await _load("bob")

    assert resolve_api_key(alice.encrypted_api_keys, "openai") == "personal-openai"
    assert resolve_api_key(bob.encrypted_api_keys, "openai") == "server-openai"
    assert PERSONAL_KEY not in bob.encrypted_api_keys.values()


# --- Chat preflight ------------------------------------------------------------------------


async def test_turn_is_rejected_before_it_starts_without_required_key(setup_test_db):
    await _seed({"openai": "user_required"}, player=None)
    player = await _load("player")

    with pytest.raises(HTTPException) as exc_info:
        ensure_turn_providers_available(player)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "personal_key_required"
    assert exc_info.value.detail["provider"] == "openai"


async def test_turn_passes_with_personal_key(setup_test_db):
    await _seed({"openai": "user_required"}, player={"openai": PERSONAL_KEY})

    ensure_turn_providers_available(await _load("player"))


# --- Player endpoints ----------------------------------------------------------------------


async def test_player_stores_lists_and_removes_a_key(client, setup_test_db, accept_any_key):
    await _seed({"openai": "user_optional"}, player=None)

    stored = await client.put(
        "/api/users/me/api-keys/openai", json={"api_key": ' "sk-mine" '}, headers=_headers("player")
    )
    listed = await client.get("/api/users/me/api-keys", headers=_headers("player"))
    removed = await client.delete("/api/users/me/api-keys/openai", headers=_headers("player"))

    assert stored.status_code == 200
    row = next(p for p in listed.json()["providers"] if p["id"] == "openai")
    assert row == {
        **row,
        "has_personal_key": True,
        "source": SOURCE_PERSONAL,
        "can_store_key": True,
    }
    assert "sk-mine" not in listed.text
    assert removed.status_code == 200
    async with TestSessionLocal() as db:
        player = (await db.execute(select(User).where(User.username == "player"))).scalar_one()
        assert player.personal_api_keys is None


async def test_stored_key_is_encrypted(client, setup_test_db, accept_any_key):
    await _seed({"openai": "user_optional"}, player=None)

    await client.put(
        "/api/users/me/api-keys/openai", json={"api_key": "sk-mine"}, headers=_headers("player")
    )

    async with TestSessionLocal() as db:
        player = (await db.execute(select(User).where(User.username == "player"))).scalar_one()
        assert player.personal_api_keys["openai"] != "sk-mine"
        assert encryption_util.decrypt_key(player.personal_api_keys["openai"]) == "sk-mine"


async def test_player_cannot_store_a_key_when_the_server_pays(client, setup_test_db):
    await _seed(None, player=None)

    res = await client.put(
        "/api/users/me/api-keys/openai", json={"api_key": "sk-mine"}, headers=_headers("player")
    )

    assert res.status_code == 403


async def test_rejected_key_is_not_stored(client, setup_test_db, monkeypatch):
    await _seed({"openai": "user_optional"}, player=None)

    async def _reject(provider, api_key, client=None):
        return False, "The API key was rejected (HTTP 401)."

    monkeypatch.setattr(api_keys_api, "verify_api_key", _reject)

    res = await client.put(
        "/api/users/me/api-keys/openai", json={"api_key": "sk-bad"}, headers=_headers("player")
    )

    assert res.status_code == 400
    assert "rejected" in res.json()["detail"]
    async with TestSessionLocal() as db:
        player = (await db.execute(select(User).where(User.username == "player"))).scalar_one()
        assert player.personal_api_keys is None


async def test_unknown_provider_is_404(client, setup_test_db):
    await _seed({"openai": "user_optional"}, player=None)

    res = await client.put(
        "/api/users/me/api-keys/ollama", json={"api_key": "x"}, headers=_headers("player")
    )

    assert res.status_code == 404


# --- Admin endpoints -----------------------------------------------------------------------


async def test_admin_sets_policy_and_user_override(client, setup_test_db):
    await _seed(None, player=None)
    async with TestSessionLocal() as db:
        player_id = (await db.execute(select(User.id).where(User.username == "player"))).scalar()

    policy = await client.put(
        "/api/settings/key-policy",
        json={"policy": {"openai": "user_required", "anthropic": "server"}},
        headers=_headers("admin"),
    )
    override = await client.put(
        f"/api/users/{player_id}/key-policy",
        json={"policy": {"openai": "server"}},
        headers=_headers("admin"),
    )
    users = await client.get("/api/users", headers=_headers("admin"))

    assert policy.json()["policy"] == {"openai": "user_required"}
    assert override.json()["overrides"] == {"openai": "server"}
    row = next(u for u in users.json() if u["username"] == "player")
    assert row["api_key_policy_overrides"] == {"openai": "server"}
    assert "personal_api_keys" not in row


async def test_policy_endpoints_are_admin_only(client, setup_test_db):
    await _seed(None, player=None)

    res = await client.put(
        "/api/settings/key-policy",
        json={"policy": {"openai": "disabled"}},
        headers=_headers("player"),
    )

    assert res.status_code == 403


async def test_invalid_policy_is_rejected(client, setup_test_db):
    await _seed(None)

    res = await client.put(
        "/api/settings/key-policy", json={"policy": {"openai": "free"}}, headers=_headers("admin")
    )

    assert res.status_code == 422
